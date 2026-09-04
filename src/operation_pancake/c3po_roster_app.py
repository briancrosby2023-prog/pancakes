"""Production HTTP boundary for the clean-room C-3PO roster."""
from __future__ import annotations

import html
import os
import tempfile
from email.parser import BytesParser
from email.policy import default
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from operation_pancake.c3po_roster import (
    C3PORosterService,
    C3PORosterStore,
    GeminiC3POProvider,
)
from operation_pancake.c3po_roster_page import render_c3po_roster

MAX_UPLOAD_BYTES = 64 * 1024 * 1024


def _page(content: str) -> bytes:
    upload = (
        '<form method="post" action="/team/upload" enctype="multipart/form-data">'
        '<label>Four Team Manager screenshots'
        '<input type="file" name="screenshots" accept="image/*" multiple required>'
        "</label><button>ANALYZE MY TEAM</button></form>"
    )
    return (
        "<!doctype html><html><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
        "<title>Pancake — My Team</title></head><body><main>"
        + upload
        + content
        + "</main></body></html>"
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
        if not filename:
            continue
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
                return (
                    '<section id="my-team"><h1>My Team</h1>'
                    "<p>Upload four screenshots.</p></section>"
                )
            return service.my_team_html()

        def do_GET(self) -> None:  # noqa: N802
            if urlparse(self.path).path not in {"/", "/setup", "/my-team"}:
                self._send(_page("<h1>Not found</h1>"), 404)
                return
            self._send(_page(self._saved_roster()))

        def do_POST(self) -> None:  # noqa: N802
            if urlparse(self.path).path != "/team/upload":
                self._send(_page("<h1>Not found</h1>"), 404)
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length <= 0 or length > MAX_UPLOAD_BYTES:
                    raise ValueError("Upload size is invalid")
                body = self.rfile.read(length)
                upload_root.mkdir(parents=True, exist_ok=True)
                with tempfile.TemporaryDirectory(dir=upload_root) as temporary:
                    screenshots = _uploaded_files(
                        self.headers.get("Content-Type", ""), body, Path(temporary)
                    )
                    roster = service.import_four(screenshots)
                self._send(_page(render_c3po_roster(roster)))
            except ValueError as exc:
                self._send(_page(f'<p class="upload-error">{html.escape(str(exc))}</p>'), 400)

        def log_message(self, format: str, *args) -> None:
            return

    return Handler


def main() -> None:
    root = Path(os.getenv("PANCAKE_ROOT", Path.cwd()))
    roster_path = Path(
        os.getenv("PANCAKE_C3PO_ROSTER", root / ".operation_pancake/c3po-roster.json")
    )
    upload_root = root / ".operation_pancake/c3po-uploads"
    service = C3PORosterService(C3PORosterStore(roster_path), GeminiC3POProvider())
    server = ThreadingHTTPServer(
        ("127.0.0.1", int(os.getenv("PANCAKE_PORT", "8765"))),
        create_handler(service, upload_root),
    )
    print(f"Pancake clean-room My Team: http://127.0.0.1:{server.server_port}/setup")
    server.serve_forever()


if __name__ == "__main__":
    main()
