"""Console entry for the existing GM CLI plus OP-X-051 role-intelligence surfaces."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from operation_pancake import gm_cli
from operation_pancake.production.role_intelligence import role_alternatives, role_board

OP_X_051_COMMANDS = {
    "role-board",
    "role-alternatives",
    "roster-roles",
    "zero-coin-upgrades",
    "target-challenge",
}


def _dump(value: object) -> None:
    print(json.dumps(value, indent=2, sort_keys=True))


def _artifact(root: Path, name: str) -> object:
    path = root / "data/research/op_x_051" / name
    if not path.exists():
        raise SystemExit(f"OP-X-051 artifact not materialized: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _op_x_051_main(argv: list[str]) -> None:
    parser = argparse.ArgumentParser(prog="operation-pancake-gm")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    sub = parser.add_subparsers(dest="command", required=True)

    board = sub.add_parser("role-board")
    board.add_argument("position")
    board.add_argument("role")
    board.add_argument("--limit", type=int, default=25)

    alternatives = sub.add_parser("role-alternatives")
    alternatives.add_argument("card_id")
    alternatives.add_argument("role")
    alternatives.add_argument("--limit", type=int, default=10)

    sub.add_parser("roster-roles")
    sub.add_parser("zero-coin-upgrades")

    challenge = sub.add_parser("target-challenge")
    challenge.add_argument("--index", type=int, choices=range(1, 6))

    args = parser.parse_args(argv)
    root = args.root.resolve()
    if args.command == "role-board":
        _dump(role_board(root, args.position.upper(), args.role.upper(), args.limit))
    elif args.command == "role-alternatives":
        _dump(role_alternatives(root, args.card_id, args.role.upper(), args.limit))
    elif args.command == "roster-roles":
        _dump(_artifact(root, "ROSTER_ROLE_MAP.json"))
    elif args.command == "zero-coin-upgrades":
        _dump(_artifact(root, "ZERO_COIN_UPGRADES.json"))
    else:
        payload = _artifact(root, "TARGET_CHALLENGES.json")
        if args.index is None:
            _dump(payload)
        else:
            targets = payload.get("targets", []) if isinstance(payload, dict) else []
            if len(targets) < args.index:
                raise SystemExit(f"target challenge {args.index} is not materialized")
            _dump(targets[args.index - 1])


def main() -> None:
    # Preserve every pre-existing gm_cli command unchanged. Only intercept the five
    # OP-X-051 command names (allowing --root before the subcommand).
    command = next((arg for arg in sys.argv[1:] if not arg.startswith("-")), None)
    if command in OP_X_051_COMMANDS:
        _op_x_051_main(sys.argv[1:])
    else:
        gm_cli.main()


if __name__ == "__main__":
    main()
