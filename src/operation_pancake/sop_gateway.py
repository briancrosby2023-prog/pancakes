"""Fail-closed decision gateway for consequential Operation Pancake work."""
from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Protocol

from operation_pancake.sop_policy import (
    TERMINAL_NEXT_ACTIONS,
    missing_predecision_codes,
    predecision_state,
    validate_state,
)
from operation_pancake.cross_surface_control import (
    HypothesisBlocked,
    HypothesisLedger,
    trusted_basis_errors,
    validate_typed_evidence,
    validate_user_test_boundary,
)
from operation_pancake.authority_guard import (
    AuthorityGuardError,
    AuthorityGuardSnapshot,
    load_authority_guard,
)

PREFLIGHT_REQUIRED = "PREFLIGHT_REQUIRED"
PREFLIGHT_PASS = "PREFLIGHT_PASS"
DECISION_ALLOWED = "DECISION_ALLOWED"
ACTION_ALLOWED = "ACTION_ALLOWED"
BLOCKED_EXTERNAL = "BLOCKED_EXTERNAL"
EVIDENCE_GAP = "EVIDENCE_GAP"
COMPLETE = "COMPLETE"


class SOPGatewayError(RuntimeError):
    """Base class for fail-closed gateway errors."""


class DecisionTransportUnavailable(SOPGatewayError):
    """Raised when no model transport is configured."""


class ActionBlocked(SOPGatewayError):
    """Raised when an action is not authorized by a decision packet."""


class StateChanged(ActionBlocked):
    """Raised when project state changed after the decision was made."""


class DecisionProvider(Protocol):
    def decide(self, request: str, context: Mapping[str, Any]) -> Mapping[str, Any]:
        """Return a structured plan after deterministic preflight has passed."""


class NoDecisionProvider:
    """Fail-closed transport used until a real model provider is explicitly configured."""

    def decide(self, request: str, context: Mapping[str, Any]) -> Mapping[str, Any]:
        raise DecisionTransportUnavailable(
            "No decision-model transport is configured. A programmatic model credential "
            "is required before live model decisions can run through the gateway."
        )


@dataclass(frozen=True)
class DecisionPacket:
    decision_id: str
    mission: str
    request: str
    map_evidence: tuple[str, ...]
    history_evidence: tuple[str, ...]
    research_evidence: tuple[str, ...]
    capability_evidence: tuple[str, ...]
    proposed_plan: str
    allowed_actions: tuple[str, ...]
    blocked_actions: tuple[str, ...]
    decision_status: str
    next_action: str
    missing_requirements: tuple[str, ...] = ()
    gate_errors: tuple[str, ...] = ()
    state_fingerprint: str | None = None
    provider_called: bool = False
    evidence_types: tuple[str, ...] = ()
    contradiction_keys: tuple[str, ...] = ()
    obstacle_classification: str = "NONE"
    alternatives_considered: tuple[str, ...] = ()
    selected_reason: str = ""
    implementation_basis_fact_keys: tuple[str, ...] = ()
    mutation_requested: bool = False
    hypothesis_id: str | None = None
    user_action_required: bool = False
    remaining_executable_routes: tuple[str, ...] = ()
    selected_route_id: str | None = None
    remaining_route_ids: tuple[str, ...] = ()
    authority_guard_fingerprint: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ActionAuthorization:
    decision_id: str
    action: str
    status: str = ACTION_ALLOWED


class DecisionRecordStore:
    def __init__(self, root: Path):
        self.root = root

    def _path(self, decision_id: str) -> Path:
        safe = decision_id.strip()
        if not safe or any(ch not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for ch in safe):
            raise ValueError("decision_id contains unsupported characters")
        return self.root / f"{safe}.json"

    def save(self, packet: DecisionPacket) -> Path:
        self.root.mkdir(parents=True, exist_ok=True)
        target = self._path(packet.decision_id)
        temporary = target.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(packet.as_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
        temporary.replace(target)
        return target

    def load(self, decision_id: str) -> DecisionPacket:
        payload = json.loads(self._path(decision_id).read_text(encoding="utf-8"))
        tuple_fields = {
            "map_evidence",
            "history_evidence",
            "research_evidence",
            "capability_evidence",
            "allowed_actions",
            "blocked_actions",
            "missing_requirements",
            "gate_errors",
            "evidence_types",
            "contradiction_keys",
            "alternatives_considered",
            "implementation_basis_fact_keys",
            "remaining_executable_routes",
            "remaining_route_ids",
        }
        for field in tuple_fields:
            payload[field] = tuple(payload.get(field, ()))
        payload.setdefault("selected_route_id", None)
        payload.setdefault("authority_guard_fingerprint", None)
        return DecisionPacket(**payload)


def state_fingerprint(snapshot: Any) -> str:
    encoded = json.dumps(snapshot, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _clean_items(values: Sequence[str] | None) -> tuple[str, ...]:
    return tuple(dict.fromkeys(str(item).strip() for item in (values or ()) if str(item).strip()))


class SOPDecisionGateway:
    def __init__(
        self,
        *,
        provider: DecisionProvider,
        store: DecisionRecordStore,
        strict_evidence: bool = False,
        hypotheses: HypothesisLedger | None = None,
        authority_path: Path | None = None,
        require_authority_guard: bool = False,
    ):
        self.provider = provider
        self.store = store
        self.strict_evidence = strict_evidence
        self.hypotheses = hypotheses
        self.authority_path = Path(authority_path) if authority_path is not None else None
        self.require_authority_guard = require_authority_guard

    def request_decision(
        self,
        *,
        mission: str,
        request: str,
        evidence: Mapping[str, Sequence[str]],
        state_snapshot: Any = None,
        decision_id: str | None = None,
        mutation_requested: bool = False,
        hypothesis_id: str | None = None,
        new_evidence: Sequence[str] = (),
    ) -> DecisionPacket:
        request = request.strip()
        mission = mission.strip()
        if not request:
            raise ValueError("request is required")
        if not mission:
            raise ValueError("mission is required")

        decision_id = decision_id or f"decision-{uuid.uuid4().hex}"
        typed_gate = None
        plain_evidence: Mapping[str, Sequence[str]] = evidence
        cross_surface_errors: list[str] = []
        evidence_types: tuple[str, ...] = ()
        contradiction_keys: tuple[str, ...] = ()
        authority_guard: AuthorityGuardSnapshot | None = None
        evidence_for_validation: Mapping[str, Sequence[Any]] = evidence
        if self.strict_evidence:
            staged_evidence = {
                stage: list(evidence.get(stage, ()))
                for stage in ("map", "history", "research", "capabilities")
            }
            try:
                authority_guard = load_authority_guard(
                    self.authority_path,
                    mission,
                    required=self.require_authority_guard,
                )
            except AuthorityGuardError as exc:
                cross_surface_errors.append(str(exc))
            if authority_guard is not None:
                staged_evidence["history"].extend(authority_guard.evidence_items())
            evidence_for_validation = staged_evidence
            typed_gate = validate_typed_evidence(evidence_for_validation)
            plain_evidence = typed_gate.plain()
            cross_surface_errors.extend(typed_gate.errors)
            evidence_types = typed_gate.kinds()
            contradiction_keys = typed_gate.contradiction_keys
        if mutation_requested and hypothesis_id and self.hypotheses is not None:
            try:
                self.hypotheses.authorize_attempt(
                    hypothesis_id,
                    new_evidence=new_evidence,
                )
            except HypothesisBlocked as exc:
                cross_surface_errors.append(str(exc))

        state = predecision_state(mission=mission, evidence=plain_evidence)
        errors = tuple(
            dict.fromkeys(
                [*validate_state(state, "plan"), *cross_surface_errors]
            )
        )
        missing = tuple(missing_predecision_codes(plain_evidence))
        fingerprint = state_fingerprint(state_snapshot) if state_snapshot is not None else None

        base = dict(
            decision_id=decision_id,
            mission=mission,
            request=request,
            map_evidence=_clean_items(plain_evidence.get("map")),
            history_evidence=_clean_items(plain_evidence.get("history")),
            research_evidence=_clean_items(plain_evidence.get("research")),
            capability_evidence=_clean_items(plain_evidence.get("capabilities")),
            state_fingerprint=fingerprint,
            authority_guard_fingerprint=(
                authority_guard.fingerprint if authority_guard is not None else None
            ),
            evidence_types=evidence_types,
            contradiction_keys=contradiction_keys,
            mutation_requested=mutation_requested,
            hypothesis_id=hypothesis_id,
        )

        if errors:
            packet = DecisionPacket(
                **base,
                proposed_plan="",
                allowed_actions=(),
                blocked_actions=(),
                decision_status=PREFLIGHT_REQUIRED,
                next_action=missing[0] if missing else "PREFLIGHT_REQUIRED",
                missing_requirements=missing,
                gate_errors=errors,
                provider_called=False,
            )
            self.store.save(packet)
            return packet

        context = {
            "mission": mission,
            "request": request,
            "evidence": {
                "map": list(base["map_evidence"]),
                "history": list(base["history_evidence"]),
                "research": list(base["research_evidence"]),
                "capabilities": list(base["capability_evidence"]),
            },
            "state_fingerprint": fingerprint,
            "typed_evidence": {
                stage: [asdict(item) for item in typed_gate.items.get(stage, ())]
                for stage in typed_gate.items
            } if typed_gate is not None else None,
            "mutation_requested": mutation_requested,
            "authority_guard": (
                authority_guard.context() if authority_guard is not None else None
            ),
            "instruction": (
                "Return a structured Operation Pancake plan only. Evidence was validated "
                "before this call; do not invent or self-certify missing evidence. "
                "If authority_guard is present, its REQUIRED_NEXT and REJECTED route "
                "constraints are mandatory and override caller omission."
            ),
        }

        try:
            decision = self.provider.decide(request, context)
        except DecisionTransportUnavailable as exc:
            packet = DecisionPacket(
                **base,
                proposed_plan="",
                allowed_actions=(),
                blocked_actions=(),
                decision_status=BLOCKED_EXTERNAL,
                next_action="configure authorized model transport",
                missing_requirements=("MODEL_TRANSPORT_REQUIRED",),
                gate_errors=(str(exc),),
                provider_called=True,
            )
            self.store.save(packet)
            return packet

        if not isinstance(decision, Mapping):
            raise SOPGatewayError("Decision provider must return a mapping")

        proposed_plan = str(decision.get("proposed_plan", "")).strip()
        if not proposed_plan:
            raise SOPGatewayError("Decision provider returned no proposed_plan")

        allowed_actions = _clean_items(decision.get("allowed_actions"))
        blocked_actions = _clean_items(decision.get("blocked_actions"))
        next_action = str(decision.get("next_action", "")).strip() or (
            allowed_actions[0] if allowed_actions else "await external input"
        )
        obstacle_classification = str(
            decision.get("obstacle_classification", "NONE")
        ).strip().upper() or "NONE"
        alternatives_considered = _clean_items(decision.get("alternatives_considered"))
        selected_reason = str(decision.get("selected_reason", "")).strip()
        implementation_basis_fact_keys = _clean_items(
            decision.get("implementation_basis_fact_keys")
        )
        user_action_required = bool(decision.get("user_action_required", False))
        remaining_executable_routes = _clean_items(
            decision.get("remaining_executable_routes")
        )
        selected_route_id = str(decision.get("selected_route_id", "")).strip() or None
        remaining_route_ids = _clean_items(decision.get("remaining_route_ids"))
        overlap = set(allowed_actions) & set(blocked_actions)
        if overlap:
            raise SOPGatewayError(
                "Decision provider placed actions in both allowed and blocked sets: "
                + ", ".join(sorted(overlap))
            )

        post_decision_errors: list[str] = []
        if self.strict_evidence:
            if not alternatives_considered:
                post_decision_errors.append("ALTERNATIVES_REQUIRED")
            if not selected_reason:
                post_decision_errors.append("SELECTED_REASON_REQUIRED")
        if self.strict_evidence and typed_gate is not None:
            post_decision_errors.extend(
                trusted_basis_errors(
                    typed_gate,
                    implementation_basis_fact_keys,
                    mutation_requested=mutation_requested,
                )
            )
            post_decision_errors.extend(
                validate_user_test_boundary(
                    user_action_required=user_action_required,
                    remaining_executable_routes=remaining_executable_routes,
                )
            )
        if self.strict_evidence and authority_guard is not None:
            post_decision_errors.extend(
                authority_guard.decision_errors(
                    selected_route_id=selected_route_id,
                    remaining_route_ids=remaining_route_ids,
                    user_action_required=user_action_required,
                )
            )
        if post_decision_errors:
            packet = DecisionPacket(
                **base,
                proposed_plan=proposed_plan,
                allowed_actions=(),
                blocked_actions=blocked_actions,
                decision_status=EVIDENCE_GAP,
                next_action=post_decision_errors[0],
                missing_requirements=tuple(dict.fromkeys(post_decision_errors)),
                gate_errors=tuple(dict.fromkeys(post_decision_errors)),
                provider_called=True,
                obstacle_classification=obstacle_classification,
                alternatives_considered=alternatives_considered,
                selected_reason=selected_reason,
                implementation_basis_fact_keys=implementation_basis_fact_keys,
                user_action_required=user_action_required,
                remaining_executable_routes=remaining_executable_routes,
                selected_route_id=selected_route_id,
                remaining_route_ids=remaining_route_ids,
            )
            self.store.save(packet)
            return packet

        packet = DecisionPacket(
            **base,
            proposed_plan=proposed_plan,
            allowed_actions=allowed_actions,
            blocked_actions=blocked_actions,
            decision_status=DECISION_ALLOWED,
            next_action=next_action,
            provider_called=True,
            obstacle_classification=obstacle_classification,
            alternatives_considered=alternatives_considered,
            selected_reason=selected_reason,
            implementation_basis_fact_keys=implementation_basis_fact_keys,
            user_action_required=user_action_required,
            remaining_executable_routes=remaining_executable_routes,
            selected_route_id=selected_route_id,
            remaining_route_ids=remaining_route_ids,
        )
        self.store.save(packet)
        return packet

    def authorize_action(
        self,
        decision_id: str,
        action: str,
        *,
        current_state_snapshot: Any = None,
    ) -> ActionAuthorization:
        action = action.strip()
        if not action:
            raise ValueError("action is required")
        packet = self.store.load(decision_id)
        if packet.authority_guard_fingerprint is not None:
            try:
                current_guard = load_authority_guard(
                    self.authority_path,
                    packet.mission,
                    required=self.require_authority_guard,
                )
            except AuthorityGuardError as exc:
                raise StateChanged(
                    "Authoritative decision guard became unavailable; rerun preflight"
                ) from exc
            if (
                current_guard is None
                or current_guard.fingerprint != packet.authority_guard_fingerprint
            ):
                raise StateChanged(
                    "Authoritative history/route constraints changed after the decision; "
                    "rerun MAP/HISTORY/RESEARCH/CAPABILITIES"
                )
        if packet.decision_status != DECISION_ALLOWED:
            raise ActionBlocked(
                f"Decision {decision_id} is not actionable; status={packet.decision_status}"
            )
        if action in packet.blocked_actions:
            raise ActionBlocked(f"Action {action!r} is explicitly blocked by decision {decision_id}")
        if action not in packet.allowed_actions:
            raise ActionBlocked(f"Action {action!r} is not authorized by decision {decision_id}")
        if packet.state_fingerprint is not None:
            if current_state_snapshot is None:
                raise StateChanged("Current project state is required to revalidate this action")
            current = state_fingerprint(current_state_snapshot)
            if current != packet.state_fingerprint:
                raise StateChanged(
                    "Project state changed after the decision; rerun MAP/HISTORY/RESEARCH/CAPABILITIES"
                )
        return ActionAuthorization(decision_id=decision_id, action=action)

    def authorize_mutation_action(
        self,
        decision_id: str,
        action: str,
        *,
        current_state_snapshot: Any = None,
    ) -> ActionAuthorization:
        packet = self.store.load(decision_id)
        if packet.mutation_requested is not True:
            raise ActionBlocked(
                f"Decision {decision_id} was not approved as a mutation decision"
            )
        if not packet.implementation_basis_fact_keys:
            raise ActionBlocked(
                f"Decision {decision_id} has no verified implementation basis"
            )
        return self.authorize_action(
            decision_id,
            action,
            current_state_snapshot=current_state_snapshot,
        )

    def record_hypothesis_result(
        self,
        hypothesis_id: str,
        *,
        outcome: str,
        evidence: Sequence[str] = (),
    ) -> Mapping[str, Any]:
        if self.hypotheses is None:
            raise SOPGatewayError("hypothesis ledger is not configured")
        return self.hypotheses.record_result(
            hypothesis_id,
            outcome=outcome,
            evidence=evidence,
        )

    def execute_action(
        self,
        decision_id: str,
        action: str,
        executor: Callable[[], Any],
        *,
        current_state_snapshot: Any = None,
    ) -> Any:
        self.authorize_action(
            decision_id,
            action,
            current_state_snapshot=current_state_snapshot,
        )
        return executor()

    def complete_decision(self, decision_id: str, *, next_action: str = "complete") -> DecisionPacket:
        packet = self.store.load(decision_id)
        normalized = next_action.strip().lower()
        if normalized not in TERMINAL_NEXT_ACTIONS:
            raise ActionBlocked(
                "Decision cannot be marked complete while executable work remains: "
                f"{next_action!r}"
            )
        complete = DecisionPacket(
            **{
                **packet.as_dict(),
                "decision_status": COMPLETE,
                "next_action": next_action,
                "map_evidence": packet.map_evidence,
                "history_evidence": packet.history_evidence,
                "research_evidence": packet.research_evidence,
                "capability_evidence": packet.capability_evidence,
                "allowed_actions": packet.allowed_actions,
                "blocked_actions": packet.blocked_actions,
                "missing_requirements": packet.missing_requirements,
                "gate_errors": packet.gate_errors,
            }
        )
        self.store.save(complete)
        return complete


def production_gateway(root: Path, provider: DecisionProvider | None = None) -> SOPDecisionGateway:
    record_root = root / ".operation_pancake" / "decisions"
    if provider is None:
        from operation_pancake.openai_decision_provider import configured_provider

        provider = configured_provider(root) or NoDecisionProvider()
    return SOPDecisionGateway(
        provider=provider,
        store=DecisionRecordStore(record_root),
        strict_evidence=True,
        hypotheses=HypothesisLedger(root / ".operation_pancake" / "hypotheses.json"),
        authority_path=root / "docs" / "OPERATION_PANCAKE_CONTROL_STATE.json",
        require_authority_guard=True,
    )


def gateway_status(root: Path) -> dict[str, Any]:
    from operation_pancake.openai_decision_provider import transport_status

    transport = transport_status(root)
    return {
        "controller": "operation_pancake.sop_gateway",
        "decision_records": str(root / ".operation_pancake" / "decisions"),
        "predecision_required": ["map", "history", "research", "capabilities"],
        "model_transport": "CONFIGURED" if transport["configured"] else "CREDENTIAL_REQUIRED",
        "model": transport["model"],
        "key_source": transport["key_source"],
        "direct_chatgpt_interception": False,
        "typed_evidence_required": True,
        "automatic_contradiction_gate": True,
        "hypothesis_circuit_breaker": True,
        "user_test_gate": True,
        "mutation_authorization": "decision-bound fail-closed tool broker",
        "repository_gate": "required downstream",
    }
