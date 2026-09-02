from pathlib import Path

from operation_pancake.c3po_tackle_resolver import TackleResolutionStore, resolve_tackles
from operation_pancake.c3po_vision import PlayerObservation, TackleScreenObservation, TackleSlotObservation


def card(cid, name, position, ovr, program="Phenoms", season="CFB27"):
    return {"card_id": cid, "player_name": name, "position": position, "native_overall": ovr, "program": program, "season": season}


def observation(rt_name="Juan Gaston", rt_ovr=81):
    return TackleScreenObservation(
        view="OFFENSE",
        slots={
            "LT1": TackleSlotObservation(PlayerObservation(None, None), (PlayerObservation("Josh Petty", None),)),
            "RT1": TackleSlotObservation(PlayerObservation("Cason Henry", 85), (PlayerObservation(rt_name, rt_ovr),)),
        },
        provider="fixture",
        model="fixture",
    )


def test_displayed_lineup_ovr_is_not_native_card_identity_key():
    cards = [
        card("henry-85", "Cason Henry", "RT", 85),
        card("gaston-80", "Juan Gaston", "RT", 80),
        card("petty-80", "Josh Petty", "LT", 80),
    ]
    rows = resolve_tackles(observation(), cards)
    gaston = next(row for row in rows if row.observed_player_name == "Juan Gaston")
    assert gaston.status == "MATCHED"
    assert gaston.canonical_player_identity == "Juan Gaston"
    assert gaston.canonical_card_id == "gaston-80"
    assert gaston.displayed_lineup_ovr == 81
    assert gaston.native_card_ovr == 80


def test_unrecognized_translated_name_fails_closed():
    rows = resolve_tackles(observation("Definitely Not A Tackle", 99), [card("gaston-80", "Juan Gaston", "RT", 80), card("petty-80", "Josh Petty", "LT", 80)])
    bad = next(row for row in rows if row.observed_player_name == "Definitely Not A Tackle")
    assert bad.status == "UNRESOLVED"
    assert bad.canonical_player_identity is None
    assert bad.canonical_card_id is None


def test_cfb25_and_cfb26_are_excluded_even_for_exact_name():
    rows = resolve_tackles(
        observation(),
        [
            card("old25", "Juan Gaston", "RT", 81, season="CFB25"),
            card("old26", "Juan Gaston", "RT", 81, season="CFB26"),
            card("gaston-80", "Juan Gaston", "RT", 80, season="CFB27"),
            card("petty-80", "Josh Petty", "LT", 80),
        ],
    )
    gaston = next(row for row in rows if row.observed_player_name == "Juan Gaston")
    assert gaston.canonical_card_id == "gaston-80"
    assert gaston.native_card_ovr == 80


def test_observed_and_native_ovr_survive_persistence_restart(tmp_path: Path):
    rows = resolve_tackles(observation(), [card("gaston-80", "Juan Gaston", "RT", 80), card("henry-85", "Cason Henry", "RT", 85), card("petty-80", "Josh Petty", "LT", 80)])
    path = tmp_path / "c3po-tackles.json"
    TackleResolutionStore(path).save(observation(), rows)
    restarted = TackleResolutionStore(path).load()
    gaston = next(row for row in restarted["resolutions"] if row["observed_player_name"] == "Juan Gaston")
    assert gaston["displayed_lineup_ovr"] == 81
    assert gaston["native_card_ovr"] == 80
    assert restarted["translator_observation"]["slots"]["RT1"]["backups"][0]["displayed_ovr"] == 81
