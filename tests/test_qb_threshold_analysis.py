"""Tests for discrete QB score-band and boundary research."""

import json
from pathlib import Path

import pytest

from operation_pancake.research.qb_model_comparison import build_model_comparison
from operation_pancake.research.qb_threshold_analysis import (
    FOCUS_ARCHITECTURES,
    build_threshold_analysis,
    fit_score_bands,
    write_threshold_artifacts,
)


@pytest.fixture(scope="module")
def research() -> dict[str, object]:
    return json.loads(
        Path("data/research/qb_formula_phase_population_boundary.json").read_text(encoding="utf-8")
    )


@pytest.fixture(scope="module")
def analysis(research: dict[str, object]) -> dict[str, object]:
    return build_threshold_analysis(research, build_model_comparison(research))


def test_focuses_on_a_and_c_without_overwriting_baseline(
    analysis: dict[str, object],
) -> None:
    assert analysis["focus_architectures"] == list(FOCUS_ARCHITECTURES)
    assert analysis["baseline_commit"] == "6a265ec"
    assert analysis["formula_status"] == "unsolved"
    assert [(result["architecture"], result["variant"]) for result in analysis["results"]] == [
        ("A", "global_bands"),
        ("A", "archetype_adjusted_bands"),
        ("C", "global_bands"),
        ("C", "archetype_adjusted_bands"),
    ]


def test_threshold_training_and_validation_are_separated(
    analysis: dict[str, object],
) -> None:
    assert analysis["leakage_controls"] == {
        "thresholds_learned_from_fit_only": True,
        "holdout_used_for_threshold_training": False,
        "cross_ovr_blocks_same_player_and_profile": True,
        "profile_duplicates_used_for_training": False,
    }
    assert all(result["training_population"]["count"] == 51 for result in analysis["results"])
    assert all(result["validation_population"]["count"] == 18 for result in analysis["results"])


def test_score_bands_are_monotonic_and_cover_79_to_89(
    analysis: dict[str, object],
) -> None:
    for result in analysis["results"]:
        centers = result["parameters"]["centers"]
        thresholds = result["parameters"]["thresholds"]
        assert list(centers) == [str(level) for level in range(79, 90)]
        assert list(thresholds) == [f"{level}_to_{level + 1}" for level in range(79, 89)]
        assert list(centers.values()) == sorted(centers.values())
        assert list(thresholds.values()) == sorted(thresholds.values())


def test_archetype_adjustments_are_minimal_and_fit_supported(
    analysis: dict[str, object],
) -> None:
    adjusted = [
        result for result in analysis["results"] if result["variant"] == "archetype_adjusted_bands"
    ]
    for result in adjusted:
        assert set(result["parameters"]["archetype_offsets"]) == {
            "Backfield Creator",
            "Dual Threat",
            "Pocket Passer",
        }
        assert "Pure Runner" not in result["parameters"]["archetype_offsets"]


def test_boundary_and_sequence_evidence_remains_complete(
    analysis: dict[str, object],
) -> None:
    for result in analysis["results"]:
        boundary = result["boundary_diagnostics"]
        assert boundary["adjacent_count"] == 14
        assert boundary["same_ovr_count"] == 15
        assert boundary["candidate_sequence_count"] == 17
        assert boundary["candidate_sequences_confirmed_progression"] is False
        assert boundary["explicit_boundary_qb_id"] == "QB-0074"
        assert len(boundary["sequence_information_priorities"]) == 17


def test_all_threshold_predictions_are_deterministic(
    research: dict[str, object], analysis: dict[str, object]
) -> None:
    second = build_threshold_analysis(research, build_model_comparison(research))
    assert second == analysis
    assert len(analysis["predictions"]) == 74 * 4


def test_threshold_stability_is_measured_across_ovr_folds(
    analysis: dict[str, object],
) -> None:
    for result in analysis["results"]:
        stability = result["threshold_stability"]
        assert list(stability) == [f"{level}_to_{level + 1}" for level in range(79, 89)]
        assert all(item["fold_count"] == 9 for item in stability.values())
        assert all(item["range"] >= 0 for item in stability.values())


def test_empty_or_non_fit_band_training_is_rejected() -> None:
    class UnusedModel:
        pass

    with pytest.raises(ValueError, match="fit-partition"):
        fit_score_bands(UnusedModel(), [], (79, 89))


def test_systematic_errors_are_explicitly_classified(
    analysis: dict[str, object],
) -> None:
    allowed = {
        "likely_threshold_error_improved",
        "threshold_mapping_worsened",
        "possible_archetype_effect_data_limited",
        "insufficient_to_distinguish_threshold_from_weighting",
    }
    for result in analysis["results"]:
        assert all(error["classification"] in allowed for error in result["systematic_errors"])


def test_generated_artifacts_are_reproducible(analysis: dict[str, object], tmp_path: Path) -> None:
    first, second = tmp_path / "first", tmp_path / "second"
    write_threshold_artifacts(first, analysis)
    write_threshold_artifacts(second, analysis)
    assert {path.name: path.read_bytes() for path in first.iterdir()} == {
        path.name: path.read_bytes() for path in second.iterdir()
    }


def test_checked_in_artifacts_match_current_analysis(
    analysis: dict[str, object], tmp_path: Path
) -> None:
    generated = tmp_path / "generated"
    committed = Path("data/research/qb_threshold_analysis")
    write_threshold_artifacts(generated, analysis)
    assert {path.name: path.read_bytes() for path in generated.iterdir()} == {
        path.name: path.read_bytes() for path in committed.iterdir()
    }
