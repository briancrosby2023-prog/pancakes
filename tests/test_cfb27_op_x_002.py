import json
from pathlib import Path

from operation_pancake.research.cfb27_op_x_002 import build_op_x_002

ROOT = Path(__file__).resolve().parents[1]
RESEARCH = ROOT / "data/research/cfb27_op_x_002"


def _load(name):
    return json.loads((RESEARCH / f"{name}.json").read_text(encoding="utf-8"))


def test_frozen_inputs_and_validation_boundaries() -> None:
    assert _load("freeze")["source_commit"] == "cc47415"
    assert _load("freeze")["population_n"] == 435
    assert _load("validation") == {
        "access_bypass": False,
        "canonical_changes": False,
        "conflicts_preserved": True,
        "gameplay_claims": False,
        "guessed_values": False,
        "market_claims": False,
        "unknown_as_zero": False,
    }


def test_te_gate_has_candidates_pairs_and_counterevidence() -> None:
    te = _load("te_moneyball")
    assert te["population"] == 23
    assert len(te["candidates"]) == 10
    assert len(te["matched_pairs"]) >= 5
    assert te["counterevidence"]["market_value_available"] is False
    assert all(row["gameplay_value_claimed"] is False for row in te["candidates"])


def test_cb_gate_has_human_readable_controlled_test_set() -> None:
    cb = _load("cb_technical_value")
    assert cb["population"] == 23
    assert len(cb["matched_comparisons"]) >= 10
    assert len(cb["athletic_floor_test_set"]) == 10
    assert cb["height_status"] == "UNAVAILABLE_NOT_ZERO"
    assert all(
        row["left"]["player"] and row["right"]["player"] for row in cb["matched_comparisons"]
    )


def test_mike_seau_matrix_is_complete_and_not_prescriptive() -> None:
    result = _load("mike_seau")
    assert result["population"] == 23
    assert len(result["seau_upgrade_decision_matrix"]) == 2
    assert all(len(row["upgrade_matrix"]) == 36 for row in result["seau_upgrade_decision_matrix"])
    assert all(
        row["gameplay_path_recommended"] is False for row in result["seau_upgrade_decision_matrix"]
    )


def test_coherence_v2_exposes_components_without_composite() -> None:
    rows = _load("ability_coherence_v2")
    assert rows
    required = {
        "ability_count",
        "ability_threshold_leverage",
        "multi_unlock_attribute_leverage",
        "role_alignment",
        "archetype_alignment",
        "redundancy",
        "diversity",
    }
    assert all(required <= row.keys() and row["opaque_composite"] is None for row in rows)


def test_cost_and_five_secondary_gates_are_reproducible() -> None:
    cost = _load("attribute_cost_analysis")
    assert set(cost) == {"ACC", "STR", "BSH"}
    assert cost["BSH"]["EDGE"]["count"] == 0
    secondary = _load("secondary_gates")
    assert set(secondary) == {
        "experiment_generator",
        "gameplay_result_schema",
        "market_join_schema",
        "release_architecture",
        "special_card_design",
    }
    assert secondary["gameplay_result_schema"]["records"] == []
    assert secondary["market_join_schema"]["observations"] == []
    assert build_op_x_002(ROOT) == build_op_x_002(ROOT)
