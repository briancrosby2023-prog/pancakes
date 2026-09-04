from __future__ import annotations

import threading
import urllib.parse
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
EXPECTED_STATE = {
    "Josh Petty": "LINKED",
    "Thomas Shrader": "SELECT CARD",
    "Zach Rice": "SELECT CARD",
    "Juan Gaston": "SELECT CARD",
    "Keyan Burnett": "SELECT CARD",
    "Martellus Bennett": "LINKED",
    "Cason Henry": "SELECT CARD",
    "Malachi Toney": "SELECT CARD",
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


def _eight_player_roster() -> C3PORoster:
    observations = REAL + (
        ("OFFENSE", "RT 1", "Cason Henry", 86),
        ("SPECIALISTS", "KR 1", "Malachi Toney", 89),
    )
    return C3PORoster(
        tuple(C3POPlayer(view, slot, name, ovr) for view, slot, name, ovr in observations),
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


def test_real_card_families_apply_only_the_safe_singleton_rule():
    roster = _eight_player_roster()
    cards = cfb27_enrichment.load_cfb27_production_cards(ROOT)

    result = cfb27_enrichment.enrich_c3po_roster(roster, cards)

    assert result.roster == roster
    assert tuple(row.observation for row in result.players) == roster.players
    assert {row.observation.name: row.state for row in result.players} == EXPECTED_STATE
    assert next(row for row in result.players if row.observation.name == "Keyan Burnett").choices


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
    evidence = service.source_evidence_store.load_for(service.store.load())
    assert evidence is not None
    assert tuple(image.order for image in evidence.images) == (0, 1, 2, 3)
    assert all(image.mime_type == "image/png" for image in evidence.images)
    assert all(image.payload == b"image" for image in evidence.images)


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


def test_manual_card_ui_contains_only_the_exact_player_family(tmp_path):
    roster = C3PORoster(
        (C3POPlayer("SPECIAL TEAMS", "LS 1", "Thomas Shrader", 85),),
        "google-gemini",
        "gemini-3.7-flash",
    )
    service = c3po_roster_app.create_service(
        ROOT,
        provider=NoGemini(),
        roster_path=tmp_path / "roster.json",
        choice_path=tmp_path / "choices.json",
    )
    service.store.save(roster)

    page = service.my_team_html()

    cards = cfb27_enrichment.load_cfb27_production_cards(ROOT)
    thomas_ids = {
        row["card_id"]
        for row in cards
        if cfb27_enrichment.normalize_c3po_name(row.get("player_name"))
        == "thomasshrader"
    }
    other_ids = {
        row["card_id"]
        for row in cards
        if cfb27_enrichment.normalize_c3po_name(row.get("player_name")) == "zachrice"
    }
    assert 'action="/team/card-version"' in page
    assert all(f'value="{card_id}"' in page for card_id in thomas_ids)
    assert all(f'value="{card_id}"' not in page for card_id in other_ids)
    assert page.count("Thomas Shrader") == 1


def test_manual_card_ui_requires_an_explicit_choice_and_links_real_card_details(
    tmp_path,
):
    roster = C3PORoster(
        (C3POPlayer("SPECIAL TEAMS", "LS 1", "Thomas Shrader", 85),),
        "google-gemini",
        "gemini-3.7-flash",
    )
    service = c3po_roster_app.create_service(
        ROOT,
        provider=NoGemini(),
        roster_path=tmp_path / "roster.json",
        choice_path=tmp_path / "choices.json",
    )
    service.store.save(roster)

    page = service.my_team_html()

    assert '<input type="radio" name="card_id"' in page
    assert 'name="card_id" required' in page
    assert " checked" not in page
    assert "84 OVR · LG · Phenoms" in page
    assert "81 OVR · LG · Core Rare" in page
    assert (
        'href="https://cfb.fan/players/21328-thomas-shrader/27-260021328/"'
        in page
    )
    assert 'target="_blank" rel="noopener noreferrer">VIEW CARD</a>' in page


def test_manual_choice_persists_across_restart_and_raw_roster_is_immutable(tmp_path):
    roster = C3PORoster(
        (C3POPlayer("SPECIAL TEAMS", "LS 1", "Thomas Shrader", 85),),
        "google-gemini",
        "gemini-3.7-flash",
    )
    roster_path = tmp_path / "roster.json"
    choice_path = tmp_path / "choices.json"
    service = c3po_roster_app.create_service(
        ROOT,
        provider=NoGemini(),
        roster_path=roster_path,
        choice_path=choice_path,
    )
    service.store.save(roster)
    before = roster_path.read_bytes()
    fingerprint = cfb27_enrichment.observation_fingerprint(roster.players[0], 0)
    body = urllib.parse.urlencode(
        {"observation": fingerprint, "card_id": "card:38d5dbb6bd21993e002b"}
    ).encode()
    handler = c3po_roster_app.create_handler(service, tmp_path / "uploads")
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    request = urllib.request.Request(
        f"http://127.0.0.1:{server.server_port}/team/card-version",
        data=body,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            selected_page = response.read().decode()
    finally:
        server.shutdown()
        server.server_close()

    restarted = c3po_roster_app.create_service(
        ROOT,
        provider=NoGemini(),
        roster_path=roster_path,
        choice_path=choice_path,
    )
    restart_page = restarted.my_team_html()
    assert "CFB27: LG · 84 OVR · Phenoms" in selected_page
    assert "CFB27: LG · 84 OVR · Phenoms" in restart_page
    assert "SELECT CARD" not in restart_page
    assert roster_path.read_bytes() == before
    assert restarted.store.load() == roster


def test_incompatible_stale_choice_fails_open_to_select_card(tmp_path):
    class ChangedRosterProvider:
        def read_four(self, screenshots):
            assert len(tuple(screenshots)) == 4
            return [
                {
                    "view": view,
                    "players": (
                        [{"slot": "LS 1", "name": "Thomas Shrader", "displayed_ovr": 86}]
                        if view == "SPECIAL TEAMS"
                        else []
                    ),
                    "provider": "fixture",
                    "model": "fixture",
                }
                for view in ("OFFENSE", "DEFENSE", "SPECIAL TEAMS", "SPECIALISTS")
            ]

    roster_path = tmp_path / "roster.json"
    choice_path = tmp_path / "choices.json"
    original = C3PORoster(
        (C3POPlayer("SPECIAL TEAMS", "LS 1", "Thomas Shrader", 85),), "p", "m"
    )
    service = c3po_roster_app.create_service(
        ROOT,
        provider=NoGemini(),
        roster_path=roster_path,
        choice_path=choice_path,
    )
    service.store.save(original)
    fingerprint = cfb27_enrichment.observation_fingerprint(original.players[0], 0)
    assert not service.select_card_version(fingerprint, "card:4a964d14b782d8c7c325")
    assert service.select_card_version(fingerprint, "card:38d5dbb6bd21993e002b")

    restarted = c3po_roster_app.create_service(
        ROOT,
        provider=ChangedRosterProvider(),
        roster_path=roster_path,
        choice_path=choice_path,
    )
    shots = []
    for index in range(4):
        shot = tmp_path / f"changed-{index}.png"
        shot.write_bytes(b"image")
        shots.append(shot)
    changed = restarted.import_four(shots)
    page = restarted.my_team_html()

    assert "Thomas Shrader" in page
    assert "EA OVR 86" in page
    assert "SELECT CARD" in page
    assert "CFB27: LG · 84 OVR · Phenoms" not in page
    assert restarted.store.load() == changed


def test_manual_card_choice_ignores_lineup_position_as_identity_veto(tmp_path):
    roster = C3PORoster(
        (C3POPlayer("DEFENSE", "RRE 1", "Keyan Burnett", 83),), "p", "m"
    )
    service = c3po_roster_app.create_service(
        ROOT,
        provider=NoGemini(),
        roster_path=tmp_path / "roster.json",
        choice_path=tmp_path / "choices.json",
    )
    service.store.save(roster)
    fingerprint = cfb27_enrichment.observation_fingerprint(roster.players[0], 0)

    assert service.select_card_version(fingerprint, "card:8bfb91f78594f2e4a227")
    page = service.my_team_html()
    assert "Keyan Burnett" in page
    assert "EA OVR 83" in page
    assert "CFB27: TE · 82 OVR · Phenoms" in page


def test_application_root_is_module_resolved_not_working_directory(tmp_path, monkeypatch):
    monkeypatch.delenv("PANCAKE_ROOT", raising=False)
    monkeypatch.chdir(tmp_path)
    assert c3po_roster_app.production_root() == ROOT.resolve()
