from operation_pancake.c3po_team_setup import search_tackle_cards
from operation_pancake.team_import import Candidate
from operation_pancake.team_lineup_visual import render_lineup


def _cards():
    return [
        {"game": "CFB27", "position": "LT", "player_name": "Josh Petty", "native_overall": 80, "program": "Phenoms", "card_id": "josh-80"},
        {"game": "CFB27", "position": "LT", "player_name": "Josh Petty", "native_overall": 75, "program": "Core", "card_id": "josh-75"},
        {"game": "CFB27", "position": "RT", "player_name": "Josh Petty", "native_overall": 99, "program": "Wrong Position", "card_id": "wrong-pos"},
        {"game": "CFB26", "position": "LT", "player_name": "Josh Petty", "native_overall": 99, "program": "Wrong Season", "card_id": "wrong-season"},
        {"game": "CFB27", "position": "RT", "player_name": "Juan Gaston", "native_overall": 80, "program": "Phenoms", "card_id": "juan-80"},
    ]


def test_user_name_fallback_searches_cfb27_and_position_only():
    rows = search_tackle_cards("Josh Petty", "LT", _cards())
    assert [row["card_id"] for row in rows] == ["josh-80", "josh-75"]


def test_user_name_fallback_can_offer_safe_suggestions_without_auto_identity():
    rows = search_tackle_cards("Josh Pett", "LT", _cards())
    assert {row["player_name"] for row in rows} == {"Josh Petty"}
    assert all(row["position"] == "LT" for row in rows)


def test_unresolved_tackle_renders_simple_player_name_entry():
    candidate = Candidate("lt", "OFFENSE", "LT1", position="LT", match_status="UNMATCHED")
    page = render_lineup([candidate], {})
    assert 'name="player_name__lt"' in page
    assert "WHO IS THIS PLAYER?" in page


def test_non_tackle_does_not_get_name_fallback():
    candidate = Candidate("qb", "OFFENSE", "QB1", position="QB", match_status="UNMATCHED")
    page = render_lineup([candidate], {})
    assert 'name="player_name__qb"' not in page
