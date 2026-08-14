import json
from pathlib import Path

from operation_pancake.research.cfb27_op_x_005 import (
    build_op_x_005,
    parse_historical_listing,
)

ROOT = Path(__file__).resolve().parents[1]
RESEARCH = ROOT / "data/research/cfb27_op_x_005"


def load(name):
    return json.loads((RESEARCH / f"{name}.json").read_text())


def test_event_master_separates_systems():
    rows = load("dynamic_upgrade_event_master_v1")
    systems = {r["attribute_class"] for r in rows}
    assert {
        "DYNAMIC_UPGRADE",
        "PREMADE_CARD_PROGRESSION",
        "SATURDAY_RESET",
        "OTHER/UNKNOWN",
    } <= systems
    assert sum(r["attribute_class"] == "DYNAMIC_UPGRADE" for r in rows) == 15
    assert all(
        r["pre_upgrade_value"] is not None
        for r in rows
        if r["attribute_class"] == "DYNAMIC_UPGRADE"
    )


def test_selection_and_primary_secondary_do_not_claim_probabilities():
    freq = load("attribute_selection_frequency")
    assert freq["events"] == 4
    assert all(r["probability_claimed"] is False for r in freq["records"])
    compare = load("primary_vs_secondary")
    assert (
        compare["classification"] == "PRIMARY_ADVANTAGE_PARTIAL"
        and compare["probability_assumed"] is False
    )


def test_ev_counterfactual_and_caps_are_exploratory():
    ev = load("expected_opportunity_value")
    assert (
        ev["total_point_ev"] == 14.75
        and ev["confidence"] == "EXPLORATORY"
        and ev["stationarity_assumed"] is False
    )
    cf = load("seau_counterfactual_v2")
    assert (
        cf["scenario_count"] == 16
        and cf["synthetic_vector"] is False
        and cf["probability_claimed"] is False
    )
    assert load("cap_interaction_model")["mechanics_inferred"] is False


def test_confidence_pc_and_collection_priorities_guard_speculation():
    confidence = load("upgrade_recommendation_confidence")
    assert (
        confidence["current_dynamic_model"] == "EXPLORATORY"
        and confidence["fact_presentation_guard"] is True
    )
    pc = load("pc_development_intelligence_v2")
    assert len(pc) == 435 and {r["confidence"] for r in pc} <= {"EXPLORATORY", "DO_NOT_MODEL"}
    assert len(load("upgrade_data_collection_priority")["ranked_fields"]) >= 8


def test_historical_parser_and_engine_are_safe_and_resumable():
    html = '<a href="/players/1-test/26-123/"><span>OVR</span> 88 Test</a>'
    assert parse_historical_listing(html)[0]["card_id"] == "26-123"
    engine = load("historical_acquisition_engine")
    assert (
        engine["minimum_delay_seconds"] == 2
        and engine["default_max_pages"] == 1
        and engine["full_population_acquired"] is False
    )


def test_all_gates_are_deterministic_and_validation_is_strict():
    first = build_op_x_005(ROOT)
    assert first == build_op_x_005(ROOT)
    assert first["freeze"]["source_commit"] == "c6d3ff6"
    assert len(first["secondary_gates"]) >= 4
    assert all(value is False for value in first["validation"].values())
