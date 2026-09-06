"""Conservative time-aware CUT market forecasting primitives.

Forecasts require timestamped completed-sale evidence. Insufficient history returns
UNKNOWN rather than manufacturing confidence.
"""
from __future__ import annotations

import math
import statistics
from collections import defaultdict
from datetime import datetime
from typing import Any

from .market import parse_timestamp

SUPPORTED_HORIZONS_MINUTES = (30, 60, 120, 240, 480)
SALE_TYPES = {"COMPLETED_SALE", "RECENT_SALE"}
TAX_RATE = 0.10


def _timestamp(row: dict[str, Any]) -> datetime:
    value = row.get("user_observed_at") or row.get("observed_at")
    if not value:
        raise ValueError("timestamped market evidence is required")
    return parse_timestamp(str(value))


def completed_sales(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        [row for row in rows if row.get("observation_type") in SALE_TYPES],
        key=_timestamp,
    )


def intraday_profile(rows: list[dict[str, Any]]) -> dict[str, Any]:
    sales = completed_sales(rows)
    by_hour: dict[int, list[int]] = defaultdict(list)
    for row in sales:
        by_hour[_timestamp(row).hour].append(int(row["observed_price"]))
    overall = statistics.median([int(row["observed_price"]) for row in sales]) if sales else None
    hours = {}
    for hour, prices in sorted(by_hour.items()):
        median = statistics.median(prices)
        hours[str(hour)] = {
            "samples": len(prices),
            "median": median,
            "effect_vs_overall": None if overall is None else round(median / overall - 1, 6),
        }
    return {"completed_sales": len(sales), "overall_median": overall, "hours": hours}


def forecast(rows: list[dict[str, Any]], as_of: str, horizon_minutes: int) -> dict[str, Any]:
    if horizon_minutes not in SUPPORTED_HORIZONS_MINUTES:
        raise ValueError("unsupported forecast horizon")
    sales = [row for row in completed_sales(rows) if _timestamp(row) <= parse_timestamp(as_of)]
    if len(sales) < 8 or len({_timestamp(row) for row in sales}) < 5:
        return {"status": "INSUFFICIENT DATA", "horizon_minutes": horizon_minutes, "sample_count": len(sales), "forecast_price": None, "forecast_range": None, "confidence": "NONE"}
    prices = [int(row["observed_price"]) for row in sales]
    recent = prices[-min(8, len(prices)):]
    center = statistics.median(recent)
    mad = statistics.median([abs(price - center) for price in recent])
    profile = intraday_profile(sales)
    future_hour = (parse_timestamp(as_of).hour + horizon_minutes // 60) % 24
    bucket = profile["hours"].get(str(future_hour))
    effect = 0.0 if not bucket or bucket["samples"] < 2 else float(bucket["effect_vs_overall"])
    predicted = max(1, round(center * (1 + effect)))
    spread = max(round(predicted * 0.05), round(1.4826 * mad))
    dispersion = statistics.pstdev(recent) / statistics.mean(recent) if len(recent) > 1 else 0.0
    confidence = "MEDIUM" if len(sales) >= 20 and dispersion <= 0.15 else "LOW"
    return {"status": "FORECAST", "horizon_minutes": horizon_minutes, "sample_count": len(sales), "forecast_price": predicted, "forecast_range": [max(1, predicted - spread), predicted + spread], "confidence": confidence, "time_of_day_effect": round(effect, 6), "liquidity": "SUPPORTED" if len(sales) >= 8 else "UNKNOWN", "downside": max(0, predicted - spread), "method": "recent median plus observed same-hour completed-sale effect"}


def exit_probability(rows: list[dict[str, Any]], exit_price: int, horizon_minutes: int, as_of: str) -> float | None:
    sales = [row for row in completed_sales(rows) if _timestamp(row) <= parse_timestamp(as_of)]
    if len(sales) < 8:
        return None
    cutoff_seconds = horizon_minutes * 60
    hits = 0
    trials = 0
    for index, row in enumerate(sales[:-1]):
        start = _timestamp(row)
        future = [x for x in sales[index + 1:] if 0 < (_timestamp(x) - start).total_seconds() <= cutoff_seconds]
        if not future:
            continue
        trials += 1
        hits += any(int(x["observed_price"]) >= exit_price for x in future)
    return None if trials < 3 else round(hits / trials, 6)


def buy_economics(forecast_sell_price: int, buy_price: int) -> dict[str, int | float]:
    net_proceeds = math.floor(forecast_sell_price * (1 - TAX_RATE))
    return {"tax_rate": TAX_RATE, "forecast_sell_price": forecast_sell_price, "buy_price": buy_price, "net_proceeds": net_proceeds, "net_profit": net_proceeds - buy_price}


def buy_ceiling(forecast_sell_price: int, minimum_net_profit: int) -> int:
    return math.floor(forecast_sell_price * (1 - TAX_RATE)) - minimum_net_profit


def rank_opportunity(expected_net_profit: int, exit_probability_value: float | None, expected_hold_minutes: int | None, confidence: str) -> float | None:
    if exit_probability_value is None or expected_hold_minutes is None or expected_hold_minutes <= 0:
        return None
    confidence_weight = {"LOW": 0.5, "MEDIUM": 0.75, "HIGH": 1.0}.get(confidence, 0.0)
    return round(expected_net_profit * exit_probability_value * confidence_weight / expected_hold_minutes, 6)


def sell_decision(current_sell_price: int, forecast_sell_price: int, purchase_price: int, expected_hold_minutes: int, confidence: str) -> dict[str, Any]:
    now = buy_economics(current_sell_price, purchase_price)
    later = buy_economics(forecast_sell_price, purchase_price)
    additional = int(later["net_profit"]) - int(now["net_profit"])
    hold = confidence in {"MEDIUM", "HIGH"} and additional > 0
    return {"action": "HOLD" if hold else "SELL NOW", "quick_exit_price": current_sell_price, "forecast_normal_exit": forecast_sell_price, "expected_after_tax_profit_now": now["net_profit"], "expected_after_tax_profit_later": later["net_profit"], "expected_additional_profit_from_waiting": additional, "expected_hold_minutes": expected_hold_minutes, "confidence": confidence}
