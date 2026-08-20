"""OP-X-050 contextual football value layer.

This module is deliberately non-numeric: context may explain a frozen Pancake
score but may never mutate score, rank, or percentile.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

EvidenceState = Literal["UNKNOWN", "POSITIVE", "NEUTRAL", "NEGATIVE", "MIXED"]
FitState = Literal["SUPPORTED", "PARTIAL", "CONFLICT", "UNKNOWN"]
Verdict = Literal["STRONG FIT", "GOOD FIT", "SPECIALIST FIT", "MIXED", "POOR FIT", "UNKNOWN"]

ROLES = {
    "QB": ("POCKET", "MOBILE_OFF_PLATFORM", "OPTION_RPO"),
    "RB": ("RUNNER", "RECEIVING", "POWER_MOVEMENT"),
    "WR": ("SEPARATOR", "VERTICAL", "POSSESSION_MISMATCH"),
    "TE": ("RECEIVING_MISMATCH", "BLOCKING", "HYBRID"),
    "OL": ("RUN", "PASS", "BALANCED"),
    "EDGE": ("FINESSE_RUSH", "POWER_RUSH", "CONTAIN_RUN", "RUSH_SPECIALIST"),
    "DT": ("RUN_STOPPER", "INTERIOR_PRESSURE", "BALANCED"),
    "LB": ("COVERAGE_USER", "RUSH", "RUN", "HYBRID"),
    "CB": ("MAN", "ZONE", "PRESS", "HYBRID"),
    "S": ("DEEP_RANGE", "BOX", "MAN_HYBRID", "USER"),
}
ASSIGNMENTS = ("MAN", "ZONE", "PRESS", "DEEP", "BOX", "CONTAIN", "PASS_RUSH", "RUN_DEFENSE", "RECEIVING", "BLOCKING", "OPTION", "POCKET", "RPO")
EVIDENCE_KINDS = ("OBSERVED_USAGE", "RECOMMENDATION", "REJECTION", "LIMITATION")
FLOOR_KINDS = ("PLAYABILITY_FLOOR", "COMPETITIVE_TARGET", "ELITE_TARGET", "ABILITY_REQUIREMENT")
EXPLANATIONS = ("ROLE", "SCHEME", "ANIMATION", "MOVEMENT", "PHYSICAL", "ABILITY", "BUILD", "MARKET", "UNKNOWN")

@dataclass(frozen=True)
class ContextEvidence:
    state: EvidenceState = "UNKNOWN"
    source: str | None = None
    observed_at: str | None = None
    evidence_type: str | None = None
    confidence: str = "UNKNOWN"
    notes: str | None = None

@dataclass(frozen=True)
class RealizedBuild:
    build_id: str
    actual_attributes: dict[str, int] = field(default_factory=dict)
    upgrade_path: str | None = None
    rolls: tuple[str, ...] = ()
    abilities: tuple[str, ...] = ()
    ap_allocation: dict[str, int] = field(default_factory=dict)
    chemistry: tuple[str, ...] = ()
    development_cost: int | None = None
    status: Literal["THEORETICAL", "OBSERVED"] = "THEORETICAL"
    source: str | None = None
    observed_at: str | None = None
    confidence: str = "UNKNOWN"

@dataclass(frozen=True)
class Deployment:
    canonical_position: str
    deployment_position: str | None = None
    specialist_slot: str | None = None
    deployment_role: str | None = None
    assignments: tuple[str, ...] = ()

@dataclass(frozen=True)
class AbilityContext:
    ability: str
    available: bool | None = None
    equipped: bool | None = None
    tier: str | None = None
    ap_cost: int | None = None
    role_relevance: EvidenceState = "UNKNOWN"
    scheme_relevance: EvidenceState = "UNKNOWN"
    competitive_evidence: ContextEvidence = field(default_factory=ContextEvidence)

@dataclass(frozen=True)
class FrozenBase:
    pancake_score: float | None
    position_rank: int | None
    position_percentile: float | None

@dataclass(frozen=True)
class ContextualEvaluation:
    base: FrozenBase
    deployment: Deployment
    role_fit: FitState = "UNKNOWN"
    scheme_fit: FitState = "UNKNOWN"
    behavior: EvidenceState = "UNKNOWN"
    physical_context: EvidenceState = "UNKNOWN"
    ability_ap_context: EvidenceState = "UNKNOWN"
    functional_risks: tuple[str, ...] = ()
    functional_advantages: tuple[str, ...] = ()
    evidence_confidence: str = "UNKNOWN"
    verdict: Verdict = "UNKNOWN"

    def frozen_identity(self) -> tuple[float | None, int | None, float | None]:
        return (self.base.pancake_score, self.base.position_rank, self.base.position_percentile)


def validate_role(position_family: str, role: str | None) -> None:
    if role is None:
        return
    if role not in ROLES.get(position_family, ()):
        raise ValueError(f"unsupported role {role!r} for {position_family!r}")


def validate_assignments(assignments: tuple[str, ...]) -> None:
    invalid = sorted(set(assignments) - set(ASSIGNMENTS))
    if invalid:
        raise ValueError(f"unsupported assignments: {invalid}")


def contextualize(base: FrozenBase, deployment: Deployment, **context: Any) -> ContextualEvaluation:
    """Construct context without arithmetic mutation of the frozen base."""
    validate_assignments(deployment.assignments)
    result = ContextualEvaluation(base=base, deployment=deployment, **context)
    if result.frozen_identity() != (base.pancake_score, base.position_rank, base.position_percentile):
        raise AssertionError("context mutated frozen evaluation")
    return result


def classify_residual(*, high_pancake: bool, adopted: bool, rejected: bool, explanation: str = "UNKNOWN") -> dict[str, Any]:
    if explanation not in EXPLANATIONS:
        raise ValueError("unsupported residual explanation")
    if adopted and rejected:
        category = "CONFLICTING_EVIDENCE"
    elif high_pancake and rejected:
        category = "HIGH_PANCAKE_REJECTION"
    elif (not high_pancake) and adopted:
        category = "LOW_PANCAKE_ADOPTION"
    else:
        category = "OTHER"
    return {"category": category, "candidate_explanation": explanation, "model_error_claimed": False}
