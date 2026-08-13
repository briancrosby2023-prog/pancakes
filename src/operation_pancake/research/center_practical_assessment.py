"""Practical Center model recovery and evaluation-readiness assessment."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from operation_pancake.evaluation.center_evaluator import CenterResearchEvaluator
from operation_pancake.research.center_exact_validation import FrozenHistoricalCenterModel

HISTORICAL_NAMES = (
    "Carson Hinzman",
    "Brady Small",
    "Coleton Price",
    "Landen Hatchett",
    "Lyndon Cooper",
    "Ashton Beers Core",
    "Jake Guarnera",
    "Jake Renfro",
    "Levi Hubbard",
    "Ashton Beers",
    "Justin Evans",
    "Bruce Mitchell",
)


def practical_status(
    accuracy: float | None,
    independent_validation: bool,
    stable: bool,
    systematic_failure: bool,
) -> str:
    """Apply distinct formula and practical evaluation standards."""
    if accuracy is None:
        return "INSUFFICIENT_EVIDENCE"
    if accuracy >= 0.98 and independent_validation and stable and not systematic_failure:
        return "OPERATIONALLY_SOLVED"
    if accuracy >= 0.95 and stable and not systematic_failure:
        return "EVALUATION_READY"
    return "EXPERIMENTAL"


def _card_type(card: dict[str, Any]) -> dict[str, Any]:
    program = card.get("program")
    if program in {"Standouts", "Platinum Rare"}:
        return {
            "primary_card_type": "SPECIAL/PROGRAM",
            "validation_group": "SPECIAL_CARD_VALIDATION",
            "reason": f"Canonical program is explicitly {program}.",
        }
    return {
        "primary_card_type": "UNKNOWN",
        "validation_group": "UNKNOWN_CARD_TYPE",
        "reason": "No repository evidence establishes regular or special card type.",
    }


def _inventory(
    canonical: list[dict[str, Any]], reconciliation: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    canonical_by_name = {card["player"]: card for card in canonical}
    rows = []
    for name in HISTORICAL_NAMES:
        card = canonical_by_name.get(name)
        classification = (
            _card_type(card)
            if card
            else {
                "primary_card_type": "UNKNOWN",
                "validation_group": "UNKNOWN_CARD_TYPE",
                "reason": "Historical name is preserved but no profile/card metadata is available.",
            }
        )
        rows.append(
            {
                "observation_id": card["card_id"]
                if card
                else f"HIST-C-{name.upper().replace(' ', '-')}",
                "player": name,
                "position": "C",
                "overall": card["overall"]
                if card
                else next(
                    (item["overall"] for item in reconciliation if item["historical_name"] == name),
                    None,
                ),
                "archetype": card["archetype"] if card else None,
                "program": card["program"] if card else None,
                "ratings": card["attributes"] if card else None,
                "complete_profile": card is not None,
                "canonical": card is not None,
                "source_id": card["source_id"] if card else None,
                **classification,
                "progression_evidence": False,
            }
        )
    rows.append(
        {
            "observation_id": "HIST-C-JEFF-SATURDAY-80",
            "player": "Jeff Saturday",
            "position": "C",
            "overall": 80,
            "archetype": "Pass Protector",
            "program": "Legendary",
            "ratings": None,
            "complete_profile": False,
            "canonical": False,
            "source_id": "RECOVERED-HISTORICAL-OPERATION-PANCAKE",
            "primary_card_type": "LEGENDARY",
            "validation_group": "PROGRESSION_CONSTRAINT",
            "reason": (
                "User-supplied recovered evidence explicitly identifies a Legendary "
                "progression card."
            ),
            "progression_evidence": True,
        }
    )
    return rows


def _static_baseline(inventory: list[dict[str, Any]]) -> dict[str, Any]:
    model = FrozenHistoricalCenterModel()
    cards = [item for item in inventory if item["complete_profile"]]
    predictions = []
    for card in cards:
        weighted = model.weighted_score(card["ratings"])
        calibrated = model.calibrated_score(card["ratings"])
        predictions.append(
            {
                "player": card["player"],
                "observed_ovr": card["overall"],
                "weighted_score": round(weighted, 8),
                "weighted_score_rounded": round(weighted),
                "madden_calibrated_score": round(calibrated, 8),
                "madden_calibrated_prediction": model.predict(card["ratings"]),
                "validation_group": card["validation_group"],
            }
        )
    return {
        "count": len(predictions),
        "predictions": predictions,
        "weighted_score_exact_accuracy": (
            sum(row["weighted_score_rounded"] == row["observed_ovr"] for row in predictions)
            / len(predictions)
        ),
        "madden_calibration_exact_accuracy": (
            sum(row["madden_calibrated_prediction"] == row["observed_ovr"] for row in predictions)
            / len(predictions)
        ),
        "representative_regular_population": False,
        "independent_validation": False,
    }


def build_center_practical_assessment(
    progression_inventory: dict[str, Any],
    reconciliation: list[dict[str, Any]],
    saturday_validation: dict[str, Any],
) -> dict[str, Any]:
    """Assess practical readiness while separating static and Legendary evidence."""
    canonical = [
        card for card in progression_inventory["canonical_cards"] if card["position"] == "C"
    ]
    inventory = _inventory(canonical, reconciliation)
    baseline = _static_baseline(inventory)
    evaluator = CenterResearchEvaluator()
    examples = [
        asdict(evaluator.evaluate(card["overall"], card["archetype"], card["ratings"]))
        for card in inventory
        if card["complete_profile"]
    ]
    return {
        "schema_version": 1,
        "phase": "Center Practical Model & Evaluation-Ready Assessment",
        "policy": {
            "formula_standard": (
                "OPERATIONALLY_SOLVED requires ≥98%, independent validation, and no "
                "systematic failure."
            ),
            "practical_standard": (
                "EVALUATION_READY requires approximately ≥95% representative accuracy and "
                "stable Moneyball behavior."
            ),
            "special_progression_not_universal_veto": True,
        },
        "evidence_inventory": inventory,
        "historical_profile_recovery": {
            "searched_names": list(HISTORICAL_NAMES),
            "complete_profiles_recovered": ["Ashton Beers", "Justin Evans", "Bruce Mitchell"],
            "historical_only_profiles_still_missing": [
                name
                for name in HISTORICAL_NAMES
                if name not in {"Ashton Beers", "Justin Evans", "Bruce Mitchell"}
            ],
            "new_profiles_recovered_this_block": [],
        },
        "hidden_band_analysis": {
            "supported": False,
            "classifications": [],
            "reason": (
                "Three static cards cover only OVR 84–85, have no established hidden ordering, "
                "and all are special/program cards. LOW/MID/HIGH assignment would be fabricated."
            ),
            "band_model_tested": False,
        },
        "trigger_stat_analysis": {
            "STRONG": [
                {"attribute": field, "scope": "Legendary progression local sensitivity"}
                for field in ("PBK", "PBF", "PBP")
            ],
            "MODERATE": [
                {"attribute": field, "scope": "unreproduced historical population evidence"}
                for field in ("RBP", "AWR")
            ],
            "WEAK": ["RBK", "RBF", "IBL", "LBK", "STR", "SPD", "ACC", "AGI", "COD"],
            "UNSUPPORTED": ["TGH", "RCK"],
            "ordinary_card_trigger_validation_available": False,
        },
        "archetype_analysis": {
            "complete_static": {"Raw Strength": 3},
            "progression_subjects": {"Pass Protector": 1},
            "universal_model": "INSUFFICIENT_VALIDATION",
            "shared_weights_archetype_adjustment": "NOT_IDENTIFIABLE",
            "archetype_specific": "REJECTED_AS_UNJUSTIFIED_COMPLEXITY",
        },
        "candidate_models": [
            {
                "model": "Madden calibrated reference M",
                "architecture": "historical weights + historical calibration",
                "static_exact_accuracy": baseline["madden_calibration_exact_accuracy"],
                "representative_validation": False,
                "status": "REJECTED_AS_CFB_PRACTICAL_MODEL",
            },
            {
                "model": "Historical weighted score W",
                "architecture": "historical weighted average without Madden calibration",
                "static_exact_accuracy": baseline["weighted_score_exact_accuracy"],
                "representative_validation": False,
                "status": "EXPERIMENTAL_REFERENCE_ONLY",
            },
            {
                "model": "Hidden-band Center",
                "architecture": "weighted score bands",
                "static_exact_accuracy": None,
                "representative_validation": False,
                "status": "INSUFFICIENT_BAND_LABELS",
            },
            {
                "model": "Minimal CFB Center fit",
                "architecture": "universal or archetype-adjusted",
                "static_exact_accuracy": None,
                "representative_validation": False,
                "status": "NOT_FIT_TO_AVOID_THREE_CARD_OVERFIT",
            },
        ],
        "separated_validation": {
            "STATIC_CARD_ACCURACY": baseline,
            "REGULAR_CARD_ACCURACY": {"count": 0, "accuracy": None},
            "SPECIAL_CARD_ACCURACY": {
                "count": 3,
                "historical_weighted_score_exact_accuracy": baseline[
                    "weighted_score_exact_accuracy"
                ],
            },
            "PROGRESSION_COMPATIBILITY": {
                "card_type": "LEGENDARY",
                "transition_count": 22,
                "frozen_madden_absolute_contradictions": saturday_validation["counts"][
                    "contradicted"
                ],
                "positive_direction_count": sum(
                    row["positive_direction_compatible"]
                    for row in saturday_validation["transitions"]
                ),
                "universal_veto_applied": False,
            },
            "CROSS_OVR_ACCURACY": {"count": 0, "accuracy": None},
            "ARCHETYPE_ACCURACY": {
                "Raw Strength": {"count": 3, "representative": False},
                "Pass Protector": {"count": 0, "representative": False},
            },
        },
        "practical_evaluation_model": {
            "selected": None,
            "status": practical_status(None, False, False, False),
            "reason": (
                "No representative regular-card population, independent validation, cross-OVR "
                "set, or supported hidden-band labels exist."
            ),
        },
        "evaluation_examples": examples,
        "moneyball_capability": {
            "same_ovr_ranking": False,
            "hidden_band": False,
            "next_ovr_proximity": False,
            "attribute_contributions": True,
            "evaluation_grade": False,
            "market_value": False,
        },
        "center_status": "INSUFFICIENT_EVIDENCE",
        "pc_tester_readiness": {
            "center_evaluator_implemented": True,
            "reusable_positional_interface": True,
            "production_ready": False,
            "exposed_status": "INSUFFICIENT_EVIDENCE",
        },
        "saturday_interpretation": (
            "Jeff Saturday is Legendary progression evidence. It establishes local sensitivity "
            "and challenges frozen M progression behavior, but is not treated as regular-card "
            "accuracy or a universal veto on future ordinary-card models."
        ),
        "canonical_observations_modified": False,
        "unknown_values_guessed": False,
        "leakage_detected": False,
    }


def write_center_practical_artifacts(directory: str | Path, analysis: dict[str, Any]) -> None:
    """Write deterministic practical-assessment artifacts."""
    root = Path(directory)
    root.mkdir(parents=True, exist_ok=True)
    payloads = {
        "center_evidence_inventory.json": analysis["evidence_inventory"],
        "center_card_type_classifications.json": [
            {
                key: item[key]
                for key in (
                    "observation_id",
                    "player",
                    "primary_card_type",
                    "validation_group",
                    "reason",
                    "progression_evidence",
                )
            }
            for item in analysis["evidence_inventory"]
        ],
        "center_historical_profile_recovery.json": analysis["historical_profile_recovery"],
        "center_hidden_band_analysis.json": analysis["hidden_band_analysis"],
        "center_trigger_stat_analysis.json": analysis["trigger_stat_analysis"],
        "center_archetype_comparison.json": analysis["archetype_analysis"],
        "center_practical_candidate_models.json": analysis["candidate_models"],
        "center_separated_validation.json": analysis["separated_validation"],
        "center_practical_evaluation_model.json": analysis["practical_evaluation_model"],
        "center_evaluation_examples.json": analysis["evaluation_examples"],
        "center_practical_formula_status.json": {
            "center_status": analysis["center_status"],
            "pc_tester_readiness": analysis["pc_tester_readiness"],
            "moneyball_capability": analysis["moneyball_capability"],
            "saturday_interpretation": analysis["saturday_interpretation"],
        },
    }
    for name, payload in payloads.items():
        (root / name).write_text(
            json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
