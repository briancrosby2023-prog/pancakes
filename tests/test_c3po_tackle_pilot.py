from pathlib import Path

import pytest

from operation_pancake.c3po_tackle_resolver import (
    TackleResolutionStore,
    resolve_tackles,
)
from operation_pancake.c3po_vision import (
    PlayerObservation,
    TackleScreenObservation,
    TackleSlotObservation,
)


def card(cid, name, position, ovr, program="Phenoms", season="CFB27"):
    return {
        "card_id": cid,
        "player_name": name,
        "position": position,
        "native_overall": ovr,
        "program": program,
        "season": season,
    }


def observation(rt_name="Juan Gaston", rt_ovr=81):
    return TackleScreenObservation(
        view="OFFENSE",
        slots={
            "LT1": TackleSlotObservation(
                PlayerObservation(None, None),
                (PlayerObservation("Josh Petty", None),),
            ),
            "RT1": TackleSlotObservation(
                PlayerObservation("Cason Henry", 85),
                (PlayerObservation(rt_name, rt_ovr),),
            ),
        },
        provider="fixture",
        model="fixture",
    )


def tackle_cards():
    return [
        card("henry-85", "Cason Henry", "RT", 85),
        card("gaston-75", "Juan Gaston", "RT", 75, program="Core"),
        card("gaston-80", "Juan Gaston", "RT", 80),
        card("petty-80", "Josh Petty", "LT", 80),
    ]


@pytest.mark.parametrize(
    ("observed", "position", "canonical"),
    [
        ("John Petty", "LT", "Josh Petty"),
        ("Jason Henry", "RT", "Cason Henry"),
        ("Juan Easton", "RT", "Juan Gaston"),
    ],
)
def test_materially_different_names_fail_closed(observed, position, canonical):
    slots = {
        "LT1": TackleSlotObservation(
            PlayerObservation(observed if position == "LT" else None, 80), ()
        ),
        "RT1": TackleSlotObservation(
            PlayerObservation(observed if position == "RT" else None, 85), ()
        ),
    }
    translated = TackleScreenObservation("OFFENSE", slots, "fixture", "fixture")
    rows = resolve_tackles(translated, tackle_cards())
    row = next(row for row in rows if row.observed_player_name == observed)
    assert row.status == "UNRESOLVED"
    assert row.canonical_player_identity is None, (
        f"{observed} must not resolve to {canonical}"
    )
    assert row.canonical_card_id is None


def test_legitimate_real_observations_still_resolve():
    rows = resolve_tackles(observation(), tackle_cards())
    by_name = {row.observed_player_name: row for row in rows if row.observed_player_name}
    assert by_name["Cason Henry"].canonical_card_id == "henry-85"
    assert by_name["Cason Henry"].status == "MATCHED"
    assert by_name["Juan Gaston"].canonical_card_id == "gaston-80"
    assert by_name["Juan Gaston"].displayed_lineup_ovr == 81
    assert by_name["Juan Gaston"].native_card_ovr == 80
    assert by_name["Juan Gaston"].display_ovr_delta == 1
    assert by_name["Juan Gaston"].display_modifier_classification == "TEAM_LINEUP_MODIFIER"
    assert by_name["Josh Petty"].canonical_card_id == "petty-80"


def test_displayed_lineup_ovr_is_context_not_card_selection_or_identity_veto():
    rows = resolve_tackles(observation(rt_ovr=75), tackle_cards())
    gaston = next(row for row in rows if row.observed_player_name == "Juan Gaston")
    assert gaston.status == "MATCHED"
    assert gaston.canonical_player_identity == "Juan Gaston"
    assert gaston.canonical_card_id == "gaston-80"
    assert gaston.displayed_lineup_ovr == 75
    assert gaston.native_card_ovr == 80
    assert gaston.display_ovr_delta == -5


def test_large_displayed_ovr_mismatch_alone_cannot_reject_valid_identity():
    rows = resolve_tackles(observation(rt_ovr=99), tackle_cards())
    gaston = next(row for row in rows if row.observed_player_name == "Juan Gaston")
    assert gaston.status == "MATCHED"
    assert gaston.canonical_card_id == "gaston-80"
    assert gaston.native_card_ovr == 80
    assert gaston.displayed_lineup_ovr == 99
    assert gaston.display_ovr_delta == 19


def test_unrecognized_translated_name_fails_closed():
    rows = resolve_tackles(observation("Definitely Not A Tackle", 99), tackle_cards())
    bad = next(
        row for row in rows if row.observed_player_name == "Definitely Not A Tackle"
    )
    assert bad.status == "UNRESOLVED"
    assert bad.canonical_player_identity is None
    assert bad.canonical_card_id is None


def test_cfb25_and_cfb26_are_excluded_even_for_exact_name():
    rows = resolve_tackles(
        observation(),
        [
            card("old25", "Juan Gaston", "RT", 99, season="CFB25"),
            card("old26", "Juan Gaston", "RT", 98, season="CFB26"),
            *tackle_cards(),
        ],
    )
    gaston = next(row for row in rows if row.observed_player_name == "Juan Gaston")
    assert gaston.canonical_card_id == "gaston-80"
    assert gaston.native_card_ovr == 80


def test_observed_and_native_ovr_survive_persistence_restart(tmp_path: Path):
    rows = resolve_tackles(observation(), tackle_cards())
    path = tmp_path / "c3po-tackles.json"
    TackleResolutionStore(path).save(observation(), rows)
    restarted = TackleResolutionStore(path).load()
    gaston = next(
        row
        for row in restarted["resolutions"]
        if row["observed_player_name"] == "Juan Gaston"
    )
    assert gaston["displayed_lineup_ovr"] == 81
    assert gaston["native_card_ovr"] == 80
    assert gaston["display_ovr_delta"] == 1
    assert gaston["display_modifier_classification"] == "TEAM_LINEUP_MODIFIER"
    backup = restarted["translator_observation"]["slots"]["RT1"]["backups"][0]
    assert backup["displayed_ovr"] == 81
