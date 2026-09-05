from __future__ import annotations

import inspect
from pathlib import Path

from operation_pancake import (
    c3po_card_version,
    c3po_roster,
    c3po_roster_app,
    c3po_roster_page,
    c3po_source_evidence,
)

REAL = (
    ("OFFENSE", "LT 1", "Josh Petty", 81),
    ("SPECIAL TEAMS", "LS 1", "Thomas Shrader", 85),
    ("OFFENSE", "RG 1", "Zach Rice", 82),
    ("OFFENSE", "RT 2", "Juan Gaston", 81),
    ("DEFENSE", "RRE 1", "Keyan Burnett", 83),
    ("DEFENSE", "SUBLB 2", "Martellus Bennett", 82),
)


def _real_roster():
    return c3po_roster.C3PORoster(
        players=tuple(
            c3po_roster.C3POPlayer(view=view, slot=slot, name=name, displayed_ovr=ovr)
            for view, slot, name, ovr in REAL
        ),
        provider="google-gemini",
        model="gemini-3.7-flash",
    )


def test_real_windows_observations_survive_persistence_restart_and_styled_html(tmp_path):
    store = c3po_roster.C3PORosterStore(tmp_path / "c3po-roster.json")
    original = _real_roster()
    store.save(original)
    restarted = c3po_roster.C3PORosterStore(store.path).load()
    assert restarted == original
    page = c3po_roster_page.render_c3po_roster(restarted)
    assert "OPERATION PANCAKE" in page
    for view, slot, name, ovr in REAL:
        assert view in page
        assert f'data-slot="{slot}"' in page
        assert name in page
        assert f"EA OVR {ovr}" in page
    assert "UNRESOLVED" not in page


def test_duplicate_slot_observations_are_preserved_exactly():
    roster = c3po_roster.C3PORoster(
        players=(
            c3po_roster.C3POPlayer("OFFENSE", "LT", "Josh Petty", 81),
            c3po_roster.C3POPlayer("OFFENSE", "LT", "Sampson Okunlola", 82),
        ),
        provider="google-gemini",
        model="gemini-3.7-flash",
    )
    page = c3po_roster_page.render_c3po_roster(roster)
    assert page.count('data-slot="LT"') == 2
    assert "Josh Petty" in page and "Sampson Okunlola" in page


def test_missing_name_has_only_product_missing_name_presentation():
    roster = c3po_roster.C3PORoster(
        players=(c3po_roster.C3POPlayer("SPECIALISTS", "KR 2", None, 79),),
        provider="google-gemini",
        model="gemini-3.7-flash",
    )
    page = c3po_roster_page.render_c3po_roster(roster)
    assert "NAME NOT READ" in page
    assert "UNRESOLVED" not in page


def test_provider_failure_keeps_saved_roster_and_product_route_renders_it(tmp_path):
    class FailureProvider:
        def read_four(self, screenshots):
            return [{"status": "PROVIDER FAILURE", "provider": "google-gemini", "model": "gemini-3.7-flash"}]

    store = c3po_roster.C3PORosterStore(tmp_path / "c3po-roster.json")
    existing = _real_roster()
    store.save(existing)
    service = c3po_roster.C3PORosterService(store, FailureProvider())
    shots = []
    for index in range(4):
        path = tmp_path / f"shot-{index}.png"
        path.write_bytes(b"image")
        shots.append(path)
    failed = service.import_four(shots)
    assert failed.status == "PROVIDER FAILURE"
    assert store.load() == existing
    page = service.my_team_html()
    for _, _, name, ovr in REAL:
        assert name in page and f"EA OVR {ovr}" in page


def test_product_shell_has_navigation_and_simple_four_image_reimport():
    source = inspect.getsource(c3po_roster_app)
    assert "OPERATION PANCAKE" in source
    assert "MY TEAM" in source
    assert "UPDATE TEAM" in source
    assert 'path in {"/", "/setup"}' in source
    assert "ANALYZE MY TEAM" in source
    assert 'name=\\"screenshots\\"' in source or 'name="screenshots"' in source
    assert "repeat(3,minmax(0,1fr))" in source
    assert "@media(max-width:900px)" in source
    assert "@media(max-width:620px)" in source


def test_styled_production_route_is_direct_clean_room_dependency_only():
    modules = (
        c3po_roster,
        c3po_roster_page,
        c3po_roster_app,
        c3po_card_version,
        c3po_source_evidence,
    )
    source = "\n".join(inspect.getsource(module) for module in modules)
    required = ("C3PORoster", "C3PORosterStore", "render_c3po_roster")
    forbidden = (
        "Candidate", "match_candidate", "c3po_tackle_resolver", "cfb27_ocr_match",
        "canonical_card", "Tesseract", "UNRESOLVED", "UNASSIGNED", "team_import",
        "ocr_team_app", "typed-name", "GeminiTeamTranslator",
    )
    for token in required:
        assert token in source
    for token in forbidden:
        assert token not in source


def test_production_launcher_targets_clean_room_app():
    pyproject = (Path(__file__).parents[1] / "pyproject.toml").read_text(encoding="utf-8")
    assert 'operation-pancake-app = "operation_pancake.c3po_roster_app:main"' in pyproject
