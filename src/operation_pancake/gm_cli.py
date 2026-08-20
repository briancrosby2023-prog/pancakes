"""Single user-facing Operation Pancake GM command surface."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from operation_pancake.production.gm import GMProduct, manual_price_payload, optimize_budget


def _dump(value: object) -> None:
    print(json.dumps(value, indent=2, sort_keys=True))


def main() -> None:
    parser = argparse.ArgumentParser(prog="operation-pancake-gm")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    sub = parser.add_subparsers(dest="command", required=True)
    lookup = sub.add_parser("player")
    lookup.add_argument("--card-id")
    lookup.add_argument("--name")
    lookup.add_argument("--position")
    lookup.add_argument("--overall", type=int)
    lookup.add_argument("--program")
    compare = sub.add_parser("compare")
    compare.add_argument("current_card_id")
    compare.add_argument("candidate_card_id")
    compare.add_argument("--price", type=int)
    compare.add_argument("--resale", type=int)
    price = sub.add_parser("price")
    price.add_argument("file", type=Path, help="JSON list of manual current-price observations")
    price.add_argument("--observed-at", required=True)
    budget = sub.add_parser("budget")
    budget.add_argument("file", type=Path, help="JSON candidate list")
    budget.add_argument("coins", type=int)
    sub.add_parser("roster")
    sub.add_parser("price-check")
    args = parser.parse_args()
    root = args.root.resolve()
    if args.command == "player":
        gm = GMProduct(root)
        _dump(gm.lookup(card_id=args.card_id, player_name=args.name, position=args.position,
                        overall=args.overall, program=args.program))
    elif args.command == "compare":
        gm = GMProduct(root)
        _dump(gm.compare(args.current_card_id, args.candidate_card_id, args.price, args.resale))
    elif args.command == "price":
        rows = json.loads(args.file.read_text(encoding="utf-8"))
        _dump(manual_price_payload(rows, args.observed_at))
    elif args.command == "budget":
        rows = json.loads(args.file.read_text(encoding="utf-8"))
        _dump(optimize_budget(rows, args.coins))
    elif args.command == "roster":
        from operation_pancake.production import build_roster_outputs
        _dump(build_roster_outputs(root))
    else:
        path = root / "data/production/roster/replacement_candidates.json"
        rows = json.loads(path.read_text(encoding="utf-8"))
        checks = []
        for replacement in rows:
            if replacement.get("status") != "UPGRADE_AVAILABLE":
                continue
            for candidate in replacement.get("candidates", {}).values():
                if candidate:
                    checks.append({**candidate, "position": replacement.get("position_family"),
                                   "reason": f"upgrade for {replacement.get('current')}"})
        from operation_pancake.production.gm import price_check_list
        _dump(price_check_list(checks))


if __name__ == "__main__":
    main()
