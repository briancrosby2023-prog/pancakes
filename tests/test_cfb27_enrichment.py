from __future__ import annotations

import inspect

from operation_pancake import cfb27_enrichment
from operation_pancake.c3po_roster import C3POPlayer, C3PORoster, C3PORosterStore
from operation_pancake.c3po_roster_page import render_c3po_roster

REAL = (
    ("OFFENSE", "LT 1", "Josh Petty", 81),
    ("SPECIAL TEAMS", "LS 1", "Thomas Shrader", 85),
    ("OFFENSE", "RG 1", "Zach Rice", 82),
    ("OFFENSE", "RT 2", "Juan Gaston", 81),
    ("DEFENSE", "RRE 1", "Keyan Burnett", 83),
    ("DEFENSE", "SUBLB 2", "Martellus Bennett", 82),
)


def _roster():
    return C3PORoster(
        tuple(C3POPlayer(view, slot, name, ovr) for view, slot, name, ovr in REAL),
        "google-gemini",
        "gemini-3.7-flash",
    )


def test_real_observations_survive_persistence_enrichment_and_html(tmp_path):
    store = C3PORosterStore(tmp_path / "roster.json")
    original = _roster()
    store.save(original)
    persisted = store.load()
    cards = [
        {"player_name": "Josh Petty", "position": "RT", "native_overall": 80, "program": "Phenoms"},
        {"player_name": "Juan Gaston", "position": "LT", "native_overall": 80, "program": "Phenoms"},
    ]
    result = cfb27_enrichment.enrich_c3po_roster(persisted, cards)
    assert result.roster == original
    assert tuple(row.observation for row in result.players) == original.players
    page = render_c3po_roster(persisted, result)
    for _, slot, name, ovr in REAL:
        assert f'data-slot="{slot}"' in page
        assert name in page
        assert f"EA OVR {ovr}" in page
    assert "UNRESOLVED" not in page
    assert "CFB27: RT · 80 OVR · Phenoms" in page
    assert "CFB27: LT · 80 OVR · Phenoms" in page


def test_zero_exact_match_keeps_player_visible():
    roster = _roster()
    result = cfb27_enrichment.enrich_c3po_roster(roster, [])
    page = render_c3po_roster(roster, result)
    assert len(result.players) == len(roster.players)
    assert all(row.state == "CFB27 DATA NOT LINKED" for row in result.players)
    assert all(row.observation in roster.players for row in result.players)
    assert "Juan Gaston" in page and "EA OVR 81" in page
    assert "CFB27 DATA NOT LINKED" in page


def test_multiple_exact_cards_are_card_ambiguity_not_identity_ambiguity():
    roster = C3PORoster((C3POPlayer("OFFENSE", "RT 2", "Juan Gaston", 81),), "p", "m")
    cards = [
        {"player_name": "Juan Gaston", "position": "RT", "native_overall": 80},
        {"player_name": "JUAN GASTON", "position": "LT", "native_overall": 82},
    ]
    result = cfb27_enrichment.enrich_c3po_roster(roster, cards)
    row = result.players[0]
    assert row.state == "SELECT CARD"
    assert row.observation.name == "Juan Gaston"
    assert row.observation.displayed_ovr == 81
    assert len(row.choices) == 2
    page = render_c3po_roster(roster, result)
    assert "Juan Gaston" in page and "EA OVR 81" in page and "SELECT CARD" in page


def test_oop_and_ovr_mismatch_never_veto_exact_name():
    roster = C3PORoster((C3POPlayer("DEFENSE", "RRE 1", "Keyan Burnett", 83),), "p", "m")
    cards = [{"player_name": "Keyan Burnett", "position": "CB", "native_overall": 79, "program": "Test"}]
    result = cfb27_enrichment.enrich_c3po_roster(roster, cards)
    row = result.players[0]
    assert row.state == "LINKED"
    assert row.observation.slot == "RRE 1"
    assert row.observation.name == "Keyan Burnett"
    assert row.observation.displayed_ovr == 83
    assert row.card.native_position == "CB"
    assert row.card.card_ovr == 79
    page = render_c3po_roster(roster, result)
    assert "Keyan Burnett" in page and "EA OVR 83" in page
    assert "CFB27: CB · 79 OVR · Test" in page


def test_enrichment_source_has_no_legacy_identity_dependencies():
    source = inspect.getsource(cfb27_enrichment)
    forbidden = (
        "Candidate",
        "match_candidate",
        "c3po_tackle_resolver",
        "Tesseract",
        "team_import",
        "UNRESOLVED",
        "UNASSIGNED",
        "SequenceMatcher",
    )
    for token in forbidden:
        assert token not in source


def test_manual_card_detail_link_rejects_non_cfb_fan_source():
    roster = C3PORoster((C3POPlayer("OFFENSE", "RT 2", "Juan Gaston", 81),), "p", "m")
    cards = [
        {
            "player_name": "Juan Gaston",
            "position": "RT",
            "native_overall": 80,
            "program": "Phenoms",
            "source": {"ratings": "javascript:alert(1)"},
        },
        {
            "player_name": "Juan Gaston",
            "position": "RT",
            "native_overall": 75,
            "program": "Core Uncommon",
        },
    ]

    result = cfb27_enrichment.enrich_c3po_roster(roster, cards)
    page = render_c3po_roster(roster, result)

    assert "javascript:" not in page
    assert "VIEW CARD" not in page
