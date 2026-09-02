import json
import threading
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

from operation_pancake import ocr_team_app_patch6 as runtime
from operation_pancake import team_app
from operation_pancake.c3po_vision import PlayerObservation, TackleScreenObservation, TackleSlotObservation
from operation_pancake.team_import import Candidate, TeamImportStore


class ConfiguredTranslator:
    calls = 0
    def translate_offense_tackles(self, screenshot):
        type(self).calls += 1
        return TackleScreenObservation("OFFENSE", {
            "LT1": TackleSlotObservation(PlayerObservation("Josh Petty", 80), ()),
            "RT1": TackleSlotObservation(PlayerObservation("Cason Henry", 85), (PlayerObservation("Juan Gaston", 81),)),
        }, "configured-fixture", "deterministic-hosted")


def _multipart():
    boundary = "C3PO-HOSTED"
    body = (f'--{boundary}\r\nContent-Disposition: form-data; name="images"; filename="offense.png"\r\nContent-Type: image/png\r\n\r\n'.encode() + b"pixels\r\n" + f"--{boundary}--\r\n".encode())
    return body, f"multipart/form-data; boundary={boundary}"


def test_actual_team_upload_invokes_configured_c3po_and_persists(monkeypatch, tmp_path):
    store = TeamImportStore(tmp_path / "team-import.json", tmp_path / "uploads")
    monkeypatch.setattr(team_app, "TeamImportStore", lambda *args, **kwargs: store)
    monkeypatch.setenv("GEMINI_API_KEY", "configured-without-network")
    monkeypatch.setattr(runtime, "C3PO_TRANSLATOR_FACTORY", ConfiguredTranslator)

    def accepted_ocr(state_store, gm):
        state = state_store.load(); shot = state.screenshots[-1]; shot["view"] = "OFFENSE"; shot["extraction_status"] = "OCR READ — OFFENSE"
        state.candidates = [Candidate("lt","OFFENSE","LT1",player_name="legacy-lt"), Candidate("rt","OFFENSE","RT1",player_name="legacy-rt"), Candidate("qb","OFFENSE","QB1",player_name="KEEP QB")]
        state_store.save(state); return state

    monkeypatch.setattr(runtime.patch5, "_extract_unique", accepted_ocr)
    runtime.install_runtime()
    server = ThreadingHTTPServer(("127.0.0.1", 0), team_app.create_handler(Path.cwd()))
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    try:
        body, content_type = _multipart(); base = f"http://127.0.0.1:{server.server_port}"
        req = urllib.request.Request(base + "/team/upload", data=body, method="POST", headers={"Content-Type":content_type})
        opener = urllib.request.build_opener(urllib.request.HTTPRedirectHandler())
        with opener.open(req, timeout=20) as response: assert response.status == 200
        with urllib.request.urlopen(base + "/api/team-import", timeout=20) as response: state = json.load(response)["state"]
    finally:
        server.shutdown(); server.server_close(); thread.join(timeout=5)

    assert ConfiguredTranslator.calls == 1
    rt = next(c for c in state["candidates"] if c["slot"] == "RT1")
    assert rt["player_name"] == "Cason Henry" and rt["canonical_card_id"]
    assert rt["backups"][0]["player_name"] == "Juan Gaston" and rt["backups"][0]["displayed_ovr"] == 81
    assert next(c for c in state["candidates"] if c["slot"] == "QB1")["player_name"] == "KEEP QB"
    restarted = TeamImportStore(tmp_path / "team-import.json", tmp_path / "uploads").load()
    assert next(c for c in restarted.candidates if c.slot == "RT1").player_name == "Cason Henry"
    assert restarted.team_observations["c3po_tackles"]["provider"] == "configured-fixture"
