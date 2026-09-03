from operation_pancake.c3po_team import (
    TeamPlayerObservation,
    TeamScreenObservation,
    candidates_from_observation,
)


def _card(card_id, name, position, ovr, program="Phenoms"):
    return {
        "card_id": card_id,
        "player_name": name,
        "position": position,
        "native_overall": ovr,
        "program": program,
        "game": "CFB27",
    }


def test_c3po_exact_name_keeps_displayed_and_canonical_ovr_separate():
    observation = TeamScreenObservation(
        "OFFENSE",
        (TeamPlayerObservation("RT1", "Juan Gaston", 81),),
        "test-c3po",
        "test-model",
    )
    result = candidates_from_observation(
        observation, [_card("juan-80", "Juan Gaston", "RT", 80)], "shot-1"
    )[0]
    assert result.match_status == "MATCHED"
    assert result.displayed_ovr == 81
    assert result.canonical_card_id == "juan-80"
    assert result.match_diagnostics["canonical"]["native_card_ovr"] == 80
    assert result.match_diagnostics["canonical"]["display_ovr_delta"] == 1


def test_c3po_exact_name_allows_out_of_position_lineup_slot():
    observation = TeamScreenObservation(
        "OFFENSE",
        (TeamPlayerObservation("LT1", "Cason Henry", 86),),
        "test-c3po",
        "test-model",
    )
    result = candidates_from_observation(
        observation, [_card("cason-85", "Cason Henry", "RT", 85)], "shot-1"
    )[0]
    assert result.match_status == "MATCHED"
    assert result.slot == "LT1"
    assert result.match_diagnostics["canonical"]["native_position"] == "RT"


def test_c3po_does_not_approximate_wrong_names():
    cards = [
        _card("josh-80", "Josh Petty", "LT", 80),
        _card("cason-85", "Cason Henry", "RT", 85),
        _card("juan-80", "Juan Gaston", "RT", 80),
    ]
    observation = TeamScreenObservation(
        "OFFENSE",
        (
            TeamPlayerObservation("LT1", "John Petty", 80),
            TeamPlayerObservation("LG1", "Jason Henry", 85),
            TeamPlayerObservation("RT1", "Juan Easton", 81),
        ),
        "test-c3po",
        "test-model",
    )
    results = candidates_from_observation(observation, cards, "shot-1")
    assert [row.match_status for row in results] == ["UNMATCHED", "UNMATCHED", "UNMATCHED"]
    assert all(row.canonical_card_id is None for row in results)
