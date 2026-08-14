import json
from pathlib import Path

import pytest

from operation_pancake.research.cfb27_phase6_10 import (
    build_phase6_10,
    grouped_thresholds,
)

ROOT = Path(__file__).resolve().parents[1]
RESEARCH = ROOT / "data/research/cfb27_ability_phase6_10"


def _load(name: str):
    return json.loads((RESEARCH / name).read_text(encoding="utf-8"))


def test_complete_source_and_catalog_coverage() -> None:
    source = json.loads((ROOT / "data/external/cfb27_ability_thresholds.json").read_text())
    catalog = _load("ability_catalog.json")
    assert len(source["records"]) == 170
    assert catalog["source_row_coverage"] == 1.0
    assert catalog["tier_requirement_groups"] == 680
    assert catalog["attribute_constraints"] == 732
    assert catalog["position_count"] == 8
    assert catalog["position_archetype_count"] == 34
    assert catalog["ability_count"] == 57


def test_grouped_thresholds_preserve_multi_attribute_requirements() -> None:
    source = json.loads((ROOT / "data/external/cfb27_ability_thresholds.json").read_text())
    groups = grouped_thresholds(source)
    assert any(len(group["requirements"]) == 2 for group in groups)
    assert all(group["validation"] == "SINGLE_STRUCTURED_SOURCE" for group in groups)
    assert all(group["ovr_requirement"] is None for group in groups)
    malformed = {**source, "records": [{**source["records"][0], "Bronze": "90"}]}
    with pytest.raises(ValueError, match="non-integer"):
        grouped_thresholds(malformed)


def test_validation_does_not_promote_catalog_cross_checks_to_numeric_confirmation() -> None:
    validation = _load("cross_source_validation.json")
    assert validation["counts"] == {
        "COMMUNITY_ONLY": 0,
        "CONFLICT": 2,
        "MULTI_SOURCE_CONFIRMED": 0,
        "PRIMARY_CONFIRMED": 0,
        "SINGLE_STRUCTURED_SOURCE": 678,
        "UNRESOLVED": 0,
    }
    assert len(validation["conflicts"]) == 2
    assert validation["domain_interchangeability_proven"] is False
    assert validation["cut_equip_availability_claimed_from_cfb_labs"] is False
    discovery = _load("ability_source_discovery.json")
    assert discovery["numeric_cross_source_validation_available"] is False
    assert discovery["access_bypass"] is False


def test_spline_graph_is_structural_and_rows_remain_unavailable() -> None:
    splines = _load("cfb27_spline_analysis.json")
    assert {edge["field"] for edge in splines["direct_reference_edges"]} == {
        "HeightModifierSpline",
        "UpgradeCostSpline",
        "WeightModifierSpline",
    }
    assert [field["name"] for field in splines["spline_definition"]["fields"]] == [
        "CalculateY",
        "X",
        "Y",
    ]
    assert splines["row_data_status"] == "ROW_DATA_UNAVAILABLE"
    assert splines["height_semantics"] == "UNKNOWN"
    assert splines["weight_semantics"] == "UNKNOWN"


def test_card_proximity_handles_missing_and_not_applicable_without_guessing() -> None:
    proximity = _load("card_threshold_proximity.json")
    assert proximity["cards_evaluated"] == 435
    assert len(proximity["card_summaries"]) == 435
    assert "NOT_APPLICABLE" in proximity["counts"]
    assert all(
        observation.get("equip_eligibility_claimed") is False
        for observation in proximity["observations"]
        if observation["status"] != "INSUFFICIENT_REQUIREMENTS"
    )


def test_seau_case_uses_only_validated_vectors() -> None:
    seau = _load("position_case_maps.json")["seau"]
    assert seau["known_progression_states"] == [81, 84, 86, 87]
    assert seau["validated_vectors_available"] == [86, 87]
    assert seau["missing_states"] == [81, 84]
    assert seau["final_ratings_inferred"] is False
    assert [card["overall"] for card in seau["cards"]] == [86, 87]


def test_progression_unknowns_are_not_zero_or_path_membership() -> None:
    progression = _load("progression_path_reconstruction.json")
    assert len(progression["chains"]) == 12
    assert len(progression["transitions"]) == 31
    assert progression["path_membership"].startswith("INSUFFICIENT")
    assert progression["path_caps"] == "NO_REPEATED_BOUNDARY_EVIDENCE"
    assert all(row["missing_changes_are_zero"] is False for row in progression["transitions"])
    assert all(
        not row["selected_attributes"] or row["classification"] == "CONFIRMED_PROGRESSION"
        for row in progression["transitions"]
    )


def test_gm_layers_cover_every_card_and_remain_research_only() -> None:
    ability = _load("gm_ability_layer.json")
    replacement = _load("gm_replacement_layer.json")
    assert len(ability) == len(replacement) == 435
    assert all(row["actual_equip_availability_claimed"] is False for row in ability)
    assert all(row["gameplay_value_claimed"] is False for row in ability)
    assert len(_load("chatgpt_research_targets.json")) == 20
    prospective = _load("prospective_validation.json")
    assert prospective["new_cards"] == 0
    assert prospective["latest_untracked_card_inspected"]["after_phase5_cutoff"] is False


def test_capability_chronology_and_ovr_comparison_are_reproducible() -> None:
    chronology = _load("capability_chronology.json")
    comparison = _load("ovr_capability_creep_comparison.json")
    assert chronology["first_access"]
    assert comparison["capability_first_access_events"] == len(chronology["first_access"])
    assert comparison["capability_without_ovr_increase"]
    assert all(
        row["prior_position_ceiling"] >= row["overall"]
        for row in comparison["capability_without_ovr_increase"]
    )


def test_replacement_pressure_v3_is_descriptive_and_evidence_bearing() -> None:
    pressure = _load("replacement_pressure_v3.json")
    assert pressure
    assert all(
        row["pressure"] in {"LOW", "NORMAL", "ELEVATED", "HIGH"} for row in pressure.values()
    )
    assert all(row["prediction_claimed"] is False for row in pressure.values())
    assert all("days_since_ceiling_change" in row for row in pressure.values())


def test_design_signals_are_not_gameplay_proof() -> None:
    signals = _load("ea_design_signals.json")
    assert signals
    assert signals[0]["classification"] == "STRONG_EA_DESIGN_SIGNAL"
    assert all(row["gameplay_proof"] is False for row in signals)


def test_phase6_10_is_deterministic_and_frozen() -> None:
    first = build_phase6_10(ROOT)
    second = build_phase6_10(ROOT)
    assert first == second
    assert first["frozen_input"]["source_commit"] == "8555000"
    assert first["frozen_input"]["population_n"] == 435
    assert first["data_validation"] == {
        "access_bypass": False,
        "canonical_modified": False,
        "conflicts_preserved": True,
        "guessed_values": False,
        "leakage": False,
        "unsupported_spline_claims": False,
    }
