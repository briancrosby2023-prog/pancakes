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
    explain = sub.add_parser("explain")
    explain.add_argument("card_id")
    compare_explain = sub.add_parser("compare-explain")
    compare_explain.add_argument("current_card_id")
    compare_explain.add_argument("candidate_card_id")
    alternatives = sub.add_parser("alternatives")
    alternatives.add_argument("card_id")
    alternatives.add_argument("--tolerance", type=float, default=0.5)
    attribute_upgrades = sub.add_parser("attribute-upgrades")
    attribute_upgrades.add_argument("card_id")
    attribute_upgrades.add_argument("--attribute")
    attribute_upgrades.add_argument("--min-score-gain", type=float, default=0)
    purchase_report = sub.add_parser("purchase-report")
    purchase_report.add_argument("current_card_id")
    purchase_report.add_argument("candidate_card_id")
    purchase_report.add_argument("--budget", type=int)
    sub.add_parser("shopping-board")
    discover = sub.add_parser("discover")
    discover.add_argument("--position")
    discover.add_argument("--ovr-max", type=int)
    discover.add_argument("--limit", type=int, default=20)
    value_alternatives = sub.add_parser("value-alternatives")
    value_alternatives.add_argument("card_id")
    ovr_savings = sub.add_parser("ovr-savings")
    ovr_savings.add_argument("card_id")
    moneyball_board = sub.add_parser("moneyball-board")
    moneyball_board.add_argument("--position")
    moneyball_board.add_argument("--limit", type=int, default=25)
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
    elif args.command in {"explain", "compare-explain", "alternatives", "attribute-upgrades"}:
        from operation_pancake.production.attributes import AttributeIntelligence

        intelligence = AttributeIntelligence(root)
        if args.command == "explain":
            _dump(intelligence.contribution(args.card_id))
        elif args.command == "compare-explain":
            _dump(intelligence.compare(args.current_card_id, args.candidate_card_id))
        elif args.command == "alternatives":
            _dump(intelligence.alternatives(args.card_id, args.tolerance))
        else:
            _dump(
                intelligence.attribute_upgrades(args.card_id, args.attribute, args.min_score_gain)
            )
    elif args.command in {"purchase-report", "shopping-board"}:
        from operation_pancake.production.purchase import PurchaseIntelligence

        purchase = PurchaseIntelligence(root)
        if args.command == "purchase-report":
            report = purchase.report(
                args.current_card_id, args.candidate_card_id, budget=args.budget
            )
            print(purchase.render(report), end="")
        else:
            _dump(purchase.shopping_board())
    elif args.command in {"discover", "value-alternatives", "ovr-savings", "moneyball-board"}:
        from operation_pancake.production.discovery import DiscoveryIntelligence

        discovery = DiscoveryIntelligence(root)
        if args.command in {"discover", "moneyball-board"}:
            _dump(discovery.discover(args.position, getattr(args, "ovr_max", None), args.limit))
        elif args.command == "value-alternatives":
            _dump(discovery.alternatives(args.card_id))
        else:
            _dump(discovery.ovr_savings(args.card_id))
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
