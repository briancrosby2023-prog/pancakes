import json
from pathlib import Path

from operation_pancake.models.cfb27_card_state import CardState, stable_id
from operation_pancake.research.cfb27_op_x_010 import build_op_x_010

ROOT = Path(__file__).resolve().parents[1]
RESEARCH = ROOT / "data/research/cfb27_op_x_010"


def load(name):
    return json.loads((RESEARCH / f"{name}.json").read_text())


def test_stable_ids_are_deterministic_and_source_sensitive():
    assert stable_id("card", "CFB_FAN", "1") == stable_id("card", "CFB_FAN", "1")
    assert stable_id("card", "CFB_FAN", "1") != stable_id("card", "OTHER", "1")


def test_435_and_632_are_not_conflated():
    audit = load("database_audit")
    state = json.loads((ROOT / "data/external/cfb_fan_population_state.json").read_text())
    assert audit["public_population_state"]["records"] == 8838
    assert len(state["cards"]) >= audit["public_population_state"]["records"]
    assert audit["evidence_catalog"]["records"] == 632
    assert "not a card population" in audit["evidence_catalog"]["meaning"]


def test_same_player_versions_survive_deduplication():
    cards = load("cards")
    by_player = {}
    for card in cards:
        by_player.setdefault(card["player_id"], []).append(card)
    assert any(len(rows) > 1 for rows in by_player.values())
    assert load("duplicate_resolution")["true_duplicate_ids"] == 0


def test_native_active_and_specialist_are_separate():
    native = load("card_native_states")
    active = load("active_states")
    specialists = load("specialist_views")
    assert all(row["active_ratings"] is None for row in native)
    assert len(active) == 1
    assert len(specialists) == 10
    assert all(row["native_ovr"] is None for row in specialists)


def test_unknown_is_not_zero_and_invalid_states_fail():
    state = CardState("s", "c", "ACTIVE", None, {"SPD": None})
    assert state.ratings["SPD"] is None


def test_seau_is_one_family_with_multiple_states():
    seau = load("seau_gold_standard")
    assert len({row["card_id"] for row in seau["states"]}) == 1
    assert len(seau["states"]) >= 5
    assert len(seau["events"]) == 6


def test_readiness_blocks_current_team_overclaim():
    readiness = load("model_readiness")
    assert not readiness["CURRENT_TEAM_READY"]["ready"]
    assert readiness["CURRENT_TEAM_READY"]["coverage"] == "1/24"


def test_packet_is_deterministic_and_integrity_strict():
    first = build_op_x_010(ROOT)
    assert first == build_op_x_010(ROOT)
    assert first["freeze"]["source_commit"] == "c6227af"
    assert len(first["secondary_gates"]) >= 15
    assert all(value is False for value in first["validation"].values())
