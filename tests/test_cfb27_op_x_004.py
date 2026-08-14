import json
from pathlib import Path

from operation_pancake.research.cfb27_op_x_004 import build_op_x_004, seau_81

ROOT = Path(__file__).resolve().parents[1]
RESEARCH = ROOT / "data/research/cfb27_op_x_004"


def load(name):
    return json.loads((RESEARCH / f"{name}.json").read_text(encoding="utf-8"))


def test_seau_primary_evidence_separates_systems_and_derives_start_exactly():
    evidence = load("seau_primary_evidence")
    assert evidence["premade_and_evo_merged"] is False
    assert [row["overall"] for row in evidence["states"]] == [81, 84, 86, 87, 86]
    assert seau_81()["SPD"] == 79 and seau_81()["ACC"] == 82 and seau_81()["CTH"] == 70
    assert evidence["development_pool"]["selection_probabilities"] == "UNKNOWN"


def test_seau_validation_preserves_both_success_and_uncertainty():
    result = load("seau_81_vs_84")
    assert result["classification"] == "INSUFFICIENT_EVIDENCE"
    assert result["actual_81_to_86"]["specialization_points"] == 16
    assert result["actual_81_to_86"]["wasted_for_target_role_points"] == 14
    assert result["counterfactual_84_range"]["exact_final_ratings"] is None
    assert result["counterfactual_84_range"]["synthetic_vector"] is False


def test_foundation_deficit_and_concentration_are_transparent():
    foundation = load("foundation_completeness")
    assert (
        foundation["84_PREMADE"]["role_foundation"] > foundation["81_EVO_START"]["role_foundation"]
    )
    deficit = load("starting_deficit_vector")
    assert deficit["81"]["total"] > deficit["84"]["total"]
    hypothesis = load("broad_foundation_custom_specialization")
    assert hypothesis["premade"]["classification"] == "BROAD_DEVELOPMENT"
    assert hypothesis["evo"]["hhi"] > hypothesis["premade"]["hhi"]


def test_master_scout_and_pc_output_preserve_unknowns():
    master = load("upgrade_progression_master_v1")
    assert master["chain_count"] >= 14 and master["no_synthetic_vectors"] is True
    scout = load("prospective_upgrade_scout")
    pc = load("pc_upgrade_decision_output")
    assert len(scout) == len(pc) == 435
    assert all(row["remaining_opportunities"] is None for row in pc)
    assert all(
        row["recommendation"] in {"GOOD_CARD_NOW", "INSUFFICIENT_UPGRADE_INFORMATION"} for row in pc
    )


def test_historical_sample_and_market_semantics_are_conservative():
    secondary = load("secondary_gates")
    acquisition = secondary["historical_acquisition"]
    assert len(acquisition["CFB25"]) == len(acquisition["CFB26"]) == 3
    assert acquisition["access_bypass"] is False
    assert secondary["market_collection"]["sale_claimed"] is False
    assert secondary["resource_economics"]["upgrade_resource_costs"] is None


def test_all_seventeen_gate_artifacts_are_deterministic_and_validated():
    first = build_op_x_004(ROOT)
    second = build_op_x_004(ROOT)
    assert first == second
    assert first["freeze"]["source_commit"] == "894665b"
    assert len(first["upgrade_failure_taxonomy"]) == 17
    assert first["optimal_starting_ovr"]["structurally_can_recommend_higher"] is True
    assert all(value is False for value in first["validation"].values())
