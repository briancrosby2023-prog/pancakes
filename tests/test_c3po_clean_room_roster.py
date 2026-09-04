from __future__ import annotations

import inspect
import threading
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

from operation_pancake import c3po_roster, c3po_roster_app, c3po_roster_page

NAMES = (
    "Josh Petty",
    "Thomas Shrader",
    "Zach Rice",
    "Juan Gaston",
    "Keyan Burnett",
    "Martellus Bennett",
)


class FakeProvider:
    def __init__(self):
        self.calls = []

    def read(self, screenshot: Path):
        self.calls.append(screenshot.name)
        index = len(self.calls) - 1
        views = ("OFFENSE", "DEFENSE", "SPECIAL TEAMS", "SPECIALISTS")
        pairs = (
            (("LT1", "Josh Petty", 80), ("RG1", "Zach Rice", 84)),
            (("RRE1", "Keyan Burnett", 85), ("SUBLB1", "Martellus Bennett", 83)),
            (("LS1", "Thomas Shrader", None),),
            (("RLE1", "Juan Gaston", 81),),
        )
        return {
            "view": views[index],
            "players": [
                {"slot": slot, "name": name, "displayed_ovr": ovr, "backups": []}
                for slot, name, ovr in pairs[index]
            ],
            "provider": "fake-c3po",
            "model": "fixture",
        }


def _shots(tmp_path):
    shots = []
    for index in range(4):
        shot = tmp_path / f"screen-{index}.png"
        shot.write_bytes(b"image")
        shots.append(shot)
    return shots


def _multipart(shots):
    boundary = "C3PO-CLEAN-ROOM"
    parts = []
    for shot in shots:
        parts.extend(
            [
                f"--{boundary}\r\n".encode(),
                (
                    'Content-Disposition: form-data; name="screenshots"; '
                    f'filename="{shot.name}"\r\n'
                ).encode(),
                b"Content-Type: image/png\r\n\r\n",
                shot.read_bytes(),
                b"\r\n",
            ]
        )
    parts.append(f"--{boundary}--\r\n".encode())
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


def _serve(handler):
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, f"http://127.0.0.1:{server.server_port}"


def test_provider_to_roster_to_persistence_to_html_preserves_c3po_names(tmp_path):
    shots = _shots(tmp_path)
    provider = FakeProvider()
    roster = c3po_roster.roster_from_screens(shots, provider)
    assert provider.calls == [shot.name for shot in shots]
    assert isinstance(roster, c3po_roster.C3PORoster)
    assert {player.name for player in roster.players} == set(NAMES)

    store = c3po_roster.C3PORosterStore(tmp_path / "c3po-roster.json")
    store.save(roster)
    restarted = store.load()
    assert restarted == roster

    page = c3po_roster_page.render_c3po_roster(restarted)
    for name in NAMES:
        assert name in page
    assert "Candidate" not in page
    assert "UNRESOLVED" not in page
    assert "UNKNOWN" not in page
    assert "UNASSIGNED" not in page


def test_service_is_the_four_screenshot_to_persisted_my_team_boundary(tmp_path):
    store = c3po_roster.C3PORosterStore(tmp_path / "c3po-roster.json")
    service = c3po_roster.C3PORosterService(store, FakeProvider())
    roster = service.import_four(_shots(tmp_path))
    assert store.load() == roster
    page = service.my_team_html()
    for name in NAMES:
        assert name in page


def test_four_image_production_post_uses_clean_room_service_and_html(tmp_path):
    provider = FakeProvider()
    store = c3po_roster.C3PORosterStore(tmp_path / "c3po-roster.json")
    service = c3po_roster.C3PORosterService(store, provider)
    handler = c3po_roster_app.create_handler(service, tmp_path / "uploads")
    server, base = _serve(handler)
    body, content_type = _multipart(_shots(tmp_path))
    try:
        request = urllib.request.Request(
            base + "/team/upload",
            data=body,
            method="POST",
            headers={"Content-Type": content_type},
        )
        with urllib.request.urlopen(request, timeout=10) as response:
            page = response.read().decode()
        with urllib.request.urlopen(base + "/my-team", timeout=10) as response:
            persisted_page = response.read().decode()
    finally:
        server.shutdown()
        server.server_close()

    assert provider.calls == [f"screen-{index}.png" for index in range(4)]
    assert store.load().players
    for name in NAMES:
        assert name in page
        assert name in persisted_page
    for token in ("UNRESOLVED", "UNKNOWN", "UNASSIGNED", "WHO IS THIS PLAYER?"):
        assert token not in page


def test_missing_provider_name_is_name_not_read():
    roster = c3po_roster.C3PORoster(
        players=(
            c3po_roster.C3POPlayer(
                view="OFFENSE", slot="LT1", name=None, displayed_ovr=80
            ),
        ),
        provider="fake-c3po",
        model="fixture",
    )
    assert "NAME NOT READ" in c3po_roster_page.render_c3po_roster(roster)


def test_clean_room_modules_have_no_identity_reconciliation_dependencies():
    source = "".join(
        inspect.getsource(module)
        for module in (c3po_roster, c3po_roster_app, c3po_roster_page)
    )
    forbidden = (
        "Candidate",
        "match_candidate",
        "tackle_resolver",
        "cfb27_ocr_match",
        "normalize_name",
        "Tesseract",
        "canonical_card",
        "UNRESOLVED",
        "UNASSIGNED",
        "GeminiTeamTranslator",
        "team_import",
        "ocr_team_app",
        "typed-name",
    )
    for token in forbidden:
        assert token not in source


def test_gemini_provider_failure_is_controlled_and_does_not_replace_roster(tmp_path):
    store = c3po_roster.C3PORosterStore(tmp_path / "c3po-roster.json")
    existing = c3po_roster.roster_from_screens(_shots(tmp_path), FakeProvider())
    store.save(existing)
    provider = c3po_roster.GeminiC3POProvider(
        api_key="test",
        client_factory=lambda: (_ for _ in ()).throw(RuntimeError("provider down")),
    )
    result = provider.read(tmp_path / "screen-0.png")
    assert result["status"] == "PROVIDER FAILURE"
    assert result["players"] == []

    service = c3po_roster.C3PORosterService(store, provider)
    failed = service.import_four(_shots(tmp_path))
    assert failed.status == "PROVIDER FAILURE"
    assert store.load() == existing


def test_production_launcher_targets_clean_room_app():
    pyproject = (Path(__file__).parents[1] / "pyproject.toml").read_text(encoding="utf-8")
    assert (
        'operation-pancake-app = "operation_pancake.c3po_roster_app:main"'
        in pyproject
    )
