"""Recovered historical Center research and integrated evidence assessment."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

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
HISTORICAL_RESULTS = {
    "Brady Small": (84, 80.10),
    "Carson Hinzman": (83, 81.08),
    "Ashton Beers": (85, 83.01),
    "Justin Evans": (84, 81.81),
    "Bruce Mitchell": (84, 81.69),
}
MARGINALS = {"RBP": 0.364, "AWR": 0.248}


def _historical_evidence() -> dict[str, Any]:
    return {
        "provenance": "Recovered earlier Operation Pancake research supplied in current session",
        "status_vocabulary": [
            "HISTORICAL_RESEARCH_RESULT",
            "CURRENTLY_REPRODUCED",
            "CURRENTLY_VALIDATED",
            "UNVERIFIED_HISTORICAL_RESULT",
            "CONTRADICTED",
        ],
        "madden_population_count": {"value": 53, "status": "HISTORICAL_RESEARCH_RESULT"},
        "cfb_population_count": {"value": 12, "status": "HISTORICAL_RESEARCH_RESULT"},
        "cfb_ovr_range": {"value": [80, 85], "status": "HISTORICAL_RESEARCH_RESULT"},
        "formula_architecture": {
            "value": "OVR = (W - L) × 99 / (H - L)",
            "status": "HISTORICAL_RESEARCH_RESULT",
        },
        "performance": {
            "mae_approximately": {"value": 0.91, "status": "UNVERIFIED_HISTORICAL_RESULT"},
            "r_squared_approximately": {"value": 0.982, "status": "UNVERIFIED_HISTORICAL_RESULT"},
        },
        "marginal_displayed_ovr": {
            field: {"value": value, "status": "UNVERIFIED_HISTORICAL_RESULT"}
            for field, value in MARGINALS.items()
        },
        "missing_for_exact_reproduction": [
            "53-player Madden Center rows and target OVR values",
            "Exact attribute coefficients and calibration bounds L/H",
            "Original fitting and validation partitions",
            "Complete historical 12-Center CFB rating profiles",
        ],
    }


def _reconciliation(canonical: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_name = {card["player"]: card for card in canonical}
    rows = []
    for name in HISTORICAL_NAMES:
        card = by_name.get(name)
        historical = HISTORICAL_RESULTS.get(name)
        rows.append(
            {
                "historical_name": name,
                "canonical_observation_exists": card is not None,
                "canonical_card_id": card["card_id"] if card else None,
                "complete_canonical_profile": card is not None,
                "overall": card["overall"] if card else historical[0] if historical else None,
                "archetype": card["archetype"] if card else None,
                "program": card["program"] if card else None,
                "source_id": card["source_id"] if card else None,
                "ratings": card["attributes"] if card else None,
                "historical_additional_ratings_supplied": False,
                "status": "CURRENTLY_VALIDATED" if card else "UNVERIFIED_HISTORICAL_RESULT",
            }
        )
    return rows


def _cfb_comparison(reconciliation: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_name = {row["historical_name"]: row for row in reconciliation}
    return [
        {
            "player": name,
            "observed_cfb_ovr": observed,
            "archetype": by_name[name]["archetype"],
            "historical_madden_style_result": historical,
            "historical_residual_observed_minus_result": round(observed - historical, 2),
            "currently_reproduced_result": None,
            "reproduction_difference": None,
            "status": "UNVERIFIED_HISTORICAL_RESULT",
            "reason": (
                "Exact historical coefficients, calibration bounds, and full profile are absent."
            ),
        }
        for name, (observed, historical) in HISTORICAL_RESULTS.items()
    ]


def _saturday_evaluation(transitions: list[dict[str, Any]]) -> dict[str, Any]:
    rows = []
    for transition in transitions:
        known = {
            field: delta
            for field, delta in transition["attribute_deltas"].items()
            if field in MARGINALS
        }
        partial = sum(MARGINALS[field] * delta for field, delta in known.items())
        rows.append(
            {
                "transition_id": transition["transition_id"],
                "observed_ovr_movement": transition["delta_ovr"],
                "known_historical_marginal_deltas": known,
                "partial_displayed_ovr_movement": round(partial, 6),
                "evaluation": "PARTIALLY_COMPATIBLE" if partial > 0 else "INDETERMINATE",
                "contradicted": partial < 0,
                "complete_historical_score_movement_available": False,
            }
        )
    return {
        "historical_weights_refitted_to_saturday": False,
        "transitions_tested": len(rows),
        "partially_compatible_count": sum(
            row["evaluation"] == "PARTIALLY_COMPATIBLE" for row in rows
        ),
        "indeterminate_count": sum(row["evaluation"] == "INDETERMINATE" for row in rows),
        "contradicted_count": sum(row["contradicted"] for row in rows),
        "complete_compatibility_count": 0,
        "interpretation": (
            "Only recovered RBP/AWR marginals can be evaluated. Positive contributions in "
            "five bundles are directionally compatible; omitted coefficients prevent a "
            "complete test of any transition, including all sparse PBF/PBP/PBK cases."
        ),
        "transitions": rows,
    }


def build_historical_center_assessment(
    progression: dict[str, Any], saturday_matrix: list[dict[str, Any]]
) -> dict[str, Any]:
    """Integrate summary evidence without fabricating the missing historical datasets."""
    canonical = [card for card in progression["canonical_cards"] if card["position"] == "C"]
    reconciliation = _reconciliation(canonical)
    comparison = _cfb_comparison(reconciliation)
    saturday = _saturday_evaluation(saturday_matrix)
    return {
        "schema_version": 1,
        "phase": "Historical Center Recovery & Integrated Model Assessment",
        "historical_evidence": _historical_evidence(),
        "center_population_reconciliation": reconciliation,
        "madden_model_reproduction": {
            "reproduced": False,
            "population_count_validated": False,
            "formula_architecture_recorded": True,
            "mae_reproduced": None,
            "r_squared_reproduced": None,
            "coefficients_reproduced": False,
            "marginals_reproduced": False,
            "reason": (
                "Summary metrics are not sufficient to recreate data, coefficients, or calibration."
            ),
        },
        "cfb_center_comparison": comparison,
        "brady_small_investigation": {
            "observed_ovr": 84,
            "historical_madden_style_result": 80.10,
            "historical_residual": 3.90,
            "archetype": None,
            "full_rating_profile_available": False,
            "structural_outlier_currently_validated": False,
            "saturday_implications": (
                "Saturday confirms local Center sensitivity to PBK/PBF/PBP and includes AWR "
                "in positive bundles, but Brady's absent profile prevents attribution to "
                "AWR, ACC, IBL, archetype, or another group."
            ),
            "special_correction_created": False,
        },
        "saturday_independent_test": saturday,
        "archetype_analysis": {
            "observed_current_archetypes": {"Raw Strength": 3, "Pass Protector": 1},
            "universal_formula": "PLAUSIBLE_BUT_UNVALIDATED",
            "shared_weights_with_archetype_calibration": "PLAUSIBLE_BUT_UNIDENTIFIED",
            "archetype_specific_formulas": "UNSUPPORTED_BY_SAMPLE_SIZE",
            "preferred_research_architecture": (
                "Universal weights remain the simplest starting hypothesis; retain archetype "
                "calibration as a testable alternative when complete profiles are recovered."
            ),
        },
        "weight_evidence": {
            "STRONG_CONTROLLED_EVIDENCE": ["PBK", "PBF", "PBP"],
            "MODERATE_POPULATION_EVIDENCE": ["RBP", "AWR"],
            "WEAK_EVIDENCE": ["RBK", "RBF", "IBL", "LBK", "STR", "SPD", "ACC", "AGI", "COD"],
            "NO_IDENTIFIABLE_EFFECT": ["TGH", "RCK"],
            "caution": (
                "Strong means controlled local sensitivity, not an identified numeric weight. "
                "RBP/AWR marginal values remain unverified historical summaries."
            ),
        },
        "candidate_model_comparison": [
            {
                "architecture": "Historical Madden-style",
                "tested": False,
                "status": "INPUTS_MISSING",
            },
            {
                "architecture": "CFB recalibration of historical weights",
                "tested": False,
                "status": "WEIGHTS_AND_PROFILES_MISSING",
            },
            {
                "architecture": "Universal Center-specific model",
                "tested": False,
                "status": "INSUFFICIENT_STATIC_POPULATION",
            },
            {
                "architecture": "Shared weights + archetype modifier",
                "tested": False,
                "status": "INSUFFICIENT_ARCHETYPE_COVERAGE",
            },
        ],
        "best_current_center_model": None,
        "center_formula_status": "INSUFFICIENT EVIDENCE",
        "pc_app_readiness": {
            "center_model_usable": False,
            "research_evidence_usable": True,
            "status_to_expose": "INSUFFICIENT EVIDENCE — historical summaries unreproduced",
        },
        "formula_fitting_performed": False,
        "canonical_observations_modified": False,
        "historical_results_silently_promoted": False,
        "unknown_values_guessed": False,
    }


def write_historical_center_artifacts(directory: str | Path, analysis: dict[str, Any]) -> None:
    """Write deterministic recovery artifacts alongside, not over, prior research."""
    root = Path(directory)
    root.mkdir(parents=True, exist_ok=True)
    payloads = {
        "historical_center_evidence.json": analysis["historical_evidence"],
        "historical_center_population_reconciliation.json": analysis[
            "center_population_reconciliation"
        ],
        "historical_madden_center_reproduction.json": analysis["madden_model_reproduction"],
        "historical_cfb_center_comparison.json": analysis["cfb_center_comparison"],
        "historical_center_saturday_evaluation.json": analysis["saturday_independent_test"],
        "historical_center_brady_small.json": analysis["brady_small_investigation"],
        "historical_center_archetype_analysis.json": analysis["archetype_analysis"],
        "historical_center_weight_evidence.json": analysis["weight_evidence"],
        "historical_center_candidate_models.json": analysis["candidate_model_comparison"],
        "historical_center_formula_status.json": {
            "best_current_center_model": analysis["best_current_center_model"],
            "center_formula_status": analysis["center_formula_status"],
            "pc_app_readiness": analysis["pc_app_readiness"],
        },
        "historical_center_assessment_summary.json": {
            key: value
            for key, value in analysis.items()
            if key
            not in {
                "historical_evidence",
                "center_population_reconciliation",
                "madden_model_reproduction",
                "cfb_center_comparison",
                "saturday_independent_test",
                "brady_small_investigation",
                "archetype_analysis",
                "weight_evidence",
                "candidate_model_comparison",
            }
        },
    }
    for name, payload in payloads.items():
        (root / name).write_text(
            json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
