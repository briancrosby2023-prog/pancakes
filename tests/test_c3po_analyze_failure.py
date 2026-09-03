import json
import threading
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

from operation_pancake import ocr_team_app_visual as app
from operation_pancake import team_app
from operation_pancake.team_import import TeamImportStore


class ProviderFailure(Exception):
    pass


class FailingTranslator:
    calls = 0

    def translate(self, screenshot):
        type(self).calls += 1
        raise ProviderFailure("simulated provider rejection")


def _multipart_four():
    boundary = "C3PO-FAILURE"
    chunks = []
    for index, view in enumerate(("offense", "defense", "special-teams", "specialists"), 1):
        chunks.append(
            (
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="images"; filename="{view}.png"\r\n'
                "Content-Type: image/png\r\n\r\n"
            ).encode()
            + f"pixels-{index}".encode()
            + b"\r\n"
        )
    chunks.append(f"--{boundary}--\r\n".encode())
    return b"".join(chunks), f"multipart/form-data; boundary={boundary}"


def test_four_image_analyze_provider_failure_returns_product_state_and_keeps_server_alive(
    monkeypatch, tmp_path
):
    store = TeamImportStore(tmp_path / "team-import.json", tmp_path / "uploads")
    original_create_handler = team_app.create_handler
    original_extract = team_app._extract
    FailingTranslator.calls = 0

    def fallback(state_store, gm):
        state = state_store.load()
        for screenshot in state.screenshots[-4:]:
            screenshot["extraction_status"] = "OCR FALLBACK COMPLETE"
        state_store.save(state)
        return state

    monkeypatch.setattr(team_app, "TeamImportStore", lambda *args, **kwargs: store)
    monkeypatch.setattr(app.patch6, "install_runtime", lambda: None)
    monkeypatch.setattr(app.patch6, "_extract_current_batch", fallback)
    monkeypatch.setattr(app, "GeminiTeamTranslator", FailingTranslator)
    monkeypatch.setenv("GEMINI_API_KEY", "configured-without-network")
    app.install_runtime()

    server = ThreadingHTTPServer(("127.0.0.1", 0), team_app.create_handler(Path.cwd()))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        body, content_type = _multipart_four()
        base = f"http://127.0.0.1:{server.server_port}"
        request = urllib.request.Request(
            base + "/team/upload",
            data=body,
            method="POST",
            headers={"Content-Type": content_type},
        )
        with urllib.request.urlopen(request, timeout=20) as response:
            assert response.status == 200
            assert "My Team" in response.read().decode()
        with urllib.request.urlopen(base + "/api/team-import", timeout=20) as response:
            state = json.load(response)["state"]
        with urllib.request.urlopen(base + "/setup", timeout=20) as response:
            assert response.status == 200
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        team_app.create_handler = original_create_handler
        team_app._extract = original_extract

    assert FailingTranslator.calls == 1
    assert len(state["screenshots"]) == 4
    assert all(
        screenshot["extraction_status"] == "OCR FALLBACK COMPLETE"
        for screenshot in state["screenshots"]
    )
