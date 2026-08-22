"""Forecast-aware PS5 market watch integration over the existing alert reconciler."""
from __future__ import annotations

import statistics
from collections import Counter, defaultdict
from typing import Any

from .market import parse_timestamp
from .market_forecast import (
    buy_ceiling,
    buy_economics,
    completed_sales,
    exit_probability,
    forecast,
    rank_opportunity,
)
from .monitor import reconcile_events

LISTING_TYPES = {"LOWEST_VISIBLE_LISTING", "LIVE_LISTING"}


def _timestamp(row: dict[str, Any]):
    return parse_timestamp(str(row.get("user_observed_at") or row.get("observed_at")))


def current_listing(rows: list[dict[str, Any]], as_of: str) -> dict[str, Any] | None:
    cutoff = parse_timestamp(as_of)
    listings = [
        row
        for row in rows
        if row.get("observation_type") in LISTING_TYPES and _timestamp(row) <= cutoff
    ]
    return max(listings, key=_timestamp) if listings else None


def buy_window_evidence(rows: list[dict[str, Any]], as_of: str) -> dict[str, Any]:
    """Describe measured timing/supply evidence without converting hypotheses into priors."""
    cutoff = parse_timestamp(as_of)
    sales = [row for row in completed_sales(rows) if _timestamp(row) <= cutoff]
    listing = current_listing(rows, as_of)
    prices = [int(row["observed_price"]) for row in sales]
    by_hour: dict[int, list[int]] = defaultdict(list)
    by_weekday: dict[int, list[int]] = defaultdict(list)
    for row in sales:
        stamp = _timestamp(row)
        by_hour[stamp.hour].append(int(row["observed_price"]))
        by_weekday[stamp.weekday()].append(int(row["observed_price"]))
    supply = [
        row
        for row in rows
        if row.get("observation_type") == "SUPPLY_COUNT" and _timestamp(row) <= cutoff
    ]
    volume = [
        row
        for row in rows
        if row.get("observation_type") == "SALE_VOLUME" and _timestamp(row) <= cutoff
    ]
    intervals = [
        (_timestamp(b) - _timestamp(a)).total_seconds() / 3600
        for a, b in zip(sales, sales[1:], strict=False)
    ]
    return {
        "completed_sale_count": len(sales),
        "completed_sale_median": statistics.median(prices) if prices else None,
        "price_dispersion": (
            None
            if len(prices) < 2
            else round(statistics.pstdev(prices) / statistics.mean(prices), 6)
        ),
        "sale_velocity_per_day": (
            None
            if not intervals or sum(intervals) <= 0
            else round((len(sales) - 1) * 24 / sum(intervals), 6)
        ),
        "current_live_floor": None if listing is None else listing.get("observed_price"),
        "latest_supply": None if not supply else supply[-1].get("value"),
        "latest_sale_volume": None if not volume else volume[-1].get("value"),
        "hour_of_day_samples": dict(
            sorted(Counter(_timestamp(row).hour for row in sales).items())
        ),
        "day_of_week_samples": dict(
            sorted(Counter(_timestamp(row).weekday() for row in sales).items())
        ),
        "hour_of_day_medians": {
            str(key): statistics.median(value) for key, value in sorted(by_hour.items())
        },
        "day_of_week_medians": {
            str(key): statistics.median(value)
            for key, value in sorted(by_weekday.items())
        },
    }


def forecast_watch(
    card: dict[str, Any],
    rows: list[dict[str, Any]],
    as_of: str,
    *,
    horizon_minutes: int = 120,
    minimum_net_profit: int = 5000,
    static_buy_ceiling: int | None = None,
) -> dict[str, Any]:
    listing = current_listing(rows, as_of)
    live_price = None if listing is None else listing.get("observed_price")
    model = forecast(rows, as_of, horizon_minutes)
    evidence = buy_window_evidence(rows, as_of)
    exact_version = {
        key: card.get(key)
        for key in (
            "card_id",
            "player_name",
            "position",
            "native_overall",
            "program",
            "archetype",
        )
    }
    base = {
        "card": card.get("player_name"),
        "exact_version": exact_version,
        "live_price": live_price,
        "forecast_state": model["status"],
        "forecast_horizon_minutes": horizon_minutes,
        "evidence_quality": model.get("confidence", "NONE"),
        "buy_window_evidence": evidence,
    }
    if model["status"] != "FORECAST":
        action = (
            "WATCH"
            if live_price is not None
            and static_buy_ceiling is not None
            and live_price <= static_buy_ceiling
            else "INSUFFICIENT DATA"
        )
        return {
            **base,
            "buy_ceiling": static_buy_ceiling,
            "forecast_exit": None,
            "forecast_range": None,
            "after_tax_net_profit": None,
            "net_proceeds": None,
            "expected_hold_minutes": None,
            "exit_probability": None,
            "confidence": "NONE",
            "liquidity": "UNKNOWN",
            "risk": ["INSUFFICIENT FORECAST HISTORY"],
            "action": action,
            "priority_score": None,
        }
    exit_price = int(model["forecast_price"])
    ceiling = buy_ceiling(exit_price, minimum_net_profit)
    probability = exit_probability(rows, exit_price, horizon_minutes, as_of)
    economics = None if live_price is None else buy_economics(exit_price, int(live_price))
    downside = model.get("forecast_range", [None])[0]
    risk = []
    if probability is None:
        risk.append("EXIT PROBABILITY INSUFFICIENT")
    if model.get("confidence") == "LOW":
        risk.append("LOW FORECAST CONFIDENCE")
    if live_price is None:
        action = "NO ACTION"
    elif int(live_price) <= ceiling:
        action = "BUY"
    else:
        action = "WATCH"
    priority = (
        None
        if economics is None
        else rank_opportunity(
            int(economics["net_profit"]),
            probability,
            horizon_minutes,
            str(model["confidence"]),
        )
    )
    return {
        **base,
        "buy_ceiling": ceiling,
        "forecast_exit": exit_price,
        "forecast_range": model.get("forecast_range"),
        "after_tax_net_profit": None if economics is None else economics["net_profit"],
        "net_proceeds": None if economics is None else economics["net_proceeds"],
        "tax_rate": 0.10,
        "expected_hold_minutes": horizon_minutes,
        "exit_probability": probability,
        "confidence": model["confidence"],
        "liquidity": model.get("liquidity", "UNKNOWN"),
        "risk": risk,
        "downside": downside,
        "action": action,
        "priority_score": priority,
    }


def alert_candidate(result: dict[str, Any]) -> dict[str, Any] | None:
    if result["action"] not in {"BUY", "WATCH"} or result.get("live_price") is None:
        return None
    return {
        "card_id": result["exact_version"]["card_id"],
        "exact_identity": result["exact_version"],
        "opportunity_type": (
            "BUY TARGET" if result["action"] == "BUY" else "WATCH TARGET"
        ),
        "observed_price": result["live_price"],
        "threshold": result.get("buy_ceiling"),
        "forecast_exit": result.get("forecast_exit"),
        "forecast_range": result.get("forecast_range"),
        "forecast_horizon_minutes": result.get("forecast_horizon_minutes"),
        "after_tax_net_profit": result.get("after_tax_net_profit"),
        "expected_hold_minutes": result.get("expected_hold_minutes"),
        "exit_probability": result.get("exit_probability"),
        "confidence": result.get("confidence"),
        "liquidity": result.get("liquidity"),
        "risk_flags": result.get("risk", []),
        "market_evidence_quality": result.get("evidence_quality"),
        "action": result["action"],
        "reason": "rendered PS5 live price evaluated against legitimate market threshold",
    }


def watcher_alerts(
    results: list[dict[str, Any]], state: dict[str, Any], evaluated_at: str
):
    candidates = [
        candidate
        for result in results
        if (candidate := alert_candidate(result)) is not None
    ]
    return reconcile_events(candidates, state, evaluated_at)


def prioritize(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Rank only opportunities whose evidence supports a deterministic score."""
    supported = [result for result in results if result.get("priority_score") is not None]
    return sorted(
        supported,
        key=lambda result: (
            -float(result["priority_score"]),
            result["exact_version"]["card_id"],
        ),
    )


def search_queue(
    card_histories: list[tuple[dict[str, Any], list[dict[str, Any]]]],
    as_of: str,
    *,
    horizon_minutes: int = 120,
) -> list[dict[str, Any]]:
    """Build deterministic EXPLOIT/EXPLORE inspection work from legitimate evidence."""
    now = parse_timestamp(as_of)
    queue = []
    for card, rows in card_histories:
        result = forecast_watch(card, rows, as_of, horizon_minutes=horizon_minutes)
        sales = [row for row in completed_sales(rows) if _timestamp(row) <= now]
        latest = max((_timestamp(row) for row in rows if _timestamp(row) <= now), default=None)
        age_minutes = None if latest is None else int((now - latest).total_seconds() / 60)
        if result["forecast_state"] == "FORECAST" and result["priority_score"] is not None:
            queue_class = "EXPLOIT"
            priority = float(result["priority_score"])
            reason = "evidence supports expected opportunity economics"
            evidence_needed = ["live listings"]
        else:
            queue_class = "EXPLORE"
            # Information value rises as legitimate completed-sale history approaches readiness,
            # and with staleness. Capital size is deliberately absent from this score.
            progress = min(len(sales), 8) / 8
            freshness_need = 1.0 if age_minutes is None else min(max(age_minutes, 0) / 1440, 1.0)
            priority = round(progress * 100 + freshness_need * 10, 6)
            reason = "another legitimate observation can improve forecast readiness or freshness"
            evidence_needed = ["completed sales", "live listings", "sales volume", "price history"]
        queue.append(
            {
                "queue_class": queue_class,
                "exact_version": result["exact_version"],
                "priority": priority,
                "reason": reason,
                "evidence_age_minutes": age_minutes,
                "last_observed_live_floor": result["live_price"],
                "forecast_state": result["forecast_state"],
                "forecast_exit": result["forecast_exit"],
                "buy_ceiling": result["buy_ceiling"] if result["forecast_state"] == "FORECAST" else None,
                "expected_net_profit": result["after_tax_net_profit"],
                "exit_probability": result["exit_probability"],
                "liquidity": result["liquidity"],
                "expected_hold_minutes": result["expected_hold_minutes"],
                "confidence": result["confidence"],
                "downside_risk": result.get("downside"),
                "next_observation_value": priority if queue_class == "EXPLORE" else None,
                "evidence_needed": evidence_needed,
            }
        )
    return sorted(
        queue,
        key=lambda item: (
            0 if item["queue_class"] == "EXPLOIT" else 1,
            -float(item["priority"]),
            item["exact_version"]["card_id"],
        ),
    )


def next_opera_inspection(queue: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Return the next read-only rendered-market inspection contract."""
    if not queue:
        return None
    target = queue[0]
    return {
        "next_card_to_inspect": target["exact_version"],
        "why": target["reason"],
        "what_evidence_is_needed": target["evidence_needed"],
        "collector_mode": "READ ONLY",
    }
