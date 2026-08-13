"""Tests for small-budget QB nonlinear mechanism research."""

import json
from pathlib import Path

import pytest

from operation_pancake.research.qb_nonlinearity_analysis import (
    CANDIDATES,
    build_nonlinearity_analysis,
    fit_candidate,
    write_nonlinearity_artifacts,
)


@pytest.fixture(scope="module")
def research() -> dict[str, object]:
    return json.loads(
        Path("data/research/qb_formula_phase_population_boundary.json").read_text(encoding="utf-8")
    )


@pytest.fixture(scope="module")
def analysis(research: dict[str, object]) -> dict[str, object]:
    return build_nonlinearity_analysis(research)


def test_candidate_family_is_small_and_predeclared(analysis: dict[str, object]) -> None:
    assert len(CANDIDATES) == 8
    assert analysis["complexity_budget"] == {
        "maximum_mechanisms": 2,
        "candidate_count_including_baseline": 8,
        "candidate_set_predeclared_before_validation": True,
    }
    assert all(result["mechanism_count"] <= 2 for result in analysis["results"])


def test_baseline_and_plausible_mechanisms_are_present(
    analysis: dict[str, object],
) -> None:
    assert [result["candidate_id"] for result in analysis["results"]] == [
        "baseline_a",
        "passing_cap_90",
        "passing_diminishing_90",
        "passing_accuracy_bottleneck",
        "power_deep_bottleneck",
        "mobility_bottleneck",
        "low_awareness_floor_80",
        "passing_plus_power_bottlenecks",
    ]
    assert analysis["formula_status"] == "unsolved"


def test_leakage_controls_preserve_all_research_partitions(
    analysis: dict[str, object],
) -> None:
    assert analysis["leakage_controls"] == {
        "holdout_used_for_fitting": False,
        "boundary_used_for_fitting": False,
        "research_only_used_for_fitting": False,
        "profile_duplicate_used_for_fitting": False,
        "cross_ovr_blocks_same_player_and_profile": True,
    }


def test_fitting_rejects_empty_or_non_fit_population() -> None:
    with pytest.raises(ValueError, match="fit observations"):
        fit_candidate(CANDIDATES[0], [])


def test_all_required_metrics_and_constraints_are_reported(
    analysis: dict[str, object],
) -> None:
    for result in analysis["results"]:
        assert result["fit_metrics"]["count"] == 51
        assert result["holdout_metrics"]["count"] == 18
        assert result["cross_ovr_metrics"]["count"] == 51
        assert result["constraints"]["adjacent_count"] == 14
        assert result["constraints"]["same_ovr_count"] == 15
        assert result["constraints"]["candidate_sequence_count"] == 17
        assert result["constraints"]["candidate_sequences_confirmed_progression"] is False
        assert len(result["constraints"]["adjacent_pair_effects"]) == 14
        assert len(result["constraints"]["same_ovr_pair_effects"]) == 15
        assert len(result["constraints"]["sequence_effects_by_information_value"]) == 17
        assert set(result["holdout_by_archetype"]) == {
            "Backfield Creator",
            "Dual Threat",
            "Pocket Passer",
        }


def test_qb0074_is_fully_audited_without_special_training(
    analysis: dict[str, object],
) -> None:
    for result in analysis["results"]:
        audit = result["qb_0074_audit"]
        assert audit["ratings_complete"] is True
        assert audit["source_id"] == "SRC-QB-002"
        assert audit["source_locator"] == "Screenshot 2026-07-26 204922.jpg"
        assert audit["source_record"] == "QB_Cards!78"
        assert audit["frozen_formula_audit_matches"] is True


def test_coefficient_stability_covers_every_candidate_feature(
    analysis: dict[str, object],
) -> None:
    for result in analysis["results"]:
        assert list(result["coefficient_stability"]) == result["feature_names"]
        assert all(
            feature["fold_count"] == 9 for feature in result["coefficient_stability"].values()
        )


def test_analysis_and_predictions_are_deterministic(
    research: dict[str, object], analysis: dict[str, object]
) -> None:
    assert build_nonlinearity_analysis(research) == analysis
    assert len(analysis["predictions"]) == 74 * len(CANDIDATES)


def test_generated_artifacts_are_reproducible(analysis: dict[str, object], tmp_path: Path) -> None:
    first, second = tmp_path / "first", tmp_path / "second"
    write_nonlinearity_artifacts(first, analysis)
    write_nonlinearity_artifacts(second, analysis)
    assert {path.name: path.read_bytes() for path in first.iterdir()} == {
        path.name: path.read_bytes() for path in second.iterdir()
    }


def test_checked_in_artifacts_match_current_analysis(
    analysis: dict[str, object], tmp_path: Path
) -> None:
    generated = tmp_path / "generated"
    committed = Path("data/research/qb_nonlinearity_analysis")
    write_nonlinearity_artifacts(generated, analysis)
    assert {path.name: path.read_bytes() for path in generated.iterdir()} == {
        path.name: path.read_bytes() for path in committed.iterdir()
    }
