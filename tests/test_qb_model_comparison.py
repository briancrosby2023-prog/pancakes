"""Tests for deterministic QB architecture comparison A-D."""

import json
from pathlib import Path

import pytest

from operation_pancake.research.qb_formula_phase import QB_RATING_FIELDS, QBObservation
from operation_pancake.research.qb_model_comparison import (
    ARCHITECTURES,
    build_model_comparison,
    fit_architecture,
    write_model_artifacts,
)


@pytest.fixture(scope="module")
def research() -> dict[str, object]:
    return json.loads(
        Path("data/research/qb_formula_phase_population_boundary.json").read_text(encoding="utf-8")
    )


@pytest.fixture(scope="module")
def comparison(research: dict[str, object]) -> dict[str, object]:
    return build_model_comparison(research)


def test_all_architectures_are_compared(comparison: dict[str, object]) -> None:
    assert [item["architecture"] for item in comparison["architectures"]] == list(ARCHITECTURES)
    assert comparison["formula_status"] == "unsolved"
    assert comparison["fit_count"] == 51
    assert comparison["holdout_count"] == 18


def test_fit_and_holdout_are_strictly_separated(comparison: dict[str, object]) -> None:
    assert comparison["leakage_controls"] == {
        "holdout_used_for_training": False,
        "profile_duplicates_used_for_training": False,
        "cross_ovr_blocks_same_player_and_profile": True,
    }
    assert all(item["training_population"]["count"] == 51 for item in comparison["architectures"])
    assert all(item["validation_population"]["count"] == 18 for item in comparison["architectures"])


def test_non_fit_observation_is_rejected_from_training() -> None:
    observation = QBObservation(
        qb_id="QB-X",
        player="Test",
        overall=80,
        archetype="Pocket Passer",
        program="Test",
        ratings=(80,) * 15,
        model_role="INDEPENDENT HOLDOUT",
        population_scope="PRIMARY 80+ POPULATION",
        unique_profile_key="unique",
        duplicate_note=None,
        frozen_score_check=80.0,
        frozen_score_formula=80.0,
        formula_delta=0.0,
        source_id="source",
        source_locator="page",
        source_record="QB_Cards!1",
        workbook_sheet="QB_Cards",
        workbook_row=1,
        analysis_partition="holdout",
    )
    with pytest.raises(ValueError, match="only the fit partition"):
        fit_architecture("A", [observation, observation])


def test_unknown_architecture_is_rejected() -> None:
    with pytest.raises(KeyError, match="Unknown architecture"):
        fit_architecture("opaque_model", [])


def test_predictions_are_deterministic(
    research: dict[str, object], comparison: dict[str, object]
) -> None:
    second = build_model_comparison(research)
    assert second == comparison
    assert len(comparison["predictions"]) == 74 * 4
    assert all(
        set(row)
        == {
            "architecture",
            "qb_id",
            "player",
            "archetype",
            "actual_ovr",
            "latent_score",
            "predicted_ovr",
            "residual",
            "analysis_partition",
        }
        for row in comparison["predictions"]
    )


def test_all_fifteen_ratings_have_fitted_stability(comparison: dict[str, object]) -> None:
    for result in comparison["weight_stability"]:
        assert tuple(result["shared_weight_stability"]) == QB_RATING_FIELDS
        assert all(
            item["sign_instability"] is False for item in result["shared_weight_stability"].values()
        )


def test_archetype_and_ovr_metrics_are_reported(comparison: dict[str, object]) -> None:
    for result in comparison["architectures"]:
        assert set(result["holdout_by_archetype"]) == {
            "Backfield Creator",
            "Dual Threat",
            "Pocket Passer",
        }
        assert result["holdout_by_ovr"]
        assert result["cross_ovr_metrics"]["count"] > 0
        assert result["threshold_mapping_comparison"].keys() == {
            "round_half_up",
            "floor",
            "ceiling",
        }


def test_pure_runner_is_explicitly_data_limited(comparison: dict[str, object]) -> None:
    architecture_b = next(
        item for item in comparison["architectures"] if item["architecture"] == "B"
    )
    assert architecture_b["viability_status"] == "DATA LIMITED"
    assert any("Pure Runner" in warning for warning in architecture_b["warnings"])
    pure_predictions = [
        row
        for row in comparison["predictions"]
        if row["architecture"] == "B" and row["archetype"] == "Pure Runner"
    ]
    assert len(pure_predictions) == 3
    assert all(row["predicted_ovr"] is None for row in pure_predictions)


def test_boundary_sequences_remain_unconfirmed(comparison: dict[str, object]) -> None:
    for result in comparison["boundary_evaluation"]:
        assert result["candidate_sequence_count"] == 17
        assert result["candidate_sequences_confirmed_progression"] is False
        assert result["adjacent_ovr_count"] == 14
        assert result["same_ovr_count"] == 15


def test_generated_artifacts_are_reproducible(
    comparison: dict[str, object], tmp_path: Path
) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    write_model_artifacts(first, comparison)
    write_model_artifacts(second, comparison)
    assert {path.name: path.read_bytes() for path in first.iterdir()} == {
        path.name: path.read_bytes() for path in second.iterdir()
    }


def test_checked_in_artifacts_match_current_analysis(
    comparison: dict[str, object], tmp_path: Path
) -> None:
    generated = tmp_path / "generated"
    committed = Path("data/research/qb_model_comparison")
    write_model_artifacts(generated, comparison)

    assert {path.name: path.read_bytes() for path in generated.iterdir()} == {
        path.name: path.read_bytes() for path in committed.iterdir()
    }
