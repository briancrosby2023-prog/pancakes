import pytest

from operation_pancake.c3po_tackle_resolver import resolve_player
from operation_pancake.c3po_team_setup import (
    apply_user_tackle_name,
    search_tackle_cards,
    select_user_tackle_card,
)
from operation_pancake.c3po_vision import PlayerObservation
from operation_pancake.team_import import Candidate, TeamImportState, TeamImportStore
from operation_pancake.team_lineup_visual import render_lineup


def _cards():
    return [
        {
            "game": "CFB27",
            "position": "LT",
            "player_name": "Josh Petty",
            "native_overall": 80,
            "program": "Phenoms",
            "card_id": "josh-80",
        },
        {
            "game": "CFB27",
            "position": "LT",
            "player_name": "Josh Petty",
            "native_overall": 75,
            "program": "Core",
            "card_id": "josh-75",
        },
        {
            "game": "CFB27",
            "position": "RT",
            "player_name": "Josh Petty",
            "native_overall": 99,
            "program": "Wrong Position",
            "card_id": "wrong-pos",
        },
        {
            "game": "CFB26",
            "position": "LT",
            "player_name": "Josh Petty",
            "native_overall": 99,
            "program": "Wrong Season",
            "card_id": "wrong-season",
        },
        {
            "game": "CFB27",
            "position": "RT",
            "player_name": "Juan Gaston",
            "native_overall": 80,
            "program": "Phenoms",
            "card_id": "juan-80",
        },
    ]


def _candidate(candidate_id: str, slot: str, position: str) -> Candidate:
    return Candidate(
        candidate_id,
        "OFFENSE",
        slot,
        position=position,
        match_status="UNMATCHED",
    )


def test_clean_exact_c3po_name_beats_nearby_identity_without_ovr_help():
    crowded = _cards() + [
        {
            "game": "CFB27",
            "position": "LT",
            "player_name": "Josh Pettyy",
            "native_overall": 99,
            "program": "Distractor",
            "card_id": "distractor",
        }
    ]
    result = resolve_player(
        PlayerObservation("Josh Petty", 99),
        "LT",
        crowded,
        "LT1",
        0,
    )
    assert result.status == "MATCHED"
    assert result.canonical_player_identity == "Josh Petty"
    assert result.canonical_card_id == "josh-80"


def test_user_name_fallback_is_name_first_across_native_positions():
    rows = search_tackle_cards("Josh Petty", "LT", _cards())
    assert [row["card_id"] for row in rows] == ["wrong-pos", "josh-80", "josh-75"]
    assert {row["position"] for row in rows} == {"LT", "RT"}


def test_user_name_fallback_can_offer_safe_suggestions_without_auto_identity():
    rows = search_tackle_cards("Josh Pett", "LT", _cards())
    assert {row["player_name"] for row in rows} == {"Josh Petty"}


@pytest.mark.parametrize("typed", ["John Petty", "Jason Henry", "Juan Easton"])
def test_user_name_fallback_rejects_unsafe_near_names(typed):
    assert search_tackle_cards(typed, "LT", _cards()) == []


def test_unresolved_tackle_renders_simple_player_name_entry():
    candidate = _candidate("lt", "LT1", "LT")
    page = render_lineup([candidate], {})
    assert 'name="player_name__lt"' in page
    assert "WHO IS THIS PLAYER?" in page
    assert 'formaction="/team/tackle-search"' in page


def test_non_tackle_does_not_get_name_fallback():
    candidate = _candidate("qb", "QB1", "QB")
    page = render_lineup([candidate], {})
    assert 'name="player_name__qb"' not in page


def test_user_exact_name_with_multiple_variants_requires_explicit_card_selection():
    candidate = _candidate("lt", "LT1", "LT")
    outcome = apply_user_tackle_name(candidate, "Josh Petty", _cards())
    assert outcome == "CHOICE_REQUIRED"
    assert candidate.canonical_card_id is None
    fallback = candidate.match_diagnostics["user_name_fallback"]
    assert fallback["query"] == "Josh Petty"
    assert fallback["result_card_ids"] == ["wrong-pos", "josh-80", "josh-75"]


def test_user_exact_name_with_one_oop_card_can_resolve_directly():
    candidate = _candidate("lt", "LT1", "LT")
    outcome = apply_user_tackle_name(candidate, "Juan Gaston", _cards())
    assert outcome == "MATCHED"
    assert candidate.player_name == "Juan Gaston"
    assert candidate.canonical_card_id == "juan-80"
    assert candidate.position == "LT"


def test_user_selected_oop_variant_persists_through_team_import_store(tmp_path):
    candidate = _candidate("lt", "LT1", "LT")
    apply_user_tackle_name(candidate, "Josh Petty", _cards())
    assert select_user_tackle_card(candidate, "wrong-pos", _cards())
    path = tmp_path / "team-import.json"
    store = TeamImportStore(path)
    store.save(TeamImportState(candidates=[candidate]))
    restarted = TeamImportStore(path).load().candidates[0]
    assert restarted.player_name == "Josh Petty"
    assert restarted.position == "LT"
    assert restarted.canonical_card_id == "wrong-pos"
    assert restarted.match_status == "MATCHED"
    assert "user-confirmed:cfb27-name-search" in restarted.provenance


def test_choice_required_renders_all_safe_cfb27_variant_options():
    candidate = _candidate("lt", "LT1", "LT")
    apply_user_tackle_name(candidate, "Josh Petty", _cards())
    cards_by_id = {row["card_id"]: row for row in _cards()}
    page = render_lineup([candidate], cards_by_id)
    assert 'value="josh-80"' in page
    assert 'value="josh-75"' in page
    assert 'value="wrong-pos"' in page
    assert "wrong-season" not in page
