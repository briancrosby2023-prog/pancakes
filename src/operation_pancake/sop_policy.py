"""Deterministic Operation Pancake SOP policy shared by CI and decision gating."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

STAGE_ORDER = [
    "map",
    "history",
    "research",
    "capabilities",
    "plan",
    "execute",
    "adapt",
    "verify",
    "update_map",
    "continue",
]

PREDECISION_STAGES = ("map", "history", "research", "capabilities")

ACTION_REQUIREMENTS = {
    "map": [],
    "history": ["map"],
    "research": ["map", "history"],
    "capabilities": ["map", "history", "research"],
    "plan": ["map", "history", "research", "capabilities"],
    "execute": ["map", "history", "research", "capabilities", "plan"],
    "commit": ["map", "history", "research", "capabilities", "plan"],
    "ci": ["map", "history", "research", "capabilities", "plan"],
    "blocked": ["map", "history", "research", "capabilities"],
    "package": [
        "map",
        "history",
        "research",
        "capabilities",
        "plan",
        "execute",
        "adapt",
        "verify",
    ],
    "release": STAGE_ORDER,
    "complete": STAGE_ORDER,
}

TERMINAL_NEXT_ACTIONS = {
    "",
    "none",
    "n/a",
    "complete",
    "completed",
    "await external input",
    "awaiting external input",
}


def _has_evidence(value: Any) -> bool:
    return isinstance(value, Sequence) and not isinstance(value, (str, bytes)) and any(
        str(item).strip() for item in value
    )


def stage_errors(state: Mapping[str, Any], stage_name: str, action: str) -> list[str]:
    stage = state.get(stage_name)
    label = stage_name.upper()
    if not isinstance(stage, Mapping):
        return [f"{label} is missing for action {action}."]
    if stage.get("complete") is not True:
        return [f"{label} is incomplete for action {action}."]
    if not _has_evidence(stage.get("evidence")):
        return [f"{label} requires evidence for action {action}."]
    return []


def validate_state(state: Mapping[str, Any], action: str) -> list[str]:
    errors: list[str] = []
    if action not in ACTION_REQUIREMENTS:
        return [f"Unknown action: {action}"]

    if not str(state.get("mission", "")).strip():
        errors.append("mission is required.")
    if not str(state.get("status", "")).strip():
        errors.append("status is required.")

    for stage_name in ACTION_REQUIREMENTS[action]:
        errors.extend(stage_errors(state, stage_name, action))

    status = str(state.get("status", "")).strip().upper()
    if status == "BLOCKED":
        for stage_name in ("research", "capabilities"):
            errors.extend(stage_errors(state, stage_name, "blocked"))

    if status == "COMPLETE":
        next_action = str(state.get("next_action", "")).strip().lower()
        if next_action not in TERMINAL_NEXT_ACTIONS:
            errors.append(
                "COMPLETE status cannot retain an executable next_action; "
                f"found next_action={state.get('next_action')!r}."
            )

    return list(dict.fromkeys(errors))


def predecision_state(
    *,
    mission: str,
    evidence: Mapping[str, Sequence[str]],
) -> dict[str, Any]:
    state: dict[str, Any] = {
        "mission": mission,
        "status": "IN_PROGRESS",
        "next_action": "produce plan after preflight",
    }
    for name in STAGE_ORDER:
        items = [str(item).strip() for item in evidence.get(name, ()) if str(item).strip()]
        state[name] = {"complete": bool(items), "evidence": items}
    return state


def missing_predecision_codes(evidence: Mapping[str, Sequence[str]]) -> list[str]:
    codes: list[str] = []
    for stage in PREDECISION_STAGES:
        items = [str(item).strip() for item in evidence.get(stage, ()) if str(item).strip()]
        if not items:
            codes.append(f"{stage.upper()}_REQUIRED")
    return codes
