from __future__ import annotations

import threading
import urllib.request
from collections import Counter
from http.server import ThreadingHTTPServer
from pathlib import Path

from operation_pancake import c3po_roster_app, cfb27_enrichment
from operation_pancake.c3po_roster import C3POPlayer, C3PORoster

ROOT = Path(__file__).parents[1]
REAL = (
    ("OFFENSE", "LT 1", "Josh Petty", 81),
    ("SPECIAL TEAMS", "LS 1", "Thomas Shrader", 85),
    ("OFFENSE", "RG 1", "Zach Rice", 82),
    ("OFFENSE", "RT 2", "Juan Gaston", 81),
    ("DEFENSE", "RRE 1", "Keyan Burnett", 83),
    ("DEFENSE", "SUBLB 2", "Martellus Bennett", 82),
)
EXPECTED_CARDINALITY = {
    "Josh Petty": 1,
    "Thomas Shrader": 4,
    "Zach Rice": 2,
    "Juan Gaston": 3,
    "Keyan Burnett": 4,
    "Martellus Bennett": 1,
    "Cason Henry": 3,
    "Malachi Toney": 5,
}


class NoGemini:
    def read_four(self, screenshots):
        raise AssertionError("persisted My Team must not call Gemini")


class RosterProvider:
    def read_four(self, screenshots):
        assert len(tuple(screenshots)) == 4
        return [
            {
                "view": view,
                "players": [
                    {"slot": slot, "name": name, "displayed_ovr": ovr}
                    for row_view, slot, name, ovr in REAL
                    if row_view == view
                ],
                "provider": "fixture",
                "model": "fixture",
            }
            for view in ("OFFENSE", "DEFENSE", "SPECIAL TEAMS", "SPECIALISTS")
        ]


def _roster() -> C3PORoster:
    return C3PORoster(
        tuple(C3POPlayer(view, slot, name, ovr) for view, slot, name, ovr in REAL),
        "google-gemini",
        "gemini-3.7-flash",
    )


def _multipart() -> tuple[bytes, str]:
    boundary = "CFB27-PRODUCTION-POST"
    parts = []
    for index in range(4):
        parts.extend(
            [
                f"--{boundary}\r\n".encode(),
                (
                    'Content-Disposition: form-data; name="screenshots"; '
                    f'filename="screen-{index}.png"\r\n'
                ).encode(),
                b"Content-Type: image/png\r\n\r\nimage\r\n",
            ]
        )
    parts.append(f"--{boundary}--\r\n".encode())
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


def test_real_production_loader_reports_exact_name_cardinality():
    cards = cfb27_enrichment.load_cfb27_production_cards(ROOT)
    counts = Counter(
        cfb27_enrichment.normalize_c3po_name(row.get("player_name")) for row in cards
    )
    actual = {
        name: counts[cfb27_enrichment.normalize_c3po_name(name)]
        for name in EXPECTED_CARDINALITY
    }
    assert actual == EXPECTED_CARDINALITY


def test_restart_loads_real_canonical_data_and_renders_without_gemini(tmp_path, monkeypatch):
    roster_path = tmp_path / "state" / "c3po-roster.json"
    service = c3po_roster_app.create_service(
        ROOT, provider=NoGemini(), roster_path=roster_path
    )
    service.store.save(_roster())
    monkeypatch.chdir(tmp_path)

    page = service.my_team_html()

    for _, _, name, ovr in REAL:
        assert name in page
        assert f"EA OVR {ovr}" in page
    assert page.count("CFB27: ") == 2
    assert page.count("SELECT CARD") == 4
    assert "CFB27 DATA NOT LINKED" not in page
    assert "UNRESOLVED" not in page


def test_successful_four_image_post_renders_real_enrichment(tmp_path):
    service = c3po_roster_app.create_service(
        ROOT,
        provider=RosterProvider(),
        roster_path=tmp_path / "c3po-roster.json",
    )
    handler = c3po_roster_app.create_handler(service, tmp_path / "uploads")
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    body, content_type = _multipart()
    request = urllib.request.Request(
        f"http://127.0.0.1:{server.server_port}/team/upload",
        data=body,
        method="POST",
        headers={"Content-Type": content_type},
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            page = response.read().decode()
    finally:
        server.shutdown()
        server.server_close()

    for _, _, name, ovr in REAL:
        assert name in page
        assert f"EA OVR {ovr}" in page
    assert page.count("CFB27: ") == 2
    assert page.count("SELECT CARD") == 4
    assert "UNRESOLVED" not in page


def test_missing_canonical_source_is_visible_and_never_hides_roster(tmp_path):
    roster_path = tmp_path / "state" / "c3po-roster.json"
    service = c3po_roster_app.create_service(
        tmp_path / "missing-root", provider=NoGemini(), roster_path=roster_path
    )
    service.store.save(_roster())

    page = service.my_team_html()

    for _, _, name, ovr in REAL:
        assert name in page
        assert f"EA OVR {ovr}" in page
    assert page.count("CFB27 DATA NOT LINKED") == len(REAL)
    assert "UNRESOLVED" not in page


def test_application_root_is_module_resolved_not_working_directory(tmp_path, monkeypatch):
    monkeypatch.delenv("PANCAKE_ROOT", raising=False)
    monkeypatch.chdir(tmp_path)
    assert c3po_roster_app.production_root() == ROOT.resolve()
