"""Production HTTP boundary for the clean-room C-3PO roster."""
from __future__ import annotations

import html
import io
import logging
import os
import subprocess
import sys
import tempfile
from contextlib import redirect_stdout
from email.parser import BytesParser
from email.policy import default
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from urllib.parse import urlparse

from operation_pancake.c3po_card_version import (
    C3POCardObservationStore,
    GeminiCardVersionAnalyzer,
)
from operation_pancake.c3po_roster import C3PORosterService, C3PORosterStore, GeminiC3POProvider
from operation_pancake.c3po_source_evidence import C3POSourceEvidenceStore

RUNTIME_DIAGNOSTIC_MARKER = "C3PO-RUNTIME-IDENTITY-1"

MAX_UPLOAD_BYTES = 64 * 1024 * 1024
STYLE = """
:root{font-family:Inter,ui-sans-serif,system-ui;background:#0b0f14;color:#f5f7fa;color-scheme:dark}
*{box-sizing:border-box}body{margin:0;background:linear-gradient(180deg,#111821,#080b10);min-height:100vh}
.shell{max-width:1200px;margin:auto;padding:0 28px 64px}.topbar{height:72px;display:flex;align-items:center;
justify-content:space-between;border-bottom:1px solid #26303b}.brand{font-weight:900;letter-spacing:.08em}
.brand span,.eyebrow{color:#f5b642}.nav{display:flex;gap:24px}.nav a{color:#aeb8c4;text-decoration:none;font-weight:700}
.nav .active{color:#fff}.upload-panel,.team-panel{margin-top:28px;background:#121923;border:1px solid #273241;
border-radius:18px;padding:24px;box-shadow:0 18px 60px #0005}.upload-panel{display:flex;align-items:end;gap:18px}
.upload-panel label{display:grid;gap:8px;flex:1;color:#c4ccd5;font-weight:700}.upload-panel input{padding:13px;
border:1px dashed #445264;border-radius:10px;background:#0c1219}button{border:0;border-radius:10px;padding:14px 22px;
font-weight:900;background:#f5b642;color:#17120a;cursor:pointer}.eyebrow{font-size:12px;font-weight:900;letter-spacing:.16em;
margin:0 0 4px}.setup-intro{margin-top:44px}.setup-intro h1,.team-header h1{font-size:34px;margin:0}.team-subtitle,.setup-intro p{color:#9ba8b6;margin:8px 0 0}.team-header{position:relative}.update-team{position:absolute;right:0;top:8px;color:#17120a;background:#f5b642;border-radius:9px;padding:10px 14px;text-decoration:none;font-size:12px;font-weight:900}.roster-view{margin-top:34px}
.section-heading{border-bottom:1px solid #2c3744;margin-bottom:14px}.section-heading h2{font-size:14px;letter-spacing:.12em;
color:#f5b642}.position-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px}.position-group{background:#0d141c;border:1px solid #26313d;border-radius:14px;padding:13px}.position-group h3{margin:0 0 9px;font-size:12px;color:#91a0b0;letter-spacing:.12em}.depth-stack{display:grid;gap:7px}.player{display:flex;gap:12px;align-items:center;padding:13px;background:#121b25;border:1px solid #2a3745;border-radius:10px}.player.backup{margin-left:16px;background:#0f1720;border-color:#222f3c}.slot{min-width:48px;font-size:11px;font-weight:900;color:#91a0b0}.player-copy{display:grid;gap:2px;min-width:0}.name{font-size:16px;overflow-wrap:anywhere}.ovr{font-size:14px;color:#f5b642;font-weight:900}.program{font-size:11px;color:#c7d0da;text-transform:uppercase;letter-spacing:.05em}.program-missing{color:#768493}.empty-view{color:#697888}.provider-failure,.upload-error{padding:14px;border-radius:10px;background:#29181a;color:#ffc2c2}@media(max-width:900px){.position-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:620px){.shell{padding:0 16px 40px}.nav{gap:12px}.position-grid{grid-template-columns:1fr}.upload-panel{align-items:stretch;flex-direction:column}.update-team{position:static;display:inline-block;margin-top:14px}}
"""


def _upload_form() -> str:
    return (
        '<section class="upload-panel"><form method="post" action="/team/upload" '
        'enctype="multipart/form-data" style="display:contents"><label>Four Team Manager screenshots'
        '<input type="file" name="screenshots" accept="image/jpeg,image/png,image/webp" multiple required>'
        "</label><button>ANALYZE MY TEAM</button></form></section>"
    )


def _page(content: str, *, active: str) -> bytes:
    return (
        '<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" '
        'content="width=device-width,initial-scale=1"><title>Operation Pancake — My Team</title>'
        f"<style>{STYLE}</style></head><body><div class=\"shell\"><header class=\"topbar\">"
        '<div class="brand">🥞 OPERATION PANCAKE</div><nav class="nav">'
        f'<a class="{"active" if active == "team" else ""}" href="/my-team">MY TEAM</a>'
        f'<a class="{"active" if active == "setup" else ""}" href="/setup">UPDATE TEAM</a>'
        '</nav></header><main>' + content + "</main></div></body></html>"
    ).encode("utf-8")


def _uploaded_files(content_type: str, body: bytes, directory: Path) -> tuple[Path, ...]:
    message = BytesParser(policy=default).parsebytes(
        f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n".encode() + body
    )
    if not message.is_multipart():
        raise ValueError("Upload must be multipart form data")
    files = []
    for part in message.iter_parts():
        if part.get_content_disposition() != "form-data" or not part.get_filename():
            continue
        filename = Path(part.get_filename()).name
        if filename:
            path = directory / f"{len(files):02d}-{filename}"
            path.write_bytes(part.get_payload(decode=True) or b"")
            files.append(path)
    if len(files) != 4:
        raise ValueError("Exactly four Team Manager screenshots are required")
    return tuple(files)


def create_handler(service: C3PORosterService, upload_root: Path):
    class Handler(BaseHTTPRequestHandler):
        def _send(self, body: bytes, status: int = 200) -> None:
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _saved_roster(self) -> str:
            if not service.store.path.exists():
                return '<section id="my-team" class="team-panel"><h1>My Team</h1><p>Upload four screenshots.</p></section>'
            return service.my_team_html()

        def do_GET(self) -> None:  # noqa: N802
            path = urlparse(self.path).path
            if path in {"/", "/setup"}:
                setup = (
                    '<section class="setup-intro"><p class="eyebrow">TEAM SETUP</p>'
                    '<h1>Update Team</h1><p>Upload all four EA Team Manager views.</p></section>'
                    + _upload_form()
                )
                self._send(_page(setup, active="setup"))
                return
            if path == "/my-team":
                self._send(_page(self._saved_roster(), active="team"))
                return
            self._send(_page("<h1>Not found</h1>", active=""), 404)

        def do_POST(self) -> None:  # noqa: N802
            path = urlparse(self.path).path
            if path != "/team/upload":
                self._send(_page("<h1>Not found</h1>", active=""), 404)
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length <= 0 or length > MAX_UPLOAD_BYTES:
                    raise ValueError("Upload size is invalid")
                body = self.rfile.read(length)
                upload_root.mkdir(parents=True, exist_ok=True)
                with tempfile.TemporaryDirectory(dir=upload_root) as temporary:
                    screenshots = _uploaded_files(self.headers.get("Content-Type", ""), body, Path(temporary))
                    service.import_four(screenshots)
                self.send_response(303)
                self.send_header("Location", "/my-team")
                self.send_header("Content-Length", "0")
                self.end_headers()
            except ValueError as exc:
                self._send(_page(f'<p class="upload-error">{html.escape(str(exc))}</p>', active="setup"), 400)

        def log_message(self, format: str, *args) -> None:
            return

    return Handler


def production_root() -> Path:
    configured = os.getenv("PANCAKE_ROOT")
    if configured:
        return Path(configured).resolve()
    return Path(__file__).resolve().parents[2]


def create_service(
    root: Path,
    provider=None,
    roster_path: Path | None = None,
    choice_path: Path | None = None,
    evidence_path: Path | None = None,
    card_observation_path: Path | None = None,
    version_analyzer=None,
) -> C3PORosterService:
    resolved_root = root.resolve()
    store_path = roster_path or Path(
        os.getenv(
            "PANCAKE_C3PO_ROSTER",
            resolved_root / ".operation_pancake/c3po-roster.json",
        )
    )
    return C3PORosterService(
        C3PORosterStore(store_path),
        provider or GeminiC3POProvider(),
        enrichment_cards=None,
        card_choice_store=None,
        source_evidence_store=C3POSourceEvidenceStore(
            evidence_path or store_path.parent / "c3po-source-evidence.zip"
        ),
        version_analyzer=version_analyzer or GeminiCardVersionAnalyzer(),
        card_observation_store=C3POCardObservationStore(
            card_observation_path
            or resolved_root / ".operation_pancake/c3po-programs.json"
        ),
    )


def main() -> None:
    root = production_root()
    upload_root = root / ".operation_pancake/c3po-uploads"
    service = create_service(root)
    server = ThreadingHTTPServer(("127.0.0.1", int(os.getenv("PANCAKE_PORT", "8765"))), create_handler(service, upload_root))
    print(f"Operation Pancake My Team: http://127.0.0.1:{server.server_port}/my-team")
    server.serve_forever()


def analyze_persisted_card_versions() -> int:
    """Explicitly analyze the already-persisted roster evidence once."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    service = create_service(production_root())
    try:
        roster = service.store.load()
    except (OSError, ValueError, TypeError):
        print("VERSION ANALYZER FAILED: persisted C-3PO roster is unavailable")
        return 1
    outcome = service.analyze_card_versions(roster)
    if outcome.timed_out:
        print("VERSION ANALYZER FAILED: TIMEOUT")
        return 3
    if outcome.rate_limited:
        print("VERSION ANALYZER FAILED: RATE_LIMITED")
        return 2
    if outcome.provider_failed:
        print("VERSION ANALYZER FAILED: PROVIDER_FAILURE")
        return 1
    print("VERSION ANALYZER COMPLETE")
    return 0


def _git_head(root: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return "unavailable"
    return result.stdout.strip() or "unavailable"


def _runtime_diagnostic_body() -> int:
    import operation_pancake
    from operation_pancake import c3po_card_version
    from operation_pancake.c3po_roster import card_version_work_groups

    root = production_root()
    service = create_service(root)
    try:
        release = version("operation-pancake")
    except PackageNotFoundError:
        release = "unavailable"
    analyzer = service.version_analyzer
    model = getattr(analyzer, "model", "unavailable")
    timeout_ms = getattr(analyzer, "timeout_ms", "unavailable")
    print(f"DIAGNOSTIC_MARKER={RUNTIME_DIAGNOSTIC_MARKER}")
    print(f"GIT_HEAD={_git_head(root)}")
    print(f"PACKAGE_RELEASE={release}")
    print(f"PACKAGE_PATH={Path(operation_pancake.__file__).resolve()}")
    print(f"C3PO_ROSTER_APP_PATH={Path(__file__).resolve()}")
    print(f"C3PO_CARD_VERSION_PATH={Path(c3po_card_version.__file__).resolve()}")
    print(f"PYTHON_EXECUTABLE={Path(sys.executable).resolve()}")
    print(f"PYTHON_VERSION={sys.version.split()[0]}")
    print(f"VERSION_MODEL={model}")
    print(f"VERSION_TIMEOUT_MS={timeout_ms}")
    print(
        "PANCAKE_GEMINI_VERSION_TIMEOUT_MS_SET="
        + ("yes" if os.getenv("PANCAKE_GEMINI_VERSION_TIMEOUT_MS") else "no")
    )
    print(
        "PANCAKE_GEMINI_VERSION_MODEL_SET="
        + ("yes" if os.getenv("PANCAKE_GEMINI_VERSION_MODEL") else "no")
    )
    print(
        "PANCAKE_GEMINI_MODEL_SET="
        + ("yes" if os.getenv("PANCAKE_GEMINI_MODEL") else "no")
    )
    print("GEMINI_API_KEY_PRESENT=" + ("yes" if os.getenv("GEMINI_API_KEY") else "no"))
    print(f"PERSISTED_ROSTER_PATH={service.store.path.resolve()}")
    evidence_path = service.source_evidence_store.path.resolve()
    card_observation_path = service.card_observation_store.path.resolve()
    print(f"SOURCE_EVIDENCE_PATH={evidence_path}")
    print("AUTOMATIC_CHOICE_STORE_PATH=unused")
    print("MANUAL_CHOICE_STORE_PATH=unused")
    print(f"C3PO_PROGRAM_STORE_PATH={card_observation_path}")
    print("CHOICE_STORE_MODE=program-observations-only")
    try:
        roster = service.store.load()
        analyzable = tuple(
            observation
            for observation in roster.players
            if observation.name and observation.name.strip()
        )
        distinct = card_version_work_groups(roster)
        evidence = service.source_evidence_store.load_for(roster)
    except (OSError, ValueError, TypeError):
        print("SOURCE_EVIDENCE_COMPATIBLE=no")
        print("SOURCE_IMAGE_COUNT=0")
        print("SOURCE_IMAGE_BYTES=0")
        print("AMBIGUOUS_OBSERVATIONS=0")
        print("DISTINCT_BATCHED_QUESTIONS=0")
        print("RUNTIME_DIAGNOSTIC_STATUS=FAILED_ROSTER_STATE")
        return 1
    print("SOURCE_EVIDENCE_COMPATIBLE=" + ("yes" if evidence is not None else "no"))
    print(f"SOURCE_IMAGE_COUNT={len(evidence.images) if evidence else 0}")
    print(
        "SOURCE_IMAGE_BYTES="
        + str(sum(len(image.payload) for image in evidence.images) if evidence else 0)
    )
    print(f"AMBIGUOUS_OBSERVATIONS={len(analyzable)}")
    print(f"CARD_OBSERVATIONS_TO_ANALYZE={len(analyzable)}")
    print(f"DISTINCT_BATCHED_QUESTIONS={len(distinct)}")
    print("RUNTIME_DIAGNOSTIC_STATUS=PASS")
    return 0


def runtime_diagnostic() -> int:
    """Emit one flushed stdout report without contacting any provider."""
    report = io.StringIO()
    with redirect_stdout(report):
        status = _runtime_diagnostic_body()
    sys.stdout.write(report.getvalue())
    sys.stdout.flush()
    return status


if __name__ == "__main__":
    main()
