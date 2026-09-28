#!/usr/bin/env python3
"""Fail-closed validator for the Operation Pancake SOP state."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from operation_pancake.sop_policy import ACTION_REQUIREMENTS, validate_state  # noqa: E402


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

    errors = validate_state(state, args.action)
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
