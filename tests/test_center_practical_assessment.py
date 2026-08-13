"""Tests for Center practical-model and evaluation-readiness assessment."""

import json
from pathlib import Path

import pytest

from operation_pancake.evaluation.center_evaluator import CenterResearchEvaluator
from operation_pancake.evaluation.position_evaluator import EvaluationResult, PositionEvaluator
from operation_pancake.research.center_practical_assessment import (
    build_center_practical_assessment,
    practical_status,
    write_center_practical_artifacts,
)


def _read(path: str) -> object:
    return json.loads(Path(path).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def inputs() -> tuple[dict[str, object], list[dict[str, object]], dict[str, object]]:
    return (
        _read("data/research/progression_audit/progression_inventory.json"),
        _read(
            "data/research/historical_center_assessment/"
            "historical_center_population_reconciliation.json"
        ),
        _read("data/research/center_exact_validation/saturday_frozen_model_validation.json"),
    )


@pytest.fixture(scope="module")
def analysis(
    inputs: tuple[dict[str, object], list[dict[str, object]], dict[str, object]],
) -> dict[str, object]:
    return build_center_practical_assessment(*inputs)


def test_distinct_status_thresholds() -> None:
    assert practical_status(0.99, True, True, False) == "OPERATIONALLY_SOLVED"
    assert practical_status(0.96, False, True, False) == "EVALUATION_READY"
    assert practical_status(0.94, True, True, False) == "EXPERIMENTAL"
    assert practical_status(None, False, False, False) == "INSUFFICIENT_EVIDENCE"
    assert practical_status(0.99, True, True, True) == "EXPERIMENTAL"


def test_evidence_population_and_card_types_are_separated(
    analysis: dict[str, object],
) -> None:
    inventory = analysis["evidence_inventory"]
    assert len(inventory) == 13
    assert sum(item["complete_profile"] for item in inventory) == 3
    assert sum(item["primary_card_type"] == "SPECIAL/PROGRAM" for item in inventory) == 3
    assert sum(item["primary_card_type"] == "LEGENDARY" for item in inventory) == 1
    assert sum(item["primary_card_type"] == "UNKNOWN" for item in inventory) == 9
    assert sum(item["primary_card_type"] == "REGULAR" for item in inventory) == 0


def test_saturday_is_special_progression_not_regular_validation(
    analysis: dict[str, object],
) -> None:
    saturday = next(
        item for item in analysis["evidence_inventory"] if item["player"] == "Jeff Saturday"
    )
    assert saturday["primary_card_type"] == "LEGENDARY"
    assert saturday["validation_group"] == "PROGRESSION_CONSTRAINT"
    progression = analysis["separated_validation"]["PROGRESSION_COMPATIBILITY"]
    assert progression["card_type"] == "LEGENDARY"
    assert progression["transition_count"] == 22
    assert not progression["universal_veto_applied"]


def test_no_hidden_band_is_fabricated(analysis: dict[str, object]) -> None:
    bands = analysis["hidden_band_analysis"]
    assert not bands["supported"]
    assert bands["classifications"] == []
    assert not bands["band_model_tested"]
    assert all(example["hidden_band"] is None for example in analysis["evaluation_examples"])


def test_trigger_evidence_scope_is_explicit(analysis: dict[str, object]) -> None:
    triggers = analysis["trigger_stat_analysis"]
    assert [item["attribute"] for item in triggers["STRONG"]] == ["PBK", "PBF", "PBP"]
    assert all("Legendary" in item["scope"] for item in triggers["STRONG"])
    assert [item["attribute"] for item in triggers["MODERATE"]] == ["RBP", "AWR"]
    assert not triggers["ordinary_card_trigger_validation_available"]


def test_archetype_complexity_is_not_overfit(analysis: dict[str, object]) -> None:
    archetypes = analysis["archetype_analysis"]
    assert archetypes["complete_static"] == {"Raw Strength": 3}
    assert archetypes["progression_subjects"] == {"Pass Protector": 1}
    assert archetypes["shared_weights_archetype_adjustment"] == "NOT_IDENTIFIABLE"
    assert archetypes["archetype_specific"] == "REJECTED_AS_UNJUSTIFIED_COMPLEXITY"


def test_validation_does_not_report_misleading_accuracy(
    analysis: dict[str, object],
) -> None:
    validation = analysis["separated_validation"]
    assert validation["STATIC_CARD_ACCURACY"]["count"] == 3
    assert validation["REGULAR_CARD_ACCURACY"] == {"count": 0, "accuracy": None}
    assert validation["CROSS_OVR_ACCURACY"] == {"count": 0, "accuracy": None}
    assert not validation["STATIC_CARD_ACCURACY"]["representative_regular_population"]
    assert not validation["STATIC_CARD_ACCURACY"]["independent_validation"]


def test_reusable_evaluator_exposes_uncertainty(
    inputs: tuple[dict[str, object], list[dict[str, object]], dict[str, object]],
) -> None:
    canonical = next(
        card
        for card in inputs[0]["canonical_cards"]
        if card["position"] == "C" and card["player"] == "Ashton Beers"
    )
    evaluator: PositionEvaluator = CenterResearchEvaluator()
    result = evaluator.evaluate(
        canonical["overall"], canonical["archetype"], canonical["attributes"]
    )
    assert isinstance(result, EvaluationResult)
    assert result.model_status == "INSUFFICIENT_EVIDENCE"
    assert result.confidence == "LOW"
    assert result.effective_ovr == pytest.approx(83.009259, abs=1e-6)
    assert result.evaluation_grade == "UNAVAILABLE"
    assert result.next_ovr_proximity is None
    assert set(result.trigger_stats) == {"PBK", "PBF", "PBP"}


def test_center_remains_insufficient_and_not_production_ready(
    analysis: dict[str, object],
) -> None:
    assert analysis["center_status"] == "INSUFFICIENT_EVIDENCE"
    assert analysis["practical_evaluation_model"]["selected"] is None
    assert analysis["pc_tester_readiness"]["center_evaluator_implemented"]
    assert analysis["pc_tester_readiness"]["reusable_positional_interface"]
    assert not analysis["pc_tester_readiness"]["production_ready"]
    assert not analysis["canonical_observations_modified"]
    assert not analysis["unknown_values_guessed"]
    assert not analysis["leakage_detected"]


def test_output_is_deterministic(
    inputs: tuple[dict[str, object], list[dict[str, object]], dict[str, object]],
    analysis: dict[str, object],
    tmp_path: Path,
) -> None:
    assert build_center_practical_assessment(*inputs) == analysis
    write_center_practical_artifacts(tmp_path, analysis)
    assert len(list(tmp_path.glob("*.json"))) == 11
