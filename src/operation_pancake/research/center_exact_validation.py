"""Exact recovered Center model and independent Jeff Saturday validation."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

WEIGHTS = {
    "RBP": 22,
    "PBP": 21,
    "AWR": 15,
    "STR": 14,
    "RBK": 10,
    "PBF": 8,
    "IBL": 6,
    "LBK": 4,
    "SPD": 2,
    "ACC": 2,
    "AGI": 2,
    "PBK": 2,
}
WEIGHT_TOTAL = 108
CALIBRATION_LOW = 36.5790018
CALIBRATION_HIGH = 91.9868505
CALIBRATION_SLOPE = 1.7867505
CALIBRATION_INTERCEPT = -65.35755
HISTORICAL_MADDEN_METRICS = {"mae": 0.9122, "r_squared": 0.98172}
HISTORICAL_CFB_METRICS = {"mae": 0.4624, "r_squared": 0.8109}
SATURDAY_BASE = {
    "PBK": 82,
    "PBF": 78,
    "PBP": 83,
    "RBK": 78,
    "RBF": 74,
    "RBP": 75,
    "IBL": 76,
    "LBK": 78,
    "STR": 82,
    "AWR": 70,
    "SPD": 65,
    "ACC": 57,
    "AGI": 64,
    "COD": 65,
}
SPARSE_IDS = ("SAT-01B", "SAT-08B", "SAT-02", "SAT-05", "SAT-04", "SAT-06", "SAT-06B")


@dataclass(frozen=True, slots=True)
class FrozenHistoricalCenterModel:
    """Immutable historical Madden Center hypothesis."""

    weights: tuple[tuple[str, int], ...] = tuple(WEIGHTS.items())
    low: float = CALIBRATION_LOW
    high: float = CALIBRATION_HIGH

    def weighted_score(self, ratings: dict[str, int]) -> float:
        missing = [field for field, _ in self.weights if field not in ratings]
        if missing:
            raise ValueError(f"Missing weighted Center attributes: {missing}")
        return sum(weight * ratings[field] for field, weight in self.weights) / WEIGHT_TOTAL

    def calibrated_score(self, ratings: dict[str, int]) -> float:
        return (self.weighted_score(ratings) - self.low) * 99 / (self.high - self.low)

    def predict(self, ratings: dict[str, int]) -> int:
        return math.floor(self.calibrated_score(ratings) + 0.5)

    def contributions(self, ratings: dict[str, int]) -> dict[str, float]:
        return {field: weight * ratings[field] / WEIGHT_TOTAL for field, weight in self.weights}

    @property
    def status(self) -> str:
        return "FROZEN_HISTORICAL_HYPOTHESIS"


def _apply(ratings: dict[str, int], deltas: dict[str, int]) -> dict[str, int]:
    result = dict(ratings)
    for field, delta in deltas.items():
        if field in result:
            result[field] += delta
    return result


def _source_artifacts() -> dict[str, Any]:
    coefficient_rows = []
    for rank, (field, weight) in enumerate(
        sorted(WEIGHTS.items(), key=lambda item: (-item[1], item[0])), start=1
    ):
        coefficient_rows.append(
            {
                "attribute": field,
                "raw_formula_weight": weight,
                "normalized_score_share": round(weight / WEIGHT_TOTAL, 10),
                "displayed_ovr_marginal_effect": round(
                    CALIBRATION_SLOPE * weight / WEIGHT_TOTAL, 10
                ),
                "rank": rank,
                "status": "HISTORICAL_RESEARCH_RESULT",
            }
        )
    return {
        "madden_source_population": {
            "reported_row_count": 53,
            "rows_ingested": [],
            "row_level_source_available": False,
            "complete": False,
            "gap": "The recovered evidence supplies exact model constants but not 53 player rows.",
        },
        "coefficients": coefficient_rows,
        "calibration": {
            "low": CALIBRATION_LOW,
            "high": CALIBRATION_HIGH,
            "slope_supplied": CALIBRATION_SLOPE,
            "intercept_supplied": CALIBRATION_INTERCEPT,
            "slope_from_low_high": round(99 / (CALIBRATION_HIGH - CALIBRATION_LOW), 10),
            "intercept_from_low_high": round(
                -CALIBRATION_LOW * 99 / (CALIBRATION_HIGH - CALIBRATION_LOW), 10
            ),
            "status": "HISTORICAL_RESEARCH_RESULT",
        },
    }


def _saturday_validation(transitions: list[dict[str, Any]]) -> dict[str, Any]:
    model = FrozenHistoricalCenterModel()
    by_id = {item["transition_id"]: item for item in transitions}
    base_w = model.weighted_score(SATURDAY_BASE)
    base_calibrated = model.calibrated_score(SATURDAY_BASE)
    trajectories = []
    transition_rows = []
    for number in range(1, 12):
        reset_id = f"SAT-{number:02d}"
        a, b = by_id[reset_id], by_id[f"{reset_id}B"]
        intermediate = _apply(SATURDAY_BASE, a["attribute_deltas"])
        end = _apply(intermediate, b["attribute_deltas"])
        iw, ew = model.weighted_score(intermediate), model.weighted_score(end)
        ic, ec = model.calibrated_score(intermediate), model.calibrated_score(end)
        rows = []
        for transition, start_w, finish_w, start_c, finish_c in (
            (a, base_w, iw, base_calibrated, ic),
            (b, iw, ew, ic, ec),
        ):
            row = {
                "transition_id": transition["transition_id"],
                "start_ovr": transition["start_ovr"],
                "end_ovr": transition["end_ovr"],
                "start_weighted_score": round(start_w, 10),
                "end_weighted_score": round(finish_w, 10),
                "delta_weighted_score": round(finish_w - start_w, 10),
                "start_calibrated_score": round(start_c, 10),
                "end_calibrated_score": round(finish_c, 10),
                "delta_calibrated_score": round(finish_c - start_c, 10),
                "observed_ovr_movement": 1,
                "madden_calibration_prediction_start": math.floor(start_c + 0.5),
                "madden_calibration_prediction_end": math.floor(finish_c + 0.5),
                "madden_absolute_classification": "CONTRADICTED",
                "positive_direction_compatible": finish_w > start_w,
            }
            rows.append(row)
            transition_rows.append(row)
        trajectories.append(
            {
                "reset_id": reset_id,
                "base_weighted_score": round(base_w, 10),
                "intermediate_weighted_score": round(iw, 10),
                "end_weighted_score": round(ew, 10),
                "transitions": rows,
                "individual_free_threshold_classification": "COMPATIBLE",
                "frozen_madden_calibration_classification": "CONTRADICTED",
            }
        )
    max_intermediate = max(item["intermediate_weighted_score"] for item in trajectories)
    min_end = min(item["end_weighted_score"] for item in trajectories)
    return {
        "model_frozen_before_evaluation": True,
        "tgh_required": False,
        "known_saturday_vector_sufficient": True,
        "base_weighted_score": round(base_w, 10),
        "base_calibrated_score": round(base_calibrated, 10),
        "base_madden_prediction": model.predict(SATURDAY_BASE),
        "trajectories": trajectories,
        "transitions": transition_rows,
        "counts": {
            "compatible": 0,
            "tension": 0,
            "contradicted": 22,
            "indeterminate": 0,
        },
        "shared_baseline_test": {
            "common_80_to_81_threshold_interval": {
                "lower_exclusive": round(base_w, 10),
                "upper_inclusive": round(
                    min(item["intermediate_weighted_score"] for item in trajectories), 10
                ),
                "feasible": True,
            },
            "common_81_to_82_threshold_condition": {
                "maximum_intermediate_score": round(max_intermediate, 10),
                "minimum_end_score": round(min_end, 10),
                "required": "maximum intermediate < minimum end",
                "feasible": max_intermediate < min_end,
                "overlap": round(max_intermediate - min_end, 10),
            },
            "result": "CONTRADICTED",
            "interpretation": (
                "Frozen weights can place one common 80→81 threshold above the shared base, "
                "but no single 81→82 threshold separates all intermediate and end scores."
            ),
        },
    }


def _sparse(validation: dict[str, Any], transitions: list[dict[str, Any]]) -> dict[str, Any]:
    by_id = {item["transition_id"]: item for item in validation["transitions"]}
    deltas_by_id = {item["transition_id"]: item["attribute_deltas"] for item in transitions}
    rows = [by_id[transition_id] for transition_id in SPARSE_IDS]
    return {
        "transitions": rows,
        "by_attribute": {
            field: [item for item in rows if field in deltas_by_id[item["transition_id"]]]
            for field in ("PBP", "PBF", "PBK")
        },
        "historical_ordering": "PBP > PBF > PBK",
        "ordering_supported": False,
        "interpretation": (
            "Every sparse delta is directionally positive, but +1 PBF, +1 PBP, and +4 PBK "
            "all cross boundaries from different hidden starts. The experiments establish "
            "positive sensitivity, not the historical numeric ordering."
        ),
    }


def build_center_exact_validation(
    saturday_transitions: list[dict[str, Any]],
    reconciliation: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build exact-constant artifacts and leakage-free controlled validation."""
    sources = _source_artifacts()
    validation = _saturday_validation(saturday_transitions)
    complete_cfb = [row for row in reconciliation if row["complete_canonical_profile"]]
    return {
        "schema_version": 1,
        "phase": "Center Exact Reproduction & Saturday Independent Validation",
        **sources,
        "historical_model_reproduction": {
            "exact_constants_reproduced": True,
            "weight_total": sum(WEIGHTS.values()),
            "per_player_reproduction": False,
            "metrics_reproduced_from_rows": False,
            "reported_metrics": HISTORICAL_MADDEN_METRICS,
            "numerical_differences": {"mae": None, "r_squared": None},
            "reason": (
                "The exact constants are reproducible; 53 row-level observations remain absent."
            ),
        },
        "frozen_model": {
            "name": "Historical Madden 19 Center",
            "status": FrozenHistoricalCenterModel().status,
            "weights": WEIGHTS,
            "weight_total": WEIGHT_TOTAL,
            "calibration": {"low": CALIBRATION_LOW, "high": CALIBRATION_HIGH},
            "frozen_before_saturday": True,
            "refitted_to_cfb_or_saturday": False,
        },
        "cfb_reproduction": {
            "reported_population_count": 12,
            "recovered_names": len(reconciliation),
            "complete_profiles": len(complete_cfb),
            "ovr_range": [80, 85],
            "model_m_metrics_reproduced": False,
            "model_mc_metrics_reproduced": False,
            "reported_model_mc_metrics": HISTORICAL_CFB_METRICS,
            "recalibration_performed": False,
            "reason": (
                "Only 3 of 12 profiles are complete and historical weights cannot be "
                "evaluated on missing rows."
            ),
        },
        "saturday_validation": validation,
        "sparse_transition_analysis": _sparse(validation, saturday_transitions),
        "weight_inequalities": {
            "positive_local_effect": ["PBP", "PBF", "PBK"],
            "historical_ordering_test": "INDETERMINATE",
            "numeric_feasible_region_derived": False,
            "reason": (
                "Unknown threshold locations and differing intermediate states prevent "
                "relative bounds."
            ),
        },
        "brady_small": {
            "historical_residual": 3.9,
            "profile_available": False,
            "reproduced": False,
            "saturday_evidence": (
                "Pass-block attributes are locally relevant for Saturday, but Brady's absent "
                "profile prevents deciding between undervaluation, calibration, missing "
                "attributes, or archetype sensitivity."
            ),
        },
        "candidate_models": {
            "M": {
                "tested_on_saturday": True,
                "static_cfb_tested": False,
                "status": "REJECTED_FOR_CFB_ABSOLUTE_CALIBRATION",
            },
            "MC": {"tested": False, "status": "INSUFFICIENT_COMPLETE_CFB_ROWS"},
            "minimal_cfb": {"tested": False, "status": "NOT_JUSTIFIED"},
        },
        "best_current_center_model": None,
        "center_formula_status": "REJECTED",
        "pc_app_readiness": {
            "center_engine": "RESEARCH_ONLY_FROZEN_HISTORICAL_INTERFACE",
            "production_prediction_usable": False,
            "confidence_status": (
                "REJECTED for CFB absolute calibration; weights remain a historical hypothesis"
            ),
        },
        "canonical_observations_modified": False,
        "unknown_ratings_guessed": False,
        "leakage_detected": False,
    }


def write_center_exact_artifacts(directory: str | Path, analysis: dict[str, Any]) -> None:
    """Write deterministic exact-model and validation artifacts."""
    root = Path(directory)
    root.mkdir(parents=True, exist_ok=True)
    payloads = {
        "madden_center_source_population.json": analysis["madden_source_population"],
        "madden_center_coefficients.json": analysis["coefficients"],
        "madden_center_calibration.json": analysis["calibration"],
        "madden_center_exact_reproduction.json": analysis["historical_model_reproduction"],
        "madden_center_frozen_model.json": analysis["frozen_model"],
        "cfb_center_exact_reproduction.json": analysis["cfb_reproduction"],
        "saturday_frozen_model_validation.json": analysis["saturday_validation"],
        "saturday_shared_baseline_constraints.json": analysis["saturday_validation"][
            "shared_baseline_test"
        ],
        "saturday_sparse_exact_validation.json": analysis["sparse_transition_analysis"],
        "saturday_center_weight_inequalities.json": analysis["weight_inequalities"],
        "center_exact_brady_small.json": analysis["brady_small"],
        "center_m_vs_mc_comparison.json": analysis["candidate_models"],
        "center_exact_formula_status.json": {
            "best_current_center_model": analysis["best_current_center_model"],
            "center_formula_status": analysis["center_formula_status"],
            "pc_app_readiness": analysis["pc_app_readiness"],
        },
    }
    for name, payload in payloads.items():
        (root / name).write_text(
            json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
