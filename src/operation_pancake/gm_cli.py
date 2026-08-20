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
    sub.add_parser("market-campaign")
    market_round = sub.add_parser("market-round")
    market_round.add_argument("file", type=Path, help="newline-separated CARD_ID PRICE entries")
    market_round.add_argument("--round-id", required=True)
    market_round.add_argument("--observed-at", required=True)
    market_round.add_argument("--type", default="LOWEST_VISIBLE_LISTING")
    market_round.add_argument("--history", type=Path)
    sub.add_parser("market-watch")
    sub.add_parser("market-board")
    sub.add_parser("arbitrage")
    sub.add_parser("purchase-frontier")
    sub.add_parser("campaigns")
    campaign_create = sub.add_parser("campaign-create")
    campaign_create.add_argument("file", type=Path)
    campaign_show = sub.add_parser("campaign-show")
    campaign_show.add_argument("campaign_id")
    campaign_start = sub.add_parser("campaign-start")
    campaign_start.add_argument("campaign_id")
    campaign_stop = sub.add_parser("campaign-stop")
    campaign_stop.add_argument("campaign_id")
    market_import = sub.add_parser("market-import")
    market_import.add_argument("file", type=Path)
    market_import.add_argument("--format", choices=("json", "csv"), default="json")
    market_import.add_argument("--ingested-at", required=True)
    market_import.add_argument("--persist", action="store_true")
    sub.add_parser("market-status")
    event_register = sub.add_parser("event-register")
    event_register.add_argument("file", type=Path)
    sub.add_parser("event-status")
    training_basket_command = sub.add_parser("training-basket")
    training_basket_command.add_argument("file", type=Path)
    training_basket_command.add_argument("--version", required=True)
    collection_campaign = sub.add_parser("collection-campaign")
    collection_campaign.add_argument("file", type=Path)
    sub.add_parser("reveals")
    reveal_import = sub.add_parser("reveal-import")
    reveal_import.add_argument("file", type=Path)
    reveal_import.add_argument("--first-seen-at", required=True)
    reveal_import.add_argument("--ingested-at", required=True)
    reveal_import.add_argument("--persist", action="store_true")
    sub.add_parser("whats-coming")
    budget = sub.add_parser("budget")
    hit_add = sub.add_parser("hit-list-add")
    hit_add.add_argument("card_id")
    hit_add.add_argument("--target", type=int)
    hit_add.add_argument("--watch", type=int)
    hit_add.add_argument("--priority", type=int, default=3)
    hit_add.add_argument("--reason")
    hit_remove = sub.add_parser("hit-list-remove")
    hit_remove.add_argument("card_id")
    hit_update = sub.add_parser("hit-list-update")
    hit_update.add_argument("card_id")
    hit_update.add_argument("--target", type=int)
    hit_update.add_argument("--watch", type=int)
    hit_update.add_argument("--priority", type=int)
    sub.add_parser("hit-list-show")
    top = sub.add_parser("top-targets")
    top.add_argument("--limit", type=int, default=25)
    sub.add_parser("monitor-universe")
    sub.add_parser("monitor-run")
    sub.add_parser("alerts")
    flip = sub.add_parser("flip-check")
    flip.add_argument("file", type=Path)
    training = sub.add_parser("training-check")
    training.add_argument("file", type=Path)
    collection = sub.add_parser("collection-evaluate")
    collection.add_argument("file", type=Path)
    collection_watch = sub.add_parser("collection-watch")
    collection_watch.add_argument("file", type=Path)
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
    elif args.command in {
        "market-campaign",
        "market-round",
        "market-watch",
        "market-board",
        "arbitrage",
        "purchase-frontier",
    }:
        from operation_pancake.production.campaign import (
            build_campaign,
            campaign_round,
            parse_compact_snapshot,
        )

        gm = GMProduct(root)
        history_path = getattr(args, "history", None) or root / REAL_HISTORY
        history = json.loads(history_path.read_text()) if history_path.exists() else []
        if args.command == "market-round":
            ingested_at = datetime.now().astimezone().isoformat()
            observations = parse_compact_snapshot(
                args.file.read_text(encoding="utf-8"),
                gm.cards,
                observed_at=args.observed_at,
                ingested_at=ingested_at,
                observation_type=args.type,
            )
            analysis = build_campaign(root, [*history, *observations], ingested_at)
            appended = append_history(history_path, observations)
            _dump(
                {
                    "round": campaign_round(
                        args.round_id, analysis["unique_targets"], observations
                    ),
                    "history": appended,
                    "next": analysis["adaptive_priority"],
                }
            )
        else:
            analysis = build_campaign(root, history, datetime.now().astimezone().isoformat())
            key = {
                "market-campaign": "adaptive_priority",
                "market-watch": "adaptive_priority",
                "market-board": "market_board",
                "arbitrage": "arbitrage",
                "purchase-frontier": "frontiers",
            }[args.command]
            _dump(analysis[key])
    elif args.command in {
        "campaigns",
        "campaign-create",
        "campaign-show",
        "campaign-start",
        "campaign-stop",
        "market-import",
        "market-status",
        "event-register",
        "event-status",
        "training-basket",
        "collection-campaign",
    }:
        from operation_pancake.production.recorder import (
            CAMPAIGN_STATE,
            RECORDER_HISTORY,
            default_campaign,
            load_json,
            parse_browser_export,
            register_event,
            run_snapshot,
            sample_sufficiency,
            save_json,
            training_basket,
        )

        campaign_path = root / CAMPAIGN_STATE
        campaigns = load_json(
            campaign_path, [default_campaign(root, datetime.now().astimezone().isoformat())]
        )
        event_path = root / "data/production/market/events.json"
        if args.command == "campaigns":
            _dump(campaigns)
        elif args.command == "campaign-show":
            match = next((row for row in campaigns if row["campaign_id"] == args.campaign_id), None)
            if match is None:
                raise SystemExit("unknown campaign")
            _dump(match)
        elif args.command in {"campaign-start", "campaign-stop"}:
            found = False
            for row in campaigns:
                if row["campaign_id"] == args.campaign_id:
                    row["active"] = args.command == "campaign-start"
                    found = True
            if not found:
                raise SystemExit("unknown campaign")
            save_json(campaign_path, campaigns)
            _dump(campaigns)
        elif args.command in {"campaign-create", "collection-campaign"}:
            value = json.loads(args.file.read_text(encoding="utf-8"))
            if args.command == "collection-campaign":
                value["campaign_type"] = "SCHEME / COLLECTION"
            if any(row["campaign_id"] == value.get("campaign_id") for row in campaigns):
                raise SystemExit("campaign already exists")
            campaigns.append(value)
            save_json(campaign_path, campaigns)
            _dump(value)
        elif args.command == "market-import":
            rows = parse_browser_export(args.file.read_text(encoding="utf-8"), args.format)
            result = run_snapshot(
                root,
                rows,
                campaigns,
                load_json(root / "data/production/market/recorder_state.json", {}),
                ingested_at=args.ingested_at,
                persist=args.persist,
            )
            _dump(result)
        elif args.command == "market-status":
            rows = load_json(root / RECORDER_HISTORY, [])
            _dump(sample_sufficiency(rows, datetime.now().astimezone().isoformat()))
        elif args.command == "event-register":
            event = register_event(json.loads(args.file.read_text(encoding="utf-8")))
            events = load_json(event_path, [])
            if any(row["event_id"] == event["event_id"] for row in events):
                raise SystemExit("event already exists")
            events.append(event)
            save_json(event_path, events)
            _dump(event)
        elif args.command == "event-status":
            _dump(load_json(event_path, []))
        else:
            rows = json.loads(args.file.read_text(encoding="utf-8"))
            _dump(training_basket(rows, args.version))
    elif args.command in {"reveals", "reveal-import", "whats-coming"}:
        from operation_pancake.production.reveals import (
            REVEAL_REGISTRY,
            merge_registry,
            normalize_reveal,
            render_whats_coming,
            save_registry,
        )

        path = root / REVEAL_REGISTRY
        existing = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
        if args.command == "reveals":
            _dump(existing)
        elif args.command == "whats-coming":
            print(render_whats_coming(existing), end="")
        else:
            payload = json.loads(args.file.read_text(encoding="utf-8"))
            if not isinstance(payload, list):
                raise SystemExit("reveal import must be a JSON list")
            incoming = [
                normalize_reveal(
                    row,
                    first_seen_at=args.first_seen_at,
                    ingested_at=args.ingested_at,
                )
                for row in payload
            ]
            merged = merge_registry(existing, incoming)
            if args.persist:
                save_registry(path, merged, production=True)
            _dump({"accepted": len(incoming), "total": len(merged), "persisted": args.persist})
    elif args.command.startswith("hit-list-"):
        from operation_pancake.production.monitor import (
            canonical_cards,
            hit_list_mutation,
            load_json,
            save_json,
        )

        path = root / "data/production/monitor/hit_list.json"
        entries = load_json(path, [])
        if args.command == "hit-list-show":
            _dump(entries)
        else:
            operation = {
                "hit-list-add": "ADD",
                "hit-list-remove": "REMOVE",
                "hit-list-update": "UPDATE",
            }[args.command]
            changes = {
                "target_buy_price": getattr(args, "target", None),
                "watch_price": getattr(args, "watch", None),
                "priority": getattr(args, "priority", None),
                "reason": getattr(args, "reason", None),
            }
            entries = hit_list_mutation(
                entries,
                operation,
                args.card_id,
                canonical_cards(root),
                now=datetime.now().astimezone().isoformat(),
                **{key: value for key, value in changes.items() if value is not None},
            )
            save_json(path, entries)
            _dump(entries)
    elif args.command in {"top-targets", "monitor-universe", "monitor-run", "alerts"}:
        from operation_pancake.production.monitor import (
            load_json,
            monitor_run,
            monitored_universe,
            save_json,
            top_targets,
        )

        hit_path = root / "data/production/monitor/hit_list.json"
        state_path = root / "data/production/monitor/alert_state.json"
        hit_list = load_json(hit_path, [])
        state = load_json(state_path, {})
        history = load_json(root / REAL_HISTORY, [])
        now = datetime.now().astimezone().isoformat()
        if args.command == "top-targets":
            _dump(top_targets(root, args.limit))
        elif args.command == "monitor-universe":
            _dump(monitored_universe(root, hit_list, history, now))
        elif args.command == "alerts":
            _dump(list(state.get("events", {}).values()))
        else:
            result = monitor_run(root, hit_list, history, state, now)
            save_json(hit_path, result["hit_list"])
            save_json(state_path, result["alert_state"])
            _dump({"events": result["events"], "monitored_universe": result["monitored_universe"]})
    elif args.command in {
        "flip-check",
        "training-check",
        "collection-evaluate",
        "collection-watch",
    }:
        from operation_pancake.production.monitor import (
            collection_evaluate,
            flip_check,
            preposition_evaluate,
            training_check,
        )

        payload = json.loads(args.file.read_text(encoding="utf-8"))
        if args.command == "flip-check":
            _dump(flip_check(**payload))
        elif args.command == "training-check":
            _dump(training_check(**payload))
        elif args.command == "collection-evaluate":
            _dump(collection_evaluate(payload["definition"], payload["inputs"]))
        else:
            _dump(preposition_evaluate(payload))
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
