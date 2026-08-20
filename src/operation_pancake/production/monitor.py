"""Deterministic, evidence-gated opportunity monitoring services."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Protocol

from .campaign import build_campaign
from .engine import load_population
from .market import training_economics
from .market_campaign import history_statistics

ALERT_TYPES = (
    "BUY TARGET",
    "WATCH TARGET",
    "FLIP",
    "TRAINING VALUE",
    "MONEYBALL",
    "COLLECTION PIECE",
    "COLLECTION ECONOMICS",
    "COLLECTION PRE-POSITION",
    "TOP-25 ENTRY",
    "TOP-10 ENTRY",
)
QUALIFIED = {"USABLE", "STRONG"}
SALE_TYPES = {"COMPLETED_SALE", "RECENT_SALE"}


class AlertDestination(Protocol):
    """Destination contract; delivery is intentionally external to this package."""

    def deliver(self, events: list[dict[str, Any]]) -> None: ...


def load_json(path: Path, default: Any) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def save_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def canonical_cards(root: Path) -> dict[str, dict[str, Any]]:
    return {row["card_id"]: row for row in load_population(root)}


def validate_card_id(card_id: str, cards: dict[str, dict[str, Any]]) -> dict[str, Any]:
    if card_id not in cards:
        raise ValueError(f"unresolved canonical card ID: {card_id}")
    return cards[card_id]


def hit_list_mutation(
    entries: list[dict[str, Any]],
    operation: str,
    card_id: str,
    cards: dict[str, dict[str, Any]],
    *,
    now: str,
    **changes: Any,
) -> list[dict[str, Any]]:
    """Apply an exact-card ADD/REMOVE/ENABLE/DISABLE/UPDATE operation."""
    card = validate_card_id(card_id, cards)
    by_id = {row["card_id"]: dict(row) for row in entries}
    if operation == "REMOVE":
        by_id.pop(card_id, None)
    elif operation == "ADD":
        if card_id in by_id:
            raise ValueError("card already exists in hit list")
        by_id[card_id] = {
            "card_id": card_id,
            "player": card.get("player_name"),
            "position": card.get("position"),
            "overall": card.get("native_overall"),
            "program": card.get("program"),
            "archetype": card.get("archetype"),
            "target_buy_price": changes.get("target_buy_price"),
            "watch_price": changes.get("watch_price"),
            "priority": changes.get("priority", 3),
            "reason": changes.get("reason"),
            "roster_context": changes.get("roster_context"),
            "date_added": now,
            "enabled": True,
            "latest_qualified_market_evidence": None,
            "latest_live_listing_evidence": None,
            "alert_state": "NO DATA",
            "last_evaluated_at": None,
        }
    elif card_id not in by_id:
        raise ValueError("card is not in hit list")
    elif operation in {"ENABLE", "DISABLE"}:
        by_id[card_id]["enabled"] = operation == "ENABLE"
    elif operation == "UPDATE":
        allowed = {"target_buy_price", "watch_price", "priority", "reason", "roster_context"}
        by_id[card_id].update({key: value for key, value in changes.items() if key in allowed})
    else:
        raise ValueError(f"unsupported hit-list operation: {operation}")
    return sorted(by_id.values(), key=lambda row: (row.get("priority", 99), row["card_id"]))


def top_targets(root: Path, limit: int = 25) -> list[dict[str, Any]]:
    payload = load_json(root / "data/research/op_x_034/football_value_index.json", {"cards": []})
    cards = sorted(
        payload["cards"],
        key=lambda row: (
            -float(row.get("football_value_index", 0)),
            -float(row.get("score", 0)),
            int(row.get("position_rank", 10**9)),
            row["card_id"],
        ),
    )[:limit]
    return [
        {
            **row,
            "top_target_rank": index,
            "monitor_tier": "TOP 10" if index <= 10 else "TOP 25",
            "selection_basis": "PRICE-INDEPENDENT FOOTBALL INTELLIGENCE",
        }
        for index, row in enumerate(cards, 1)
    ]


def monitored_universe(
    root: Path,
    hit_list: list[dict[str, Any]],
    history: list[dict[str, Any]],
    as_of: str,
) -> list[dict[str, Any]]:
    cards = canonical_cards(root)
    merged: dict[str, dict[str, Any]] = {}

    def add(card_id: str, source: str, reason: str) -> None:
        card = validate_card_id(card_id, cards)
        row = merged.setdefault(
            card_id,
            {
                "card_id": card_id,
                "player": card.get("player_name"),
                "position": card.get("position"),
                "overall": card.get("native_overall"),
                "program": card.get("program"),
                "archetype": card.get("archetype"),
                "sources": [],
                "reasons": [],
            },
        )
        if source not in row["sources"]:
            row["sources"].append(source)
        if reason not in row["reasons"]:
            row["reasons"].append(reason)

    for row in hit_list:
        if row.get("enabled", True):
            add(
                row["card_id"], "PERSONAL HIT LIST", row.get("reason") or "user-selected exact card"
            )
    for row in top_targets(root):
        add(row["card_id"], row["monitor_tier"], "dynamic football-intelligence target")
    campaign = build_campaign(root, history, as_of)
    for item in campaign["comparison_sets"]:
        for key, source in (
            ("target", "ROSTER BUY TARGET"),
            ("current_player_resale", "CURRENT ROSTER"),
            ("best_lower_ovr_substitute", "NEAR-EQUIVALENT ALTERNATIVE"),
            ("best_near_equivalent", "NEAR-EQUIVALENT ALTERNATIVE"),
        ):
            if item.get(key):
                add(item[key], source, f"OP-X-035 comparison role: {key}")
    return sorted(merged.values(), key=lambda row: row["card_id"])


def _event_id(event: dict[str, Any]) -> str:
    material = {
        key: event.get(key)
        for key in ("card_id", "opportunity_type", "observed_price", "threshold", "reason")
    }
    digest = hashlib.sha256(json.dumps(material, sort_keys=True).encode()).hexdigest()[:20]
    return f"opportunity:{digest}"


def reconcile_events(
    candidates: list[dict[str, Any]], state: dict[str, Any], evaluated_at: str
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    prior = state.get("events", {})
    emitted = []
    current = dict(prior)
    for candidate in candidates:
        event = {**candidate, "timestamp": evaluated_at}
        event_id = _event_id(event)
        if event_id in prior:
            continue
        event["event_id"] = event_id
        emitted.append(event)
        current[event_id] = event
    return emitted, {"schema_version": 1, "events": current, "last_run_at": evaluated_at}


def evaluate_hit_list(
    entries: list[dict[str, Any]], history: list[dict[str, Any]], as_of: str
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in history:
        grouped[row["card_id"]].append(row)
    evaluated, alerts = [], []
    for original in entries:
        row = dict(original)
        observations = sorted(
            grouped.get(row["card_id"], []), key=lambda item: item["user_observed_at"]
        )
        stats = history_statistics(observations, as_of)
        latest = observations[-1] if observations else None
        price = latest.get("observed_price") if latest else None
        qualified = stats.get("quality") in QUALIFIED
        row["latest_live_listing_evidence"] = latest
        row["latest_qualified_market_evidence"] = stats if qualified else None
        row["last_evaluated_at"] = as_of
        row["alert_state"] = "NO DATA"
        target = row.get("target_buy_price")
        watch = row.get("watch_price")
        alert_type = None
        threshold = None
        if (
            row.get("enabled", True)
            and price is not None
            and target is not None
            and price <= target
        ):
            row["alert_state"] = "BUY TARGET CROSSED"
            alert_type, threshold = "BUY TARGET", target
        elif (
            row.get("enabled", True) and price is not None and watch is not None and price <= watch
        ):
            row["alert_state"] = "WATCH TARGET CROSSED"
            alert_type, threshold = "WATCH TARGET", watch
        if alert_type:
            alerts.append(
                {
                    "card_id": row["card_id"],
                    "exact_identity": {
                        key: row.get(key)
                        for key in ("player", "position", "overall", "program", "archetype")
                    },
                    "opportunity_type": alert_type,
                    "observed_price": price,
                    "threshold": threshold,
                    "market_evidence_quality": stats.get("quality"),
                    "risk_flags": [] if qualified else ["BUY GATES NOT SATISFIED"],
                    "reason": f"observed price reached user {alert_type.lower()}",
                    "next_action": "RUN PURCHASE EVALUATION"
                    if qualified
                    else "COLLECT QUALIFYING MARKET EVIDENCE",
                }
            )
        evaluated.append(row)
    return evaluated, alerts


def flip_check(
    listing_price: int,
    sale_history: list[dict[str, Any]],
    as_of: str,
    *,
    tax_rate: float | None,
    minimum_roi: float = 0.0,
    minimum_profit: int = 1,
) -> dict[str, Any]:
    sales = [row for row in sale_history if row.get("observation_type") in SALE_TYPES]
    stats = history_statistics(sales, as_of)
    if stats.get("quality") not in QUALIFIED or tax_rate is None:
        return {
            "status": "INSUFFICIENT EVIDENCE",
            "alert": False,
            "market_quality": stats.get("quality"),
            "reason": "qualified completed-sale history and explicit fee rule required",
        }
    resale = int(stats["median"])
    net = int(resale * (1 - tax_rate))
    profit = net - listing_price
    roi = round(profit / listing_price, 6)
    alert = profit >= minimum_profit and roi >= minimum_roi
    return {
        "status": "FLIP" if alert else "PASS",
        "alert": alert,
        "purchase_price": listing_price,
        "expected_resale_basis": resale,
        "tax_rate": tax_rate,
        "net_proceeds": net,
        "projected_profit": profit,
        "roi": roi,
        "margin_of_safety": round((net - listing_price) / net, 6) if net else None,
        "market_quality": stats["quality"],
        "volatility": stats.get("dispersion_ratio"),
        "risk_flags": [] if stats.get("dispersion_ratio", 1) <= 0.15 else ["VOLATILE"],
    }


def training_check(
    price: int | None, overall: int, program: str, alternatives: list[dict[str, Any]]
) -> dict[str, Any]:
    candidate = training_economics(price, overall, program)
    if candidate["status"] == "UNSUPPORTED" or candidate["coins_per_training"] is None:
        return {**candidate, "alert": False, "reason": "verified quicksell value unavailable"}
    supported = [candidate]
    for row in alternatives:
        value = training_economics(row.get("price"), row["overall"], row["program"])
        if value.get("coins_per_training") is not None:
            supported.append(value)
    ordered = sorted(supported, key=lambda row: row["coins_per_training"])
    rank = ordered.index(candidate) + 1
    return {
        **candidate,
        "rank": rank,
        "comparison_count": len(ordered),
        "percentile": round(100 * (len(ordered) - rank + 1) / len(ordered), 6),
        "alert": rank == 1 and len(ordered) > 1,
        "reason": "best verified coins-per-training among supplied monitored listings"
        if rank == 1
        else "better monitored training listing exists",
    }


def collection_evaluate(definition: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    required = definition.get("required_number")
    pieces = inputs.get("piece_costs", [])
    if required is None or len(pieces) != required:
        return {"decision": "PASS", "status": "UNKNOWN RULES OR INCOMPLETE INPUTS"}
    gross = sum(pieces)
    returned = inputs.get("returned_cards", []) if definition.get("returns_cards") is True else []
    nominal_training = sum(int(row.get("training", 0)) for row in returned)
    cpt = inputs.get("qualified_coins_per_training")
    training_recovery = round(nominal_training * cpt) if cpt is not None else None
    resale_recovery = (
        sum(int(row.get("resale", 0)) for row in returned)
        if definition.get("returned_cards_sellable") is True
        else 0
    )
    reward_price = inputs.get("reward_sale_price")
    tax_rate = inputs.get("tax_rate")
    reward_net = (
        None
        if reward_price is None or tax_rate is None or not definition.get("reward_sellable")
        else int(reward_price * (1 - tax_rate))
    )
    recoverable = resale_recovery + (training_recovery or 0)
    effective = gross - recoverable
    sell_profit = None if reward_net is None else reward_net - effective
    keep_gain = inputs.get("reward_score_gain")
    direct = inputs.get("direct_alternative_cost")
    keep_wins = (
        keep_gain is not None and keep_gain > 0 and direct is not None and effective < direct
    )
    if sell_profit is not None and sell_profit > 0:
        decision = "SELL REWARD"
    elif keep_wins:
        decision = "KEEP REWARD"
    else:
        decision = "PASS"
    return {
        "decision": decision,
        "gross_collection_cost": gross,
        "nominal_returned_training": nominal_training,
        "training_market_replacement_value": training_recovery,
        "returned_resale_value": resale_recovery,
        "reward_net_sale_proceeds": reward_net,
        "effective_collection_cost": effective,
        "expected_profit": sell_profit,
        "roi": None if sell_profit is None or effective <= 0 else round(sell_profit / effective, 6),
        "football_score_improvement": keep_gain,
        "cost_per_pancake_point": None
        if not keep_gain or keep_gain <= 0
        else round(effective / keep_gain, 6),
        "warning": (
            "training is reported separately from coins; replacement value requires "
            "qualified coins-per-training evidence"
        ),
    }


def preposition_evaluate(state: dict[str, Any]) -> dict[str, Any]:
    eligible = state.get("collection_eligibility") is True
    price_state = state.get("market_quality")
    if not eligible:
        action = "PASS"
    elif state.get("owned"):
        action = "HOLD"
    elif price_state in QUALIFIED and state.get("at_or_below_accumulate_threshold"):
        action = "ACCUMULATE"
    else:
        action = "WATCH"
    return {
        "action": action,
        "guaranteed_profit": False,
        "forecast": None,
        "timeline_fields": [
            "T-14",
            "T-10",
            "T-7",
            "T-5",
            "T-3",
            "T-1",
            "release",
            "+6h",
            "+12h",
            "+24h",
            "+48h",
            "+7d",
        ],
    }


def monitor_run(
    root: Path,
    hit_list: list[dict[str, Any]],
    history: list[dict[str, Any]],
    state: dict[str, Any],
    as_of: str,
) -> dict[str, Any]:
    evaluated, hit_alerts = evaluate_hit_list(hit_list, history, as_of)
    universe = monitored_universe(root, evaluated, history, as_of)
    prior_top = set(state.get("top_25", []))
    tops = top_targets(root)
    entry_alerts = [
        {
            "card_id": row["card_id"],
            "opportunity_type": "TOP-10 ENTRY" if row["top_target_rank"] <= 10 else "TOP-25 ENTRY",
            "observed_price": None,
            "threshold": None,
            "market_evidence_quality": "PRICE-INDEPENDENT",
            "risk_flags": ["MARKET PRICE UNKNOWN"],
            "reason": f"entered dynamic {row['monitor_tier']}",
            "next_action": "MONITOR PRICE",
        }
        for row in tops
        if row["card_id"] not in prior_top
    ]
    events, event_state = reconcile_events([*hit_alerts, *entry_alerts], state, as_of)
    event_state["top_25"] = [row["card_id"] for row in tops]
    return {
        "hit_list": evaluated,
        "monitored_universe": universe,
        "events": events,
        "alert_state": event_state,
    }
