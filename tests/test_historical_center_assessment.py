"""Tests for recovered historical Center research integration."""

import json
from pathlib import Path

import pytest

from operation_pancake.research.historical_center_assessment import (
    HISTORICAL_NAMES,
    build_historical_center_assessment,
    write_historical_center_artifacts,
)


def _read(path: str) -> object:
    return json.loads(Path(path).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def inputs() -> tuple[dict[str, object], list[dict[str, object]]]:
    return (
        _read("data/research/progression_audit/progression_inventory.json"),
        _read("data/research/saturday_center_analysis/saturday_center_transition_matrix.json"),
    )


@pytest.fixture(scope="module")
def analysis(
    inputs: tuple[dict[str, object], list[dict[str, object]]],
) -> dict[str, object]:
    return build_historical_center_assessment(*inputs)


def test_historical_evidence_is_statused_not_promoted(analysis: dict[str, object]) -> None:
    evidence = analysis["historical_evidence"]
    assert evidence["madden_population_count"] == {
        "value": 53,
        "status": "HISTORICAL_RESEARCH_RESULT",
    }
    assert evidence["performance"]["mae_approximately"]["status"] == (
        "UNVERIFIED_HISTORICAL_RESULT"
    )
    assert not analysis["historical_results_silently_promoted"]


def test_population_reconciliation_preserves_all_12_names(
    analysis: dict[str, object],
) -> None:
    rows = analysis["center_population_reconciliation"]
    assert tuple(row["historical_name"] for row in rows) == HISTORICAL_NAMES
    assert sum(row["canonical_observation_exists"] for row in rows) == 3
    assert sum(not row["canonical_observation_exists"] for row in rows) == 9
    assert sum(row["complete_canonical_profile"] for row in rows) == 3
    assert all(not row["historical_additional_ratings_supplied"] for row in rows)


def test_madden_reproduction_is_refused_without_inputs(
    analysis: dict[str, object],
) -> None:
    result = analysis["madden_model_reproduction"]
    assert not result["reproduced"]
    assert result["mae_reproduced"] is None
    assert result["r_squared_reproduced"] is None
    assert not result["coefficients_reproduced"]
    assert not analysis["formula_fitting_performed"]


def test_historical_cfb_results_and_brady_are_preserved(
    analysis: dict[str, object],
) -> None:
    rows = analysis["cfb_center_comparison"]
    assert len(rows) == 5
    brady = next(row for row in rows if row["player"] == "Brady Small")
    assert brady["historical_residual_observed_minus_result"] == 3.9
    assert brady["currently_reproduced_result"] is None
    investigation = analysis["brady_small_investigation"]
    assert not investigation["full_rating_profile_available"]
    assert not investigation["structural_outlier_currently_validated"]
    assert not investigation["special_correction_created"]


def test_saturday_is_an_independent_partial_test(analysis: dict[str, object]) -> None:
    result = analysis["saturday_independent_test"]
    assert result["transitions_tested"] == 22
    assert result["partially_compatible_count"] == 5
    assert result["indeterminate_count"] == 17
    assert result["contradicted_count"] == 0
    assert result["complete_compatibility_count"] == 0
    assert not result["historical_weights_refitted_to_saturday"]


def test_archetype_and_weight_evidence_remain_calibrated(
    analysis: dict[str, object],
) -> None:
    archetypes = analysis["archetype_analysis"]
    assert archetypes["observed_current_archetypes"] == {
        "Pass Protector": 1,
        "Raw Strength": 3,
    }
    assert archetypes["archetype_specific_formulas"] == "UNSUPPORTED_BY_SAMPLE_SIZE"
    assert analysis["weight_evidence"]["STRONG_CONTROLLED_EVIDENCE"] == [
        "PBK",
        "PBF",
        "PBP",
    ]
    assert analysis["center_formula_status"] == "INSUFFICIENT EVIDENCE"
    assert not analysis["pc_app_readiness"]["center_model_usable"]


def test_no_canonical_contamination_or_guessing(analysis: dict[str, object]) -> None:
    assert not analysis["canonical_observations_modified"]
    assert not analysis["unknown_values_guessed"]
    assert analysis["best_current_center_model"] is None


def test_output_is_deterministic(
    inputs: tuple[dict[str, object], list[dict[str, object]]],
    analysis: dict[str, object],
    tmp_path: Path,
) -> None:
    assert build_historical_center_assessment(*inputs) == analysis
    write_historical_center_artifacts(tmp_path, analysis)
    assert len(list(tmp_path.glob("*.json"))) == 11
