"""Tests for exact recovered Center model and Saturday validation."""

import json
from pathlib import Path

import pytest

from operation_pancake.research.center_exact_validation import (
    CALIBRATION_HIGH,
    CALIBRATION_INTERCEPT,
    CALIBRATION_LOW,
    CALIBRATION_SLOPE,
    SATURDAY_BASE,
    SPARSE_IDS,
    WEIGHT_TOTAL,
    WEIGHTS,
    FrozenHistoricalCenterModel,
    build_center_exact_validation,
    write_center_exact_artifacts,
)


def _read(path: str) -> object:
    return json.loads(Path(path).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def inputs() -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    return (
        _read("data/research/saturday_center_analysis/saturday_center_transition_matrix.json"),
        _read(
            "data/research/historical_center_assessment/"
            "historical_center_population_reconciliation.json"
        ),
    )


@pytest.fixture(scope="module")
def analysis(
    inputs: tuple[list[dict[str, object]], list[dict[str, object]]],
) -> dict[str, object]:
    return build_center_exact_validation(*inputs)


def test_exact_weights_and_calibration(analysis: dict[str, object]) -> None:
    assert sum(WEIGHTS.values()) == WEIGHT_TOTAL == 108
    assert analysis["frozen_model"]["weights"] == WEIGHTS
    assert analysis["calibration"]["low"] == CALIBRATION_LOW
    assert analysis["calibration"]["high"] == CALIBRATION_HIGH
    assert analysis["calibration"]["slope_supplied"] == CALIBRATION_SLOPE
    assert analysis["calibration"]["intercept_supplied"] == CALIBRATION_INTERCEPT
    assert [row["attribute"] for row in analysis["coefficients"][:4]] == [
        "RBP",
        "PBP",
        "AWR",
        "STR",
    ]


def test_reproduction_scope_does_not_fabricate_53_rows(
    analysis: dict[str, object],
) -> None:
    source = analysis["madden_source_population"]
    assert source["reported_row_count"] == 53
    assert source["rows_ingested"] == []
    assert not source["complete"]
    reproduction = analysis["historical_model_reproduction"]
    assert reproduction["exact_constants_reproduced"]
    assert not reproduction["metrics_reproduced_from_rows"]
    assert reproduction["reported_metrics"] == {"mae": 0.9122, "r_squared": 0.98172}


def test_model_is_frozen_before_saturday(analysis: dict[str, object]) -> None:
    model = FrozenHistoricalCenterModel()
    assert model.status == "FROZEN_HISTORICAL_HYPOTHESIS"
    assert analysis["frozen_model"]["frozen_before_saturday"]
    assert not analysis["frozen_model"]["refitted_to_cfb_or_saturday"]
    assert analysis["saturday_validation"]["model_frozen_before_evaluation"]


def test_saturday_vector_is_exactly_sufficient_without_tgh(
    analysis: dict[str, object],
) -> None:
    validation = analysis["saturday_validation"]
    assert validation["known_saturday_vector_sufficient"]
    assert not validation["tgh_required"]
    assert FrozenHistoricalCenterModel().weighted_score(SATURDAY_BASE) == pytest.approx(
        76.8425925926
    )
    assert validation["base_madden_prediction"] == 72


def test_all_22_transitions_are_evaluated(analysis: dict[str, object]) -> None:
    validation = analysis["saturday_validation"]
    assert len(validation["trajectories"]) == 11
    assert len(validation["transitions"]) == 22
    assert all(item["positive_direction_compatible"] for item in validation["transitions"])
    assert validation["counts"] == {
        "compatible": 0,
        "tension": 0,
        "contradicted": 22,
        "indeterminate": 0,
    }


def test_shared_baseline_rejects_one_common_second_threshold(
    analysis: dict[str, object],
) -> None:
    shared = analysis["saturday_validation"]["shared_baseline_test"]
    assert shared["common_80_to_81_threshold_interval"]["feasible"]
    assert not shared["common_81_to_82_threshold_condition"]["feasible"]
    assert shared["common_81_to_82_threshold_condition"]["overlap"] > 0
    assert shared["result"] == "CONTRADICTED"


def test_sparse_experiments_do_not_overclaim_historical_ordering(
    analysis: dict[str, object],
) -> None:
    sparse = analysis["sparse_transition_analysis"]
    assert tuple(item["transition_id"] for item in sparse["transitions"]) == SPARSE_IDS
    assert len(sparse["by_attribute"]["PBP"]) == 4
    assert len(sparse["by_attribute"]["PBF"]) == 2
    assert len(sparse["by_attribute"]["PBK"]) == 1
    assert sparse["historical_ordering"] == "PBP > PBF > PBK"
    assert not sparse["ordering_supported"]


def test_cfb_recalibration_and_minimal_model_are_not_leaked(
    analysis: dict[str, object],
) -> None:
    cfb = analysis["cfb_reproduction"]
    assert cfb["recovered_names"] == 12
    assert cfb["complete_profiles"] == 3
    assert not cfb["recalibration_performed"]
    assert cfb["reported_model_mc_metrics"] == {"mae": 0.4624, "r_squared": 0.8109}
    assert analysis["candidate_models"]["MC"]["status"] == ("INSUFFICIENT_COMPLETE_CFB_ROWS")
    assert not analysis["leakage_detected"]


def test_research_interface_is_not_a_fake_production_model(
    analysis: dict[str, object],
) -> None:
    assert analysis["center_formula_status"] == "REJECTED"
    assert analysis["best_current_center_model"] is None
    assert analysis["pc_app_readiness"]["center_engine"] == (
        "RESEARCH_ONLY_FROZEN_HISTORICAL_INTERFACE"
    )
    assert not analysis["pc_app_readiness"]["production_prediction_usable"]
    assert not analysis["canonical_observations_modified"]
    assert not analysis["unknown_ratings_guessed"]


def test_output_is_deterministic(
    inputs: tuple[list[dict[str, object]], list[dict[str, object]]],
    analysis: dict[str, object],
    tmp_path: Path,
) -> None:
    assert build_center_exact_validation(*inputs) == analysis
    write_center_exact_artifacts(tmp_path, analysis)
    assert len(list(tmp_path.glob("*.json"))) == 13
