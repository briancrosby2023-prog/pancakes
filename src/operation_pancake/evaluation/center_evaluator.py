"""Research-only Center evaluator backed by the frozen historical reference."""

from __future__ import annotations

from operation_pancake.evaluation.position_evaluator import EvaluationResult
from operation_pancake.research.center_exact_validation import FrozenHistoricalCenterModel


class CenterResearchEvaluator:
    """Expose useful historical scoring without presenting a production CFB formula."""

    position = "C"
    model_status = "INSUFFICIENT_EVIDENCE"

    def __init__(self) -> None:
        self._model = FrozenHistoricalCenterModel()

    def evaluate(
        self, displayed_ovr: int, archetype: str, ratings: dict[str, int]
    ) -> EvaluationResult:
        """Return a transparent reference score with unsupported outputs withheld."""
        score = self._model.weighted_score(ratings)
        contributions = self._model.contributions(ratings)
        ranked = sorted(contributions, key=lambda field: (-contributions[field], field))
        return EvaluationResult(
            position=self.position,
            displayed_ovr=displayed_ovr,
            effective_ovr=round(score, 6),
            hidden_band=None,
            archetype=archetype,
            model_name="Historical Madden Center weighted-score reference",
            model_status=self.model_status,
            confidence="LOW",
            attribute_contributions={
                field: round(value, 6) for field, value in contributions.items()
            },
            trigger_stats=("PBK", "PBF", "PBP"),
            strengths=tuple(ranked[:3]),
            weaknesses=tuple(reversed(ranked[-3:])),
            same_ovr_comparison=None,
            next_ovr_proximity=None,
            evaluation_grade="UNAVAILABLE",
            limitations=(
                "Reference score is not a validated CFB effective OVR.",
                "Hidden band, same-OVR rank, proximity, and grade lack sufficient evidence.",
                "No identifiable regular-card validation population is available.",
            ),
        )
