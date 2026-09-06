from operation_pancake.c3po_team import (
    TeamPlayerObservation,
    TeamScreenObservation,
    candidates_from_observation,
)
from operation_pancake.team_lineup_visual import render_lineup


def _card(card_id, name, position, ovr, program="Phenoms"):
    return {
        "card_id": card_id,
        "player_name": name,
        "position": position,
        "native_overall": ovr,
        "program": program,
        "game": "CFB27",
    }


def _observation(slot, name, ovr, backups=()):
    return TeamScreenObservation(
        "OFFENSE",
        (TeamPlayerObservation(slot, name, ovr, backups),),
        "test-c3po",
        "test-model",
    )


def test_unique_exact_name_links_without_ovr_or_position_veto():
    result = candidates_from_observation(
        _observation("LT1", "Juan Gaston", 81),
        [_card("juan-80", "Juan Gaston", "RT", 80)],
        "shot-1",
    )[0]
    assert result.player_name == "Juan Gaston"
    assert result.displayed_ovr == 81
    assert result.match_status == "LINKED"
    assert result.canonical_card_id == "juan-80"
    assert result.match_diagnostics["enrichment"]["native_position"] == "RT"
    assert result.match_diagnostics["enrichment"]["native_card_ovr"] == 80


def test_observed_player_survives_missing_canonical_data():
    result = candidates_from_observation(
        _observation("LG1", "Thomas Shrader", 85), [], "shot-1"
    )[0]
    assert result.player_name == "Thomas Shrader"
    assert result.displayed_ovr == 85
    assert result.match_status == "OBSERVED"
    assert result.canonical_card_id is None
    rendered = render_lineup([result], {})
    assert "Thomas Shrader" in rendered
    assert "CFB27 DATA NOT LINKED" in rendered
    assert "WHO IS THIS PLAYER?" not in rendered


def test_real_observed_names_are_never_erased_by_enrichment_failure():
    players = (
        TeamPlayerObservation("LT1", "Josh Petty", None),
        TeamPlayerObservation("LG1", "Thomas Shrader", 85),
        TeamPlayerObservation("RG1", "Zach Rice", 82),
        TeamPlayerObservation("TE1", "Keyan Burnett", 83),
    )
    observation = TeamScreenObservation("OFFENSE", players, "test-c3po", "test-model")
    results = candidates_from_observation(observation, [], "shot-1")
    assert [row.player_name for row in results] == [
        "Josh Petty",
        "Thomas Shrader",
        "Zach Rice",
        "Keyan Burnett",
    ]
    assert all(row.match_status == "OBSERVED" for row in results)


def test_backup_identity_survives_oop_and_missing_enrichment():
    backups = (
        {"player_name": "Juan Gaston", "displayed_ovr": 81},
        {"player_name": "Martellus Bennett", "displayed_ovr": None},
    )
    result = candidates_from_observation(
        _observation("RT1", "Cason Henry", 86, backups),
        [_card("cason", "Cason Henry", "RT", 85)],
        "shot-1",
    )[0]
    assert result.backups[0]["player_name"] == "Juan Gaston"
    assert result.backups[0]["displayed_ovr"] == 81
    assert result.backups[0]["enrichment_status"] == "not-linked"
    assert result.backups[1]["player_name"] == "Martellus Bennett"


def test_multiple_exact_cards_make_card_ambiguous_not_player_unresolved():
    cards = [
        _card("one", "Josh Petty", "LT", 80),
        _card("two", "Josh Petty", "LT", 82),
    ]
    result = candidates_from_observation(
        _observation("LT1", "Josh Petty", 82), cards, "shot-1"
    )[0]
    assert result.player_name == "Josh Petty"
    assert result.match_status == "AMBIGUOUS_CARD"
    assert result.canonical_card_id is None
    rendered = render_lineup([result], {})
    assert "Josh Petty" in rendered
    assert "CFB27 CARD: SELECT CARD" in rendered


def test_missing_usable_name_is_the_only_unresolved_observation():
    result = candidates_from_observation(
        _observation("LT1", None, 80), [], "shot-1"
    )[0]
    assert result.player_name is None
    assert result.match_status == "UNRESOLVED"


def test_false_positive_names_are_preserved_not_silently_reinterpreted():
    cards = [
        _card("josh-80", "Josh Petty", "LT", 80),
        _card("cason-85", "Cason Henry", "RT", 85),
        _card("juan-80", "Juan Gaston", "RT", 80),
    ]
    players = (
        TeamPlayerObservation("LT1", "John Petty", 80),
        TeamPlayerObservation("LG1", "Jason Henry", 85),
        TeamPlayerObservation("RT1", "Juan Easton", 81),
    )
    observation = TeamScreenObservation("OFFENSE", players, "test-c3po", "test-model")
    results = candidates_from_observation(observation, cards, "shot-1")
    assert [row.player_name for row in results] == ["John Petty", "Jason Henry", "Juan Easton"]
    assert all(row.match_status == "OBSERVED" for row in results)
    assert all(row.canonical_card_id is None for row in results)
