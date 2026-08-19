"""Deterministic candidate-model scoring for OP-X-012E.15.

This module deliberately separates model evaluation from model discovery. A
candidate must be stated before it is scored; low error is evidence for a
candidate, not proof that the candidate is EA's implementation.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence


ROUNDING_RULES = ("HALF_UP", "FLOOR", "CEIL")
CONFIDENCE_LEVELS = (
    "EXACT",
    "HIGH_CONFIDENCE",
    "PROVISIONAL",
    "UNDERDETERMINED",
    "REJECTED",
)
DEPLOYMENT_LEVELS = ("GM_READY", "GM_USABLE", "RESEARCH_REQUIRED")


@dataclass(frozen=True, slots=True)
class LinearFormulaCandidate:
    """A declared linear OVR hypothesis with explicit calibration."""

    name: str
    weights: tuple[tuple[str, float], ...]
    slope: float = 1.0
    intercept: float = 0.0
    rounding: str = "HALF_UP"

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("candidate name is required")
        if not self.weights:
            raise ValueError("candidate weights are required")
        if self.rounding not in ROUNDING_RULES:
            raise ValueError(f"unsupported rounding rule: {self.rounding}")
        if sum(weight for _, weight in self.weights) == 0:
            raise ValueError("candidate weight total must be non-zero")

    @property
    def attributes(self) -> tuple[str, ...]:
        return tuple(field for field, _ in self.weights)

    def raw_component(self, ratings: Mapping[str, int]) -> float:
        missing = [field for field, _ in self.weights if field not in ratings]
        if missing:
            raise ValueError(f"missing candidate attributes: {missing}")
        total = sum(weight for _, weight in self.weights)
        return sum(ratings[field] * weight for field, weight in self.weights) / total

    def continuous_score(self, ratings: Mapping[str, int]) -> float:
        return self.slope * self.raw_component(ratings) + self.intercept

    def predict(self, ratings: Mapping[str, int]) -> int:
        value = self.continuous_score(ratings)
        if self.rounding == "HALF_UP":
            return math.floor(value + 0.5)
        if self.rounding == "FLOOR":
            return math.floor(value)
        return math.ceil(value)


def _eligible_rows(cards: Iterable[Mapping], position: str, archetype: str) -> list[Mapping]:
    rows = []
    for card in cards:
        if card.get("position") != position or card.get("archetype") != archetype:
            continue
        if card.get("overall") is None or not isinstance(card.get("displayed_ratings"), Mapping):
            continue
        rows.append(card)
    return sorted(rows, key=lambda row: str(row.get("external_card_id", "")))


def score_candidate(
    candidate: LinearFormulaCandidate,
    cards: Iterable[Mapping],
    *,
    position: str,
    archetype: str,
) -> dict:
    """Score a predeclared formula against one position/archetype population."""
    population = _eligible_rows(cards, position, archetype)
    scored = []
    skipped = []
    for card in population:
        ratings = card["displayed_ratings"]
        missing = [field for field in candidate.attributes if field not in ratings]
        card_id = str(card.get("external_card_id", ""))
        if missing:
            skipped.append({"card_id": card_id, "missing_attributes": sorted(missing)})
            continue
        observed = int(card["overall"])
        continuous = candidate.continuous_score(ratings)
        predicted = candidate.predict(ratings)
        error = predicted - observed
        scored.append(
            {
                "card_id": card_id,
                "observed_ovr": observed,
                "predicted_ovr": predicted,
                "continuous_score": round(continuous, 10),
                "error": error,
                "absolute_error": abs(error),
            }
        )

    count = len(scored)
    exact = sum(row["absolute_error"] == 0 for row in scored)
    mae = sum(row["absolute_error"] for row in scored) / count if count else None
    max_error = max((row["absolute_error"] for row in scored), default=None)
    residuals = [row for row in scored if row["absolute_error"]]
    return {
        "candidate": candidate.name,
        "position": position,
        "archetype": archetype,
        "attributes": list(candidate.attributes),
        "weights": {field: weight for field, weight in candidate.weights},
        "calibration": {"slope": candidate.slope, "intercept": candidate.intercept},
        "rounding": candidate.rounding,
        "population_cards": len(population),
        "scored_cards": count,
        "skipped_cards": skipped,
        "exact_match_count": exact,
        "exact_match_rate": round(exact / count, 10) if count else None,
        "mean_absolute_error": round(mae, 10) if mae is not None else None,
        "maximum_absolute_error": max_error,
        "residual_count": len(residuals),
        "residuals": residuals,
    }


def compare_rounding_rules(
    candidate: LinearFormulaCandidate,
    cards: Iterable[Mapping],
    *,
    position: str,
    archetype: str,
) -> list[dict]:
    """Evaluate identical weights/calibration under each supported quantizer."""
    results = []
    for rule in ROUNDING_RULES:
        variant = LinearFormulaCandidate(
            name=f"{candidate.name}:{rule}",
            weights=candidate.weights,
            slope=candidate.slope,
            intercept=candidate.intercept,
            rounding=rule,
        )
        results.append(score_candidate(variant, cards, position=position, archetype=archetype))
    return sorted(
        results,
        key=lambda row: (
            -(row["exact_match_rate"] or 0),
            row["mean_absolute_error"] if row["mean_absolute_error"] is not None else math.inf,
            row["rounding"],
        ),
    )


def classify_candidate(result: Mapping, *, contradictions: int = 0) -> str:
    """Apply conservative scientific evidence labels to a scored candidate."""
    count = int(result.get("scored_cards") or 0)
    exact_rate = result.get("exact_match_rate")
    mae = result.get("mean_absolute_error")
    if count == 0 or exact_rate is None or mae is None:
        return "UNDERDETERMINED"
    if contradictions:
        return "REJECTED"
    if exact_rate == 1.0:
        return "EXACT" if count >= 15 else "UNDERDETERMINED"
    if count >= 30 and exact_rate >= 0.95 and mae <= 0.05:
        return "HIGH_CONFIDENCE"
    if count >= 15 and exact_rate >= 0.75 and mae <= 0.35:
        return "PROVISIONAL"
    return "REJECTED"


def classify_deployment(result: Mapping, *, systematic_failure: bool = False) -> str:
    """Classify practical GM usefulness without requiring scientific perfection.

    >=95% exact agreement is ready when residuals are small and non-systematic.
    90-95% is usable when misses remain predominantly small. Anything lower
    remains research-required. This intentionally lets useful models ship.
    """
    count = int(result.get("scored_cards") or 0)
    exact_rate = result.get("exact_match_rate")
    mae = result.get("mean_absolute_error")
    max_error = result.get("maximum_absolute_error")
    if count == 0 or exact_rate is None or mae is None or systematic_failure:
        return "RESEARCH_REQUIRED"
    if exact_rate >= 0.95 and mae <= 0.10 and (max_error is None or max_error <= 2):
        return "GM_READY"
    if exact_rate >= 0.90 and mae <= 0.20 and (max_error is None or max_error <= 2):
        return "GM_USABLE"
    return "RESEARCH_REQUIRED"


def rank_candidates(results: Sequence[Mapping]) -> list[Mapping]:
    """Return deterministic best-first candidate ordering without declaring a winner."""
    return sorted(
        results,
        key=lambda row: (
            -(row.get("exact_match_rate") or 0),
            row.get("mean_absolute_error") if row.get("mean_absolute_error") is not None else math.inf,
            row.get("maximum_absolute_error") if row.get("maximum_absolute_error") is not None else math.inf,
            str(row.get("candidate", "")),
        ),
    )
