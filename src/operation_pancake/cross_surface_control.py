"""Deterministic cross-surface SOP controls for Operation Pancake."""
from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

EVIDENCE_TYPES = {
    "OBSERVED",
    "VERIFIED_HISTORY",
    "EXTERNAL_RESEARCH",
    "INFERENCE",
    "UNKNOWN",
}
TRUSTED_TYPES = {"OBSERVED", "VERIFIED_HISTORY", "EXTERNAL_RESEARCH"}
PREFLIGHT_STAGES = ("map", "history", "research", "capabilities")


class CrossSurfaceControlError(RuntimeError):
    pass


class EvidenceBlocked(CrossSurfaceControlError):
    pass


class HypothesisBlocked(CrossSurfaceControlError):
    pass


class UserActionBlocked(CrossSurfaceControlError):
    pass


@dataclass(frozen=True)
class EvidenceItem:
    kind: str
    text: str
    fact_key: str | None = None
    fact_value: str | None = None
    source: str | None = None

    @classmethod
    def from_raw(cls, raw: Any) -> "EvidenceItem":
        if isinstance(raw, cls):
            return raw
        if not isinstance(raw, Mapping):
            raise ValueError("typed evidence item must be an object")
        kind = str(raw.get("kind", "")).strip().upper()
        text = str(raw.get("text", "")).strip()
        if kind not in EVIDENCE_TYPES:
            raise ValueError(f"unsupported evidence kind: {kind or '<missing>'}")
        if not text:
            raise ValueError("typed evidence item requires text")
        fact_key = str(raw.get("fact_key", "")).strip() or None
        fact_value = str(raw.get("fact_value", "")).strip() or None
        source = str(raw.get("source", "")).strip() or None
        if bool(fact_key) != bool(fact_value):
            raise ValueError("fact_key and fact_value must be supplied together")
        return cls(kind, text, fact_key, fact_value, source)


@dataclass(frozen=True)
class EvidenceGateResult:
    items: Mapping[str, tuple[EvidenceItem, ...]]
    errors: tuple[str, ...]
    contradiction_keys: tuple[str, ...]

    @property
    def passed(self) -> bool:
        return not self.errors and not self.contradiction_keys

    def plain(self) -> dict[str, list[str]]:
        return {
            stage: [item.text for item in self.items.get(stage, ())]
            for stage in PREFLIGHT_STAGES
        }

    def kinds(self) -> tuple[str, ...]:
        return tuple(sorted({
            item.kind
            for stage in PREFLIGHT_STAGES
            for item in self.items.get(stage, ())
        }))

    def trusted_fact_keys(self) -> set[str]:
        return {
            item.fact_key
            for stage in PREFLIGHT_STAGES
            for item in self.items.get(stage, ())
            if item.kind in TRUSTED_TYPES and item.fact_key
        }


def _unique(values: Sequence[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(str(v).strip() for v in values if str(v).strip()))


def validate_typed_evidence(
    evidence: Mapping[str, Sequence[Any]],
) -> EvidenceGateResult:
    normalized: dict[str, tuple[EvidenceItem, ...]] = {}
    errors: list[str] = []
    facts: dict[str, set[str]] = {}
    if not isinstance(evidence, Mapping):
        return EvidenceGateResult({}, ("EVIDENCE must be an object.",), ())

    for stage in PREFLIGHT_STAGES:
        raw_items = evidence.get(stage, ())
        if not isinstance(raw_items, Sequence) or isinstance(raw_items, (str, bytes)):
            raw_items = ()
        parsed: list[EvidenceItem] = []
        for index, raw in enumerate(raw_items):
            try:
                parsed.append(EvidenceItem.from_raw(raw))
            except ValueError as exc:
                errors.append(f"{stage.upper()} evidence[{index}]: {exc}")
        normalized[stage] = tuple(parsed)
        if not parsed:
            errors.append(f"{stage.upper()}_REQUIRED")
            continue
        if not any(item.kind in TRUSTED_TYPES for item in parsed):
            errors.append(
                f"{stage.upper()} requires OBSERVED, VERIFIED_HISTORY, or EXTERNAL_RESEARCH evidence."
            )
        for item in parsed:
            if item.fact_key and item.fact_value and item.kind in TRUSTED_TYPES:
                facts.setdefault(item.fact_key, set()).add(item.fact_value)

    contradictions = tuple(sorted(k for k, values in facts.items() if len(values) > 1))
    if contradictions:
        errors.append("CONTRADICTION_UNRESOLVED: " + ", ".join(contradictions))
    return EvidenceGateResult(
        normalized,
        _unique(errors),
        contradictions,
    )


def trusted_basis_errors(
    gate: EvidenceGateResult,
    fact_keys: Sequence[str],
    *,
    mutation_requested: bool,
) -> tuple[str, ...]:
    if not mutation_requested:
        return ()
    requested = _unique(fact_keys)
    if not requested:
        return ("IMPLEMENTATION_BASIS_REQUIRED",)
    trusted = gate.trusted_fact_keys()
    return tuple(
        f"IMPLEMENTATION_BASIS_UNVERIFIED:{key}"
        for key in requested
        if key not in trusted
    )


def validate_user_test_boundary(
    *,
    user_action_required: bool,
    remaining_executable_routes: Sequence[str],
) -> tuple[str, ...]:
    routes = _unique(remaining_executable_routes)
    if user_action_required and routes:
        return (
            "USER_TEST_BLOCKED_WHILE_EXECUTABLE_ROUTES_REMAIN: " + " | ".join(routes),
        )
    return ()


def evidence_fingerprint(values: Sequence[str]) -> str:
    raw = json.dumps(sorted(_unique(values)), separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


class HypothesisLedger:
    """Stop repeated implementation attempts that lack materially new evidence."""

    def __init__(self, path: Path):
        self.path = path

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"schema": "operation-pancake-hypothesis-ledger-v1", "hypotheses": {}}
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise HypothesisBlocked("hypothesis ledger root must be an object")
        payload.setdefault("hypotheses", {})
        return payload

    def _save(self, payload: Mapping[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_suffix(self.path.suffix + ".tmp")
        temp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        temp.replace(self.path)

    def authorize_attempt(
        self,
        hypothesis_id: str,
        *,
        new_evidence: Sequence[str] = (),
    ) -> None:
        hypothesis_id = hypothesis_id.strip()
        if not hypothesis_id:
            raise HypothesisBlocked("hypothesis_id is required")
        record = self._load()["hypotheses"].get(hypothesis_id, {})
        failures = int(record.get("failures", 0))
        if record.get("invalidated") is True or failures >= 2:
            raise HypothesisBlocked(
                f"hypothesis {hypothesis_id} is invalidated after two failed attempts"
            )
        if failures >= 1 and not _unique(new_evidence):
            raise HypothesisBlocked(
                f"hypothesis {hypothesis_id} already failed; materially new evidence is required"
            )

    def record_result(
        self,
        hypothesis_id: str,
        *,
        outcome: str,
        evidence: Sequence[str] = (),
    ) -> Mapping[str, Any]:
        hypothesis_id = hypothesis_id.strip()
        normalized = outcome.strip().upper()
        if not hypothesis_id:
            raise HypothesisBlocked("hypothesis_id is required")
        if normalized not in {"PASS", "FAIL"}:
            raise ValueError("outcome must be PASS or FAIL")
        payload = self._load()
        record = dict(payload["hypotheses"].get(hypothesis_id, {}))
        attempts = list(record.get("attempts", []))
        attempts.append({
            "outcome": normalized,
            "evidence": list(_unique(evidence)),
            "evidence_fingerprint": evidence_fingerprint(evidence),
        })
        failures = sum(1 for item in attempts if item.get("outcome") == "FAIL")
        record.update({
            "attempts": attempts,
            "failures": failures,
            "invalidated": failures >= 2,
        })
        payload["hypotheses"][hypothesis_id] = record
        self._save(payload)
        return record
