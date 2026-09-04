"""Production HTTP boundary for the clean-room C-3PO roster."""
from __future__ import annotations

import html
import os
import tempfile
from email.parser import BytesParser
from email.policy import default
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from operation_pancake.c3po_roster import C3PORosterService, C3PORosterStore, GeminiC3POProvider
from operation_pancake.cfb27_enrichment import (
    CFB27CardChoiceStore,
    load_cfb27_production_cards,
)

MAX_UPLOAD_BYTES = 64 * 1024 * 1024
STYLE = """
:root{font-family:Inter,ui-sans-serif,system-ui;background:#0b0f14;color:#f5f7fa;color-scheme:dark}
*{box-sizing:border-box}body{margin:0;background:linear-gradient(180deg,#111821,#080b10);min-height:100vh}
.shell{max-width:1280px;margin:auto;padding:0 28px 64px}.topbar{height:72px;display:flex;align-items:center;
justify-content:space-between;border-bottom:1px solid #26303b}.brand{font-weight:900;letter-spacing:.08em}
.brand span,.eyebrow{color:#f5b642}.nav{display:flex;gap:24px}.nav a{color:#aeb8c4;text-decoration:none;font-weight:700}
.nav .active{color:#fff}.upload-panel,.team-panel{margin-top:28px;background:#121923;border:1px solid #273241;
border-radius:18px;padding:24px;box-shadow:0 18px 60px #0005}.upload-panel{display:flex;align-items:end;gap:18px}
.upload-panel label{display:grid;gap:8px;flex:1;color:#c4ccd5;font-weight:700}.upload-panel input{padding:13px;
border:1px dashed #445264;border-radius:10px;background:#0c1219}button{border:0;border-radius:10px;padding:14px 22px;
font-weight:900;background:#f5b642;color:#17120a;cursor:pointer}.eyebrow{font-size:12px;font-weight:900;letter-spacing:.16em;
margin:0 0 4px}.team-header h1{font-size:34px;margin:0}.team-subtitle{color:#9ba8b6;margin:8px 0 0}.roster-view{margin-top:30px}
.section-heading{border-bottom:1px solid #2c3744;margin-bottom:14px}.section-heading h2{font-size:14px;letter-spacing:.12em;
color:#f5b642}.player-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:12px}.player{display:flex;
gap:13px;align-items:center;padding:14px;background:#0d141c;border:1px solid #26313d;border-radius:12px}.slot{min-width:48px;
font-size:12px;font-weight:900;color:#91a0b0}.player-copy{display:grid;gap:3px}.name{font-size:16px}.ovr{font-size:12px;
color:#f5b642;font-weight:800}.empty-view{color:#697888}.provider-failure,.upload-error{padding:14px;border-radius:10px;
background:#29181a;color:#ffc2c2}@media(max-width:700px){.nav{display:none}.upload-panel{align-items:stretch;flex-direction:column}}
"""


def _page(content: str) -> bytes:
    upload = (
        '<section class="upload-panel"><form method="post" action="/team/upload" '
        'enctype="multipart/form-data" style="display:contents"><label>Four Team Manager screenshots'
        '<input type="file" name="screenshots" accept="image/jpeg,image/png,image/webp" multiple required>'
        "</label><button>ANALYZE MY TEAM</button></form></section>"
    )
    return (
        '<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" '
        'content="width=device-width,initial-scale=1"><title>Operation Pancake — My Team</title>'
        f"<style>{STYLE}</style></head><body><div class=\"shell\"><header class=\"topbar\">"
        '<div class="brand">🥞 OPERATION PANCAKE</div><nav class="nav"><a class="active" href="/my-team">'
        'MY TEAM</a><a href="#">MARKET</a><a href="#">UPGRADES</a></nav></header><main>'
        + upload + content + "</main></div></body></html>"
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
            path = directory / filename
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
            if urlparse(self.path).path not in {"/", "/setup", "/my-team"}:
                self._send(_page("<h1>Not found</h1>"), 404)
                return
            self._send(_page(self._saved_roster()))

        def do_POST(self) -> None:  # noqa: N802
            path = urlparse(self.path).path
            if path == "/team/card-version":
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                    if length <= 0 or length > 8192:
                        raise ValueError("Card selection size is invalid")
                    fields = parse_qs(self.rfile.read(length).decode("utf-8"))
                    service.select_card_version(
                        fields.get("observation", [""])[0],
                        fields.get("card_id", [""])[0],
                    )
                    self._send(_page(self._saved_roster()))
                except (UnicodeError, ValueError):
                    self._send(_page(self._saved_roster()), 400)
                return
            if path != "/team/upload":
                self._send(_page("<h1>Not found</h1>"), 404)
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length <= 0 or length > MAX_UPLOAD_BYTES:
                    raise ValueError("Upload size is invalid")
                body = self.rfile.read(length)
                upload_root.mkdir(parents=True, exist_ok=True)
                with tempfile.TemporaryDirectory(dir=upload_root) as temporary:
                    screenshots = _uploaded_files(self.headers.get("Content-Type", ""), body, Path(temporary))
                    roster = service.import_four(screenshots)
                rendered = (
                    self._saved_roster()
                    if roster.status == "PROVIDER FAILURE"
                    else service.render_html(roster)
                )
                self._send(_page(rendered))
            except ValueError as exc:
                self._send(_page(f'<p class="upload-error">{html.escape(str(exc))}</p>'), 400)

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
) -> C3PORosterService:
    resolved_root = root.resolve()
    store_path = roster_path or Path(
        os.getenv(
            "PANCAKE_C3PO_ROSTER",
            resolved_root / ".operation_pancake/c3po-roster.json",
        )
    )
    cards = load_cfb27_production_cards(resolved_root)
    choices = CFB27CardChoiceStore(
        choice_path
        or resolved_root / ".operation_pancake/cfb27-card-version-choices.json"
    )
    return C3PORosterService(
        C3PORosterStore(store_path),
        provider or GeminiC3POProvider(),
        enrichment_cards=cards,
        card_choice_store=choices,
    )


def main() -> None:
    root = production_root()
    upload_root = root / ".operation_pancake/c3po-uploads"
    service = create_service(root)
    server = ThreadingHTTPServer(("127.0.0.1", int(os.getenv("PANCAKE_PORT", "8765"))), create_handler(service, upload_root))
    print(f"Operation Pancake My Team: http://127.0.0.1:{server.server_port}/my-team")
    server.serve_forever()


if __name__ == "__main__":
    main()
