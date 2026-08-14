import json
from pathlib import Path

from operation_pancake.research.cfb27_op_x_006 import build_op_x_006

ROOT = Path(__file__).resolve().parents[1]
RESEARCH = ROOT / "data/research/cfb27_op_x_006"


def load(name):
    return json.loads((RESEARCH / f"{name}.json").read_text())


def test_ontology_and_compatibility_are_constraint_first():
    ontology = load("roster_decision_ontology")
    assert ontology["multi_role_allowed"] and "SPECIALIST" in ontology["roles"]
    duce = next(row for row in load("roster_compatibility_model") if row.get("user_case"))
    assert duce["normal_starter_status"] == "INELIGIBLE_BY_KNOWN_THEME_CONSTRAINT"
    assert "chemistry" in duce["unknown_fields"]


def test_duce_bnd_validation_never_sells_and_preserves_unknown_package():
    duce = load("mandatory_validation")["duce"]
    assert duce["raw_card_quality"] == "HIGH"
    assert duce["specialist_status"] == "CANDIDATE"
    assert duce["sell_recommendation"] is False
    assert duce["exact_package"] == "UNKNOWN"


def test_population_outputs_and_component_transparency():
    assert len(load("starter_value_profile")) == 435
    decisions = load("decision_engine_v1")
    assert len(decisions) == 435
    assert all("raw_card_quality" in row and "missing_information" in row for row in decisions)
    assert all(row["market_resource_value"] == "UNKNOWN" for row in decisions)


def test_moneyball_specialist_and_trap_validations_exist():
    validations = load("mandatory_validation")
    assert validations["center"] is not None
    assert validations["te"] is not None
    assert validations["high_ovr_trap"] is not None
    assert load("specialist_discovery")
    assert all(
        row["claim"] == "STATISTICAL_ROLE_PROFILE_ONLY" for row in load("above_ovr_moneyball_v2")
    )


def test_roster_schema_graph_and_strategy_preserve_unknowns():
    schema = load("roster_ingestion_schema")
    assert schema["partial_records_legal"] and len(schema["fields"]) == 19
    assert load("roster_constraint_graph")["unknown_nodes_allowed"]
    strategy = load("strategy_constraints")
    assert strategy["protected_rerollable"] == ["FS1", "MIKE1", "MIKE2"]


def test_all_gates_deterministic_and_no_integrity_violation():
    first = build_op_x_006(ROOT)
    assert first == build_op_x_006(ROOT)
    assert first["freeze"]["source_commit"] == "b74ecba"
    assert len(first["secondary_gates"]) >= 6
    assert all(value is False for value in first["validation"].values())
