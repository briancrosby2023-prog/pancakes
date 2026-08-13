"""Shared interfaces for research-aware positional card evaluation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class EvaluationResult:
    """One transparent evaluation with uncertainty kept visible."""

    position: str
    displayed_ovr: int
    effective_ovr: float | None
    hidden_band: str | None
    archetype: str
    model_name: str
    model_status: str
    confidence: str
    attribute_contributions: dict[str, float]
    trigger_stats: tuple[str, ...]
    strengths: tuple[str, ...]
    weaknesses: tuple[str, ...]
    same_ovr_comparison: str | None
    next_ovr_proximity: float | None
    evaluation_grade: str
    limitations: tuple[str, ...]


class PositionEvaluator(Protocol):
    """Contract implemented by position-specific research evaluators."""

    position: str

    def evaluate(
        self, displayed_ovr: int, archetype: str, ratings: dict[str, int]
    ) -> EvaluationResult:
        """Evaluate one profile while exposing model status and uncertainty."""
