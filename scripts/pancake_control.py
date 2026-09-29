#!/usr/bin/env python3
"""Validate and render the project-wide Operation Pancake control state."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from operation_pancake.control_state import (  # noqa: E402
    AUTHORITY_FILE,
    preflight_summary,
    render_handoff,
    validate_control_state,
)


def load_state(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("control state root must be an object")
    return payload


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Operation Pancake project-wide decision control")
    p.add_argument(
        "--state",
        type=Path,
        default=ROOT / AUTHORITY_FILE,
        help=f"authoritative control state (default: {AUTHORITY_FILE})",
    )
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("validate")
    sub.add_parser("preflight")
    handoff = sub.add_parser("handoff")
    handoff.add_argument("--check", type=Path, default=None)
    return p


def main() -> int:
    args = parser().parse_args()
    try:
        state = load_state(args.state)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print("PANCAKE CONTROL: FAIL")
        print(f"- {exc}")
        return 1

    errors = validate_control_state(state)
    if args.command == "validate":
        if errors:
            print("PANCAKE CONTROL: FAIL")
            for error in errors:
                print(f"- {error}")
            return 1
        print("PANCAKE CONTROL: PASS")
        print(f"- authority: {AUTHORITY_FILE}")
        print(f"- revision: {state['state_revision']}")
        print(f"- mission: {state['active_mission']['id']}")
        return 0

    if args.command == "preflight":
        summary = preflight_summary(state)
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 0 if summary["status"] == "PASS" else 1

    if errors:
        print("PANCAKE CONTROL: FAIL")
        for error in errors:
            print(f"- {error}")
        return 1

    rendered = render_handoff(state)
    if args.check is not None:
        try:
            existing = args.check.read_text(encoding="utf-8")
        except OSError as exc:
            print("PANCAKE HANDOFF: FAIL")
            print(f"- {exc}")
            return 1
        if existing != rendered:
            print("PANCAKE HANDOFF: FAIL")
            print("- handoff is stale; regenerate it from the authoritative control state")
            return 1
        print("PANCAKE HANDOFF: PASS")
        return 0

    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
