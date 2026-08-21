"""OP-X-050 contextual football value layered on OP-X-043A evidence.

Context explains a frozen Pancake evaluation; it never mutates score, rank,
percentile, market semantics, or purchase gates.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

from .competitive_evidence import (
    ABILITY_STATUSES,
    CONTEXT_ASSIGNMENTS,
    CONTEXT_EVIDENCE_KINDS,
    CONTEXT_FIT_STATES,
    CONTEXT_STATES,
    REGISTRY,
)
from .discovery import DiscoveryIntelligence
from .gm import GMProduct

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
POSITION_FAMILY = {
    "HB": "RB",
    "FB": "RB",
    "LT": "OL",
    "LG": "OL",
    "C": "OL",
    "RG": "OL",
    "RT": "OL",
    "LE": "EDGE",
    "RE": "EDGE",
    "MLB": "LB",
    "LOLB": "LB",
    "ROLB": "LB",
    "FS": "S",
    "SS": "S",
}
ASSIGNMENTS = tuple(sorted(CONTEXT_ASSIGNMENTS))
EVIDENCE_KINDS = tuple(sorted(CONTEXT_EVIDENCE_KINDS - {"UNKNOWN"}))
FLOOR_KINDS = ("PLAYABILITY_FLOOR", "COMPETITIVE_TARGET", "ELITE_TARGET", "ABILITY_REQUIREMENT")
EXPLANATIONS = (
    "ROLE",
    "SCHEME",
    "ANIMATION",
    "MOVEMENT",
    "PHYSICAL",
    "ABILITY",
    "BUILD",
    "MARKET",
    "UNKNOWN",
)


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
    ability_status: str = "UNKNOWN"
    tier: str | None = None
    ap_cost: int | None = None
    role_relevance: EvidenceState = "UNKNOWN"
    scheme_relevance: EvidenceState = "UNKNOWN"
    competitive_evidence: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        if self.ability_status not in ABILITY_STATUSES:
            raise ValueError("unsupported OP-X-043A ability status")


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


def _family(position: str) -> str:
    return POSITION_FAMILY.get(position, position)


def validate_role(position_family: str, role: str | None) -> None:
    if role is not None and role not in ROLES.get(_family(position_family), ()):
        raise ValueError(f"unsupported role {role!r} for {position_family!r}")


def validate_assignments(assignments: tuple[str, ...]) -> None:
    invalid = sorted(set(assignments) - CONTEXT_ASSIGNMENTS)
    if invalid:
        raise ValueError(f"unsupported assignments: {invalid}")


def contextualize(base: FrozenBase, deployment: Deployment, **context: Any) -> ContextualEvaluation:
    """Construct context without arithmetic mutation of the frozen base."""
    validate_assignments(deployment.assignments)
    validate_role(
        deployment.deployment_position or deployment.canonical_position, deployment.deployment_role
    )
    for field_name, allowed in (
        ("behavior", CONTEXT_STATES),
        ("physical_context", CONTEXT_STATES),
        ("ability_ap_context", CONTEXT_STATES),
        ("role_fit", CONTEXT_FIT_STATES),
        ("scheme_fit", CONTEXT_FIT_STATES),
    ):
        if field_name in context and context[field_name] not in allowed:
            raise ValueError(f"unsupported {field_name}")
    result = ContextualEvaluation(base=base, deployment=deployment, **context)
    if result.frozen_identity() != (
        base.pancake_score,
        base.position_rank,
        base.position_percentile,
    ):
        raise AssertionError("context mutated frozen evaluation")
    return result


def _combined(
    records: list[dict[str, Any]],
    field_name: str,
    unknown: str = "UNKNOWN",
    mixed: str = "MIXED",
) -> str:
    values = {row.get(field_name, unknown) for row in records} - {unknown}
    if not values:
        return unknown
    return next(iter(values)) if len(values) == 1 else mixed


def contextual_report(
    root: Path,
    card_id: str,
    *,
    deployment_position: str | None = None,
    role: str | None = None,
    assignments: tuple[str, ...] = (),
    build_id: str | None = None,
) -> dict[str, Any]:
    """Expose frozen numerical value alongside OP-X-043A contextual evidence."""
    lookup = GMProduct(root).lookup(card_id=card_id)
    if "card" not in lookup:
        return lookup
    evaluation = lookup["evaluation"]
    registry = root / REGISTRY
    records = json.loads(registry.read_text(encoding="utf-8")) if registry.exists() else []
    matched = [
        row for row in records if row.get("card_resolution", {}).get("canonical_card_id") == card_id
    ]
    if build_id:
        matched = [row for row in matched if row.get("build_id") in {build_id, "UNKNOWN"}]
    canonical = lookup["card"]["position"]
    deployment = Deployment(
        canonical, deployment_position or canonical, deployment_role=role, assignments=assignments
    )
    discovery = DiscoveryIntelligence(root).by_id.get(card_id, {})
    base = FrozenBase(
        evaluation.get("score"),
        evaluation.get("position_rank"),
        discovery.get("position_percentile"),
    )
    risks = tuple(sorted({item for row in matched for item in row.get("functional_risks", [])}))
    advantages = tuple(
        sorted({item for row in matched for item in row.get("functional_advantages", [])})
    )
    result = contextualize(
        base,
        deployment,
        role_fit=_combined(matched, "role_fit", mixed="CONFLICT"),
        scheme_fit=_combined(matched, "scheme_fit", mixed="CONFLICT"),
        behavior=_combined(matched, "behavior_state"),
        functional_risks=risks,
        functional_advantages=advantages,
        evidence_confidence=_combined(matched, "confidence"),
    )
    unknowns = [
        name
        for name, value in (
            ("role_fit", result.role_fit),
            ("scheme_fit", result.scheme_fit),
            ("behavior", result.behavior),
        )
        if value == "UNKNOWN"
    ]
    return {
        "status": "CONTEXTUALIZED",
        "card": lookup["card"],
        "frozen_evaluation": asdict(base),
        "context": asdict(result),
        "evidence_records": len(matched),
        "source_families": sorted({row["source_family"] for row in matched}),
        "unknowns": unknowns,
        "score_modified": False,
        "market_semantics_modified": False,
        "buy_gates_modified": False,
    }


def classify_residual(
    *, high_pancake: bool, adopted: bool, rejected: bool, explanation: str = "UNKNOWN"
) -> dict[str, Any]:
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
    return {
        "category": category,
        "candidate_explanation": explanation,
        "model_error_claimed": False,
    }
