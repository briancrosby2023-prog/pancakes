"""Tests for Jeff Saturday controlled Center reconstruction."""

import json
from pathlib import Path

import pytest

from operation_pancake.research.saturday_center_analysis import (
    CENTER_ATTRIBUTES,
    RECOVERED_BASE,
    SPARSE_IDS,
    build_saturday_center_analysis,
    write_saturday_center_artifacts,
)


def _read(path: str) -> object:
    return json.loads(Path(path).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def inputs() -> tuple[dict[str, object], dict[str, object]]:
    progression = _read("data/research/progression_audit/progression_inventory.json")
    progression["confirmed_transitions"] = _read(
        "data/research/progression_audit/confirmed_transition_deltas.json"
    )
    previous = {
        "reset_linkages": _read(
            "data/research/reset_context_audit/reset_linkage_classifications.json"
        )
    }
    return progression, previous


@pytest.fixture(scope="module")
def analysis(
    inputs: tuple[dict[str, object], dict[str, object]],
) -> dict[str, object]:
    return build_saturday_center_analysis(*inputs)


def test_recovered_evidence_provenance_is_explicit(analysis: dict[str, object]) -> None:
    evidence = analysis["evidence_record"]
    assert evidence["player"] == {
        "value": "Jeff Saturday",
        "status": "HISTORICALLY_RECOVERED",
    }
    assert evidence["position"]["value"] == "C"
    assert evidence["archetype"]["value"] == "Pass Protector"
    assert evidence["starting_overall"]["value"] == 80
    assert evidence["reset_deltas_status"] == "REPOSITORY_CONFIRMED"
    assert evidence["previous_repository_only_result_preserved"]["classification"] == ("UNRESOLVED")


def test_base_ratings_preserve_unknown_tgh(analysis: dict[str, object]) -> None:
    ratings = analysis["evidence_record"]["base_ratings"]
    assert set(ratings) == set(CENTER_ATTRIBUTES)
    assert all(ratings[field]["value"] == value for field, value in RECOVERED_BASE.items())
    assert ratings["TGH"] == {"value": None, "status": "UNKNOWN"}
    assert not analysis["unknown_ratings_guessed"]


def test_all_reset_series_are_assigned_to_center(analysis: dict[str, object]) -> None:
    linkages = analysis["reset_linkages"]
    assert len(linkages) == 11
    assert all(item["classification"] == "CONFIRMED" for item in linkages)
    assert all(item["player"] == "Jeff Saturday" for item in linkages)
    assert all(item["position"] == "C" for item in linkages)
    assert all(item["archetype"] == "Pass Protector" for item in linkages)
    assert all(item["prior_repository_only_classification"] == "UNRESOLVED" for item in linkages)


def test_fresh_baseline_then_sequential_trajectory(analysis: dict[str, object]) -> None:
    architecture = analysis["trajectory_architecture"]
    assert architecture["classification"] == ("FRESH_COMMON_80_BASELINE_THEN_SEQUENTIAL_A_B")
    assert architecture["series_are_independent"]
    assert architecture["within_series_b_follows_a"]
    assert len(analysis["reconstructed_series"]) == 11
    assert all(
        [state["overall"] for state in series["states"]] == [80, 81, 82]
        for series in analysis["reconstructed_series"]
    )


def test_delta_arithmetic_and_value_statuses(analysis: dict[str, object]) -> None:
    sat_01 = next(item for item in analysis["reconstructed_series"] if item["reset_id"] == "SAT-01")
    base, at_81, at_82 = sat_01["states"]
    assert base["ratings"]["PBF"] == {"value": 78, "status": "DIRECTLY_OBSERVED"}
    assert at_81["ratings"]["PBF"] == {"value": 83, "status": "DERIVED_FROM_CONFIRMED_DELTA"}
    assert at_82["ratings"]["PBF"] == {"value": 84, "status": "DERIVED_FROM_CONFIRMED_DELTA"}
    assert at_82["ratings"]["TGH"] == {"value": None, "status": "UNKNOWN"}


def test_sparse_center_constraints_are_preserved(analysis: dict[str, object]) -> None:
    sparse = analysis["sparse_boundary_analysis"]
    assert tuple(item["transition_id"] for item in sparse) == SPARSE_IDS
    assert all(item["position"] == "C" for item in sparse)
    assert all(item["archetype"] == "Pass Protector" for item in sparse)
    assert all(item["information_value"] == "HIGH_SPARSE_BOUNDARY" for item in sparse)
    assert all(not item["one_rating_point_equals_one_ovr"] for item in sparse)


def test_center_model_status_remains_evidence_limited(analysis: dict[str, object]) -> None:
    comparison = analysis["center_model_comparison"]
    assert comparison["canonical_count"] == 3
    assert comparison["canonical_archetypes"] == ["Raw Strength"]
    assert not comparison["saturday_archetype_represented_in_canonical_cards"]
    assert not comparison["madden_center_weight_reference_available"]
    assert not comparison["candidate_model_tested"]
    assert analysis["center_formula_status"] == "INSUFFICIENT EVIDENCE"
    assert not analysis["formula_fitting_performed"]


def test_output_is_deterministic(
    inputs: tuple[dict[str, object], dict[str, object]],
    analysis: dict[str, object],
    tmp_path: Path,
) -> None:
    assert build_saturday_center_analysis(*inputs) == analysis
    write_saturday_center_artifacts(tmp_path, analysis)
    assert len(list(tmp_path.glob("*.json"))) == 10
