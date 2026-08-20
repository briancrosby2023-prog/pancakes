"""First OP-X-012E.15 calibration experiment: historical Center model vs CFB27 Alpha.

The historical model is intentionally evaluated as a frozen prior. This
module does not refit its weights or calibration before scoring CFB27 cards.
"""

from __future__ import annotations

from pathlib import Path

from operation_pancake.research.center_exact_validation import (
    CALIBRATION_HIGH,
    CALIBRATION_LOW,
    WEIGHTS,
)
from operation_pancake.research.cfb27_alpha_population import build_alpha_population
from operation_pancake.research.cfb27_e15_formula import (
    LinearFormulaCandidate,
    classify_candidate,
    classify_deployment,
    compare_rounding_rules,
    score_candidate,
)


def frozen_historical_center_candidate(rounding: str = "HALF_UP") -> LinearFormulaCandidate:
    """Translate the frozen historical Center hypothesis into E.15 form."""
    slope = 99 / (CALIBRATION_HIGH - CALIBRATION_LOW)
    intercept = -CALIBRATION_LOW * slope
    return LinearFormulaCandidate(
        name="FROZEN_HISTORICAL_CENTER",
        weights=tuple((field, float(weight)) for field, weight in WEIGHTS.items()),
        slope=slope,
        intercept=intercept,
        rounding=rounding,
    )


def build_center_calibration_assessment(root: Path) -> dict:
    """Score the frozen prior independently for every observed Center archetype."""
    alpha = build_alpha_population(root)
    centers = [
        card
        for card in alpha["cards"].values()
        if card.get("position") == "C"
        and card.get("extraction_status") == "COMPLETE"
        and card.get("overall") is not None
        and card.get("archetype")
    ]
    archetypes = sorted({str(card["archetype"]) for card in centers})
    candidate = frozen_historical_center_candidate()
    assessments = []
    for archetype in archetypes:
        result = score_candidate(candidate, centers, position="C", archetype=archetype)
        result["confidence"] = classify_candidate(result)
        result["deployment"] = classify_deployment(result)
        result["rounding_comparison"] = [
            {
                "rounding": row["rounding"],
                "exact_match_count": row["exact_match_count"],
                "exact_match_rate": row["exact_match_rate"],
                "mean_absolute_error": row["mean_absolute_error"],
                "maximum_absolute_error": row["maximum_absolute_error"],
                "deployment": classify_deployment(row),
            }
            for row in compare_rounding_rules(candidate, centers, position="C", archetype=archetype)
        ]
        assessments.append(result)

    return {
        "phase": "OP-X-012E.15",
        "experiment": "CENTER_FROZEN_HISTORICAL_PRIOR",
        "scientific_role": "CALIBRATION_AND_MODEL_DISCRIMINATION",
        "refit_before_evaluation": False,
        "alpha_population": alpha["summary"],
        "center_cards": len(centers),
        "center_archetypes": archetypes,
        "candidate_source": "center_exact_validation.FrozenHistoricalCenterModel",
        "candidate": {
            "weights": dict(candidate.weights),
            "slope": candidate.slope,
            "intercept": candidate.intercept,
            "rounding": candidate.rounding,
        },
        "assessments": assessments,
        "interpretation_policy": (
            "A strong fit supports inheritance of the historical Center prior; a weak fit "
            "rejects that frozen implementation for CFB27 but does not identify the "
            "replacement formula. "
            "GM_READY or GM_USABLE models may advance without requiring perfect reconstruction."
        ),
    }
