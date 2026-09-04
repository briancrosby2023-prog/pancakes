from __future__ import annotations

import inspect
from pathlib import Path

from operation_pancake.c3po_roster import (
    C3POPlayer,
    C3PORoster,
    C3PORosterStore,
    GeminiC3POProvider,
    roster_from_screens,
)
from operation_pancake.c3po_roster_page import render_c3po_roster


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


def test_provider_to_roster_to_persistence_to_html_preserves_c3po_names(tmp_path):
    shots = []
    for index in range(4):
        shot = tmp_path / f"screen-{index}.png"
        shot.write_bytes(b"image")
        shots.append(shot)

    provider = FakeProvider()
    roster = roster_from_screens(shots, provider)
    assert provider.calls == [shot.name for shot in shots]
    assert isinstance(roster, C3PORoster)
    assert {player.name for player in roster.players} == set(NAMES)

    store = C3PORosterStore(tmp_path / "c3po-roster.json")
    store.save(roster)
    restarted = store.load()
    assert restarted == roster

    page = render_c3po_roster(restarted)
    for name in NAMES:
        assert name in page
    assert "Candidate" not in page
    assert "UNRESOLVED" not in page
    assert "UNKNOWN" not in page
    assert "UNASSIGNED" not in page


def test_missing_provider_name_is_name_not_read():
    roster = C3PORoster(
        players=(C3POPlayer(view="OFFENSE", slot="LT1", name=None, displayed_ovr=80),),
        provider="fake-c3po",
        model="fixture",
    )
    assert "NAME NOT READ" in render_c3po_roster(roster)


def test_clean_room_modules_have_no_identity_reconciliation_dependencies():
    import operation_pancake.c3po_roster as roster_module
    import operation_pancake.c3po_roster_page as page_module

    source = inspect.getsource(roster_module) + inspect.getsource(page_module)
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
    )
    for token in forbidden:
        assert token not in source


def test_gemini_provider_failure_is_controlled(tmp_path):
    shot = tmp_path / "screen.png"
    shot.write_bytes(b"image")
    provider = GeminiC3POProvider(api_key="test", client_factory=lambda: (_ for _ in ()).throw(RuntimeError("provider down")))
    result = provider.read(shot)
    assert result["status"] == "PROVIDER FAILURE"
    assert result["players"] == []
