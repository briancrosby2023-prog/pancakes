#!/usr/bin/env python3
"""Fail-closed validator for the Operation Pancake SOP state."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

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


def _stage_errors(state: dict, stage_name: str, action: str) -> list[str]:
    stage = state.get(stage_name)
    label = stage_name.upper()
    if not isinstance(stage, dict):
        return [f"{label} is missing for action {action}."]
    if stage.get("complete") is not True:
        return [f"{label} is incomplete for action {action}."]
    evidence = stage.get("evidence")
    if not isinstance(evidence, list) or not any(str(item).strip() for item in evidence):
        return [f"{label} requires evidence for action {action}."]
    return []


def validate(state: dict, action: str) -> list[str]:
    errors: list[str] = []
    if action not in ACTION_REQUIREMENTS:
        return [f"Unknown action: {action}"]

    if not str(state.get("mission", "")).strip():
        errors.append("mission is required.")
    if not str(state.get("status", "")).strip():
        errors.append("status is required.")

    for stage_name in ACTION_REQUIREMENTS[action]:
        errors.extend(_stage_errors(state, stage_name, action))

    status = str(state.get("status", "")).strip().upper()
    if status == "BLOCKED":
        for stage_name in ("research", "capabilities"):
            errors.extend(_stage_errors(state, stage_name, "blocked"))

    if status == "COMPLETE":
        next_action = str(state.get("next_action", "")).strip().lower()
        if next_action not in TERMINAL_NEXT_ACTIONS:
            errors.append(
                "COMPLETE status cannot retain an executable next_action; "
                f"found next_action={state.get('next_action')!r}."
            )

    return list(dict.fromkeys(errors))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate Operation Pancake SOP state")
    parser.add_argument("--state", required=True, type=Path, help="Path to SOP state JSON")
    parser.add_argument("--action", required=True, choices=sorted(ACTION_REQUIREMENTS))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.state.is_file():
        print("SOP GATE: FAIL")
        print(f"- state file not found: {args.state}")
        return 1

    try:
        state = json.loads(args.state.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print("SOP GATE: FAIL")
        print(f"- cannot read state: {exc}")
        return 1

    if not isinstance(state, dict):
        print("SOP GATE: FAIL")
        print("- state root must be a JSON object")
        return 1

    errors = validate(state, args.action)
    if errors:
        print("SOP GATE: FAIL")
        for error in errors:
            print(f"- {error}")
        return 1

    print("SOP GATE: PASS")
    print(f"- action: {args.action}")
    print(f"- state: {args.state}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
