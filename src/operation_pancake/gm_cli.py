"""Single user-facing Operation Pancake GM command surface."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

from operation_pancake.production.gm import GMProduct, manual_price_payload, optimize_budget
from operation_pancake.production.market_campaign import (
    REAL_HISTORY,
    append_history,
    enrich_observation,
)


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
    observe = sub.add_parser("market-observe")
    observe.add_argument("card_id")
    observe.add_argument("price", type=int)
    observe.add_argument("observation_type")
    observe.add_argument("--observed-at")
    observe.add_argument("--history", type=Path)
    snapshot = sub.add_parser("market-snapshot")
    snapshot.add_argument("file", type=Path, help="JSON object of canonical card IDs to prices")
    snapshot.add_argument("--type", default="DISPLAYED_MARKET_PRICE")
    snapshot.add_argument("--observed-at")
    snapshot.add_argument("--history", type=Path)
    budget = sub.add_parser("budget")
    budget.add_argument("file", type=Path, help="JSON candidate list")
    budget.add_argument("coins", type=int)
    sub.add_parser("roster")
    sub.add_parser("price-check")
    args = parser.parse_args()
    root = args.root.resolve()
    if args.command == "player":
        gm = GMProduct(root)
        _dump(
            gm.lookup(
                card_id=args.card_id,
                player_name=args.name,
                position=args.position,
                overall=args.overall,
                program=args.program,
            )
        )
    elif args.command == "compare":
        gm = GMProduct(root)
        _dump(gm.compare(args.current_card_id, args.candidate_card_id, args.price, args.resale))
    elif args.command == "price":
        rows = json.loads(args.file.read_text(encoding="utf-8"))
        gm = GMProduct(root)
        _dump(manual_price_payload(rows, args.observed_at, gm.population))
    elif args.command in {"market-observe", "market-snapshot"}:
        gm = GMProduct(root)
        observed_at = args.observed_at or datetime.now().astimezone().isoformat()
        values = (
            {args.card_id: args.price}
            if args.command == "market-observe"
            else json.loads(args.file.read_text(encoding="utf-8"))
        )
        observation_type = args.observation_type if args.command == "market-observe" else args.type
        observations = []
        for card_id, amount in values.items():
            if card_id not in gm.cards:
                raise SystemExit(f"unresolved canonical card ID: {card_id}")
            observations.append(
                enrich_observation(
                    gm.cards[card_id], int(amount), observation_type, observed_at=observed_at
                )
            )
        history = args.history or root / REAL_HISTORY
        _dump({"observations": observations, "history": append_history(history, observations)})
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
                    checks.append(
                        {
                            **candidate,
                            "position": replacement.get("position_family"),
                            "reason": f"upgrade for {replacement.get('current')}",
                        }
                    )
        from operation_pancake.production.gm import price_check_list

        _dump(price_check_list(checks))


if __name__ == "__main__":
    main()
