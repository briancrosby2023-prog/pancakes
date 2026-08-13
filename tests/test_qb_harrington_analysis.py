"""Tests for the controlled Joey Harrington progression experiment."""

import json
from pathlib import Path

import pytest

from operation_pancake.research.qb_formula_phase import QB_RATING_FIELDS
from operation_pancake.research.qb_harrington_analysis import (
    CHAIN_IDS,
    build_harrington_analysis,
    write_harrington_artifacts,
)


def _read(path: str) -> dict[str, object]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def inputs() -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    constraints = json.loads(
        Path(
            "data/research/qb_provenance_audit/qb_confirmed_progression_constraints.json"
        ).read_text(encoding="utf-8")
    )
    return (
        _read("data/research/qb_formula_phase_population_boundary.json"),
        _read("data/research/qb_model_comparison/qb_model_comparison.json"),
        {"confirmed_constraints": constraints},
    )


@pytest.fixture(scope="module")
def analysis(
    inputs: tuple[dict[str, object], dict[str, object], dict[str, object]],
) -> dict[str, object]:
    return build_harrington_analysis(*inputs, "data/canonical/canonical_v1.9.xlsx")


def test_exact_confirmed_chain_is_reconstructed(analysis: dict[str, object]) -> None:
    assert tuple(card["qb_id"] for card in analysis["chain"]) == CHAIN_IDS
    assert [card["overall"] for card in analysis["chain"]] == [79, 81, 84, 86]
    assert {card["program"] for card in analysis["chain"]} == {"SI Legends - Millennium"}
    assert all(card["progression_confirmed"] for card in analysis["chain"])
    assert all(set(card["ratings"]) == set(QB_RATING_FIELDS) for card in analysis["chain"])


def test_transition_deltas_are_exact(analysis: dict[str, object]) -> None:
    transitions = analysis["transitions"]
    assert [item["observed_ovr_movement"] for item in transitions] == [2, 3, 2]
    assert [item["total_raw_rating_point_increase"] for item in transitions] == [24, 37, 24]
    assert [item["changed_attribute_count"] for item in transitions] == [12, 12, 12]
    assert [item["unchanged_attributes"] for item in transitions] == [
        ["AWR", "TGH", "TAC"],
        ["AWR", "TGH", "TAC"],
        ["AWR", "TGH", "TAC"],
    ]
    assert transitions[0]["structurally_uniform"]
    assert not transitions[1]["structurally_uniform"]
    assert transitions[1]["exceptional_attributes"] == {"TUP": 4}
    assert transitions[2]["structurally_uniform"]


def test_a_and_c_use_existing_parameters_without_refitting(
    analysis: dict[str, object],
) -> None:
    assert not analysis["global_formula_search_performed"]
    assert not analysis["new_interactions_added"]
    for architecture in ("A", "C"):
        result = analysis["architectures"][architecture]
        assert result["parameters_source"] == "existing qb_model_comparison artifact"
        assert result["refitted_to_harrington"] is False
        assert len(result["state_scores"]) == 4
        assert len(result["transitions"]) == 3


def test_score_movements_and_contributions_reconcile(
    analysis: dict[str, object],
) -> None:
    for architecture in ("A", "C"):
        transitions = analysis["architectures"][architecture]["transitions"]
        for transition in transitions:
            assert transition["contribution_sum"] == pytest.approx(
                transition["latent_score_movement"], abs=1e-7
            )
            assert sum(
                item["percent_of_score_movement"] for item in transition["contributions"]
            ) == pytest.approx(100, abs=1e-4)


def test_offset_intervals_and_inequalities_are_generated(
    analysis: dict[str, object],
) -> None:
    for architecture in ("A", "C"):
        result = analysis["architectures"][architecture]
        offset = result["local_offset"]
        assert len(offset["state_offset_intervals"]) == 4
        assert offset["production_parameter_created"] is False
        for transition in result["transitions"]:
            bounds = transition["ordinary_rounding_movement_interval"]
            assert bounds["lower_exclusive"] < transition["latent_score_movement"]
            assert transition["latent_score_movement"] < bounds["upper_exclusive"]
            assert transition["movement_compatible"]


def test_madden_reference_is_internal_and_mapping_neutral(
    analysis: dict[str, object],
) -> None:
    reference = analysis["madden_reference"]
    assert reference["available"]
    assert reference["source_sheet"] == "Madden19_QB_Weights"
    assert reference["historical_reference_only"]
    assert reference["cfb_archetype_mapping_assumed"] is False
    assert set(reference["movements"]) == {
        "Field General",
        "Scrambler",
        "Strong Arm",
        "West Coast",
    }


def test_upgrade_magnitude_comparison_does_not_promote_a_formula(
    analysis: dict[str, object],
) -> None:
    comparison = analysis["magnitude_comparison"]
    assert comparison["best_descriptive_representations"] == [
        "mean_changed_attribute_delta",
        "total_raw_rating_points",
    ]
    count_result = comparison["proportional_no_intercept_comparisons"]["changed_attribute_count"]
    assert len(set(count_result["scaled_predictions"])) == 1
    assert analysis["formula_status"] == "unsolved"


def test_analysis_and_artifacts_are_deterministic(
    inputs: tuple[dict[str, object], dict[str, object], dict[str, object]],
    analysis: dict[str, object],
    tmp_path: Path,
) -> None:
    assert build_harrington_analysis(*inputs, "data/canonical/canonical_v1.9.xlsx") == analysis
    write_harrington_artifacts(tmp_path, analysis)
    assert len(list(tmp_path.glob("*.json"))) == 11
