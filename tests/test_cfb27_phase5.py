import json
from pathlib import Path

import pytest

from operation_pancake.research.cfb27_phase5 import (
    build_phase5,
    normalize_thresholds,
    threshold_proximity,
)

ROOT = Path(__file__).resolve().parents[1]
RESEARCH = ROOT / "data/research/cfb27_inheritance_phase5"


def _load(name: str):
    return json.loads((RESEARCH / name).read_text(encoding="utf-8"))


def test_phase5_freezes_phase4_population_and_inputs() -> None:
    frozen = _load("phase5_frozen_snapshot.json")
    assert frozen["source_commit"] == "49acdda"
    assert frozen["population_n"] == 8838
    assert frozen["no_retrospective_leakage"] is True
    assert all(len(value) == 64 for value in frozen["input_sha256"].values())


def test_ability_progression_evolution_preserves_complete_raw_definitions() -> None:
    raw = _load("ability_progression_tunable_raw.json")
    assert list(raw) == ["C27", "M19", "M20", "M21", "M22", "M23", "M24", "M25", "M26", "M27"]
    assert [field["name"] for field in raw["M19"]["fields"]] == [
        "Ability",
        "AbilityLifetimeCapsRef",
        "ProgressionChance",
        "ProgressionSoftCap",
        "RegressionChance",
        "RegressionSoftCap",
    ]
    assert [field["name"] for field in raw["C27"]["fields"]] == [
        "Ability",
        "HeightModifierSpline",
        "UpgradeCostSpline",
        "WeightModifierSpline",
    ]
    evolution = _load("ability_progression_field_evolution.json")
    c27 = {row["field"]: row["status"] for row in evolution if row["game"] == "C27"}
    assert c27["ProgressionChance"] == "REMOVED"
    assert c27["UpgradeCostSpline"] == "ADDED"


def test_schema_graph_edges_require_explicit_field_types() -> None:
    graph = _load("related_table_graph.json")
    assert graph["edges"]
    assert all(edge["evidence"] == "EXPLICIT_FIELD_TYPE" for edge in graph["edges"])
    assert all(edge["confidence"] == "VERIFIED" for edge in graph["edges"])
    assert graph["unsupported_name_similarity_edges"] == []


def test_threshold_ingestion_expands_tiers_without_guessing() -> None:
    snapshot = json.loads((ROOT / "data/external/cfb27_ability_thresholds.json").read_text())
    records = normalize_thresholds(snapshot)
    assert len(snapshot["records"]) == 170
    assert len(records) == 732
    assert all(record["ovr_requirement"] is None for record in records)
    assert all(record["source_class"] == "STRUCTURED_SECONDARY" for record in records)
    assert all(record["source_id"] == "SRC-CFB27-ABILITY-001" for record in records)
    malformed = {**snapshot, "records": [{**snapshot["records"][0], "Bronze": "83"}]}
    with pytest.raises(ValueError, match="non-integer"):
        normalize_thresholds(malformed)


def test_threshold_proximity_does_not_claim_equip_eligibility() -> None:
    records = [
        {
            "position": "TE",
            "archetype": "Vertical Threat",
            "ability": "Example",
            "tier": "BRONZE",
            "attribute": "ACC",
            "required_rating": 90,
        }
    ]
    cards = [
        {
            "external_card_id": "a",
            "player_name": "A",
            "position": "TE",
            "archetype": "Vertical Threat",
            "displayed_ratings": {"ACC": 89},
        },
        {
            "external_card_id": "b",
            "player_name": "B",
            "position": "TE",
            "archetype": "Vertical Threat",
            "displayed_ratings": {"ACC": 90},
        },
    ]
    result = threshold_proximity(cards, records)
    assert result["counts"] == {"1_BELOW": 1, "AT_THRESHOLD": 1}
    assert not any(row["equip_eligibility_claimed"] for row in result["observations"])


def test_progression_crosswalk_preserves_missing_evidence() -> None:
    progression = _load("progression_attribute_crosswalk.json")
    assert len(progression["confirmed_chains"]) == 12
    assert progression["core_specialization_status"].startswith("INSUFFICIENT")
    assert all(
        row["missing_observation_is_zero"] is False for row in progression["candidate_observations"]
    )


def test_capability_chronology_is_deterministic_and_sorted() -> None:
    chronology = _load("capability_chronology.json")["first_observed_threshold_access"]
    assert chronology == sorted(
        chronology,
        key=lambda row: (
            row["position"],
            row["archetype"],
            row["ability"],
            row["tier"],
            row["first_release_date"],
            row["card_id"],
        ),
    )
    assert all(row["first_release_date"].startswith("2026-") for row in chronology)


def test_replacement_pressure_v2_does_not_overstate_partial_capability_data() -> None:
    pressure = _load("replacement_pressure_v2.json")
    assert pressure
    assert all(row["pressure_v2"] in {"ELEVATED", "NORMAL", "LOWER"} for row in pressure.values())
    assert all(
        row["change_from_phase4"] == "UNCHANGED_INSUFFICIENT_COMPLETE_THRESHOLD_COVERAGE"
        for row in pressure.values()
    )


def test_gm_output_covers_population_without_claiming_eligibility() -> None:
    evaluator = _load("pc_evaluator_phase5.json")
    assert len(evaluator) == 8838
    assert len({row["card_id"] for row in evaluator}) == 8838
    assert all(row["ability_eligibility_confirmed"] is False for row in evaluator)
    assert len(_load("chatgpt_research_queue.json")) == 20


def test_formula_status_preserves_phase4_rejections() -> None:
    status = _load("formula_research_status.json")
    assert status["Center"] == "HISTORICAL_NUMERIC_INHERITANCE_REJECTED"
    assert status["QB"] == "NO_HISTORICAL_HYBRID_PRODUCTION_MODEL"
    assert "GRITTY_ARCHITECTURE_ONLY" in status["TE"]
    assert _load("prospective_validation_ledger.json")["new_cards"] == 0


def test_complete_phase5_analysis_is_deterministic() -> None:
    first = build_phase5(ROOT)
    second = build_phase5(ROOT)
    assert first == second
    assert first["data_validation"] == {
        "access_bypass": False,
        "canonical_modified": False,
        "guessed_values": False,
        "leakage": False,
        "threshold_rows_cross_source_validated": False,
        "unsupported_schema_inference": False,
    }
