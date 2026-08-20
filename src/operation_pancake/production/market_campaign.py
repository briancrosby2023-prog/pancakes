"""Append-only user-observed market campaigns and evidence calibration."""

from __future__ import annotations

import hashlib
import json
import statistics
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from .market import parse_timestamp

OBSERVATION_TYPES = {
    "LOWEST_VISIBLE_LISTING",
    "VISIBLE_LISTING",
    "DISPLAYED_MARKET_PRICE",
    "RECENT_SALE",
    "COMPLETED_SALE",
    "USER_REPORTED_OTHER",
}
REAL_HISTORY = "data/production/market/user_observation_history.json"


def _now() -> str:
    return datetime.now().astimezone().isoformat()


def enrich_observation(
    card: dict[str, Any],
    price: int,
    observation_type: str,
    *,
    observed_at: str | None = None,
    ingested_at: str | None = None,
    source: str = "USER_OBSERVED_CFB_FAN",
    fixture: bool = False,
) -> dict[str, Any]:
    if not card.get("card_id"):
        raise ValueError("exact canonical card identity is required")
    if price <= 0:
        raise ValueError("observed price must be positive")
    if observation_type not in OBSERVATION_TYPES:
        raise ValueError(f"unsupported observation type: {observation_type}")
    observed_at = observed_at or _now()
    ingested_at = ingested_at or _now()
    parse_timestamp(observed_at)
    parse_timestamp(ingested_at)
    identity = {
        "card_id": card["card_id"],
        "player_name": card.get("player_name"),
        "position": card.get("position"),
        "overall": card.get("native_overall"),
        "program": card.get("program"),
        "archetype": card.get("archetype"),
    }
    stable = json.dumps(
        [card["card_id"], price, observation_type, observed_at, source], separators=(",", ":")
    ).encode()
    return {
        "observation_id": f"user-market:{hashlib.sha256(stable).hexdigest()[:20]}",
        **identity,
        "observed_price": int(price),
        "currency": "CUT_COINS",
        "observation_type": observation_type,
        "user_observed_at": observed_at,
        "source_published_at": None,
        "ingested_at": ingested_at,
        "source": source,
        "source_confidence": "USER_ATTESTED_OBSERVATION",
        "identity_confidence": "EXACT",
        "evidence_scope": "FIXTURE" if fixture else "REAL",
    }


def append_history(path: Path, observations: list[dict[str, Any]]) -> dict[str, Any]:
    if any(row.get("evidence_scope") != "REAL" for row in observations):
        raise ValueError("fixture observations cannot enter real history")
    existing = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
    by_id = {row["observation_id"]: row for row in existing}
    before = len(by_id)
    for row in observations:
        by_id.setdefault(row["observation_id"], row)
    history = sorted(
        by_id.values(), key=lambda row: (row["user_observed_at"], row["observation_id"])
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(history, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"existing": before, "appended": len(history) - before, "total": len(history)}


def history_statistics(rows: list[dict[str, Any]], as_of: str | None = None) -> dict[str, Any]:
    if not rows:
        return {"observation_count": 0, "quality": "INSUFFICIENT"}
    ordered = sorted(rows, key=lambda row: row["user_observed_at"])
    prices = [row["observed_price"] for row in ordered]
    times = [parse_timestamp(row["user_observed_at"]) for row in ordered]
    span_hours = (times[-1] - times[0]).total_seconds() / 3600
    reference = parse_timestamp(as_of) if as_of else datetime.now().astimezone()
    age_hours = (reference - times[-1]).total_seconds() / 3600
    mean = statistics.mean(prices)
    dispersion = 0.0 if len(prices) < 2 else statistics.pstdev(prices) / mean
    semantics = Counter(row["observation_type"] for row in rows)
    distinct_times = len({row["user_observed_at"] for row in rows})
    quality = evidence_quality(
        len(rows),
        distinct_times,
        span_hours,
        age_hours,
        dispersion,
        all(row.get("identity_confidence") == "EXACT" for row in rows),
        semantics,
    )
    result = {
        "observation_count": len(rows),
        "distinct_observation_times": distinct_times,
        "first_observed": ordered[0]["user_observed_at"],
        "latest_observed": ordered[-1]["user_observed_at"],
        "minimum": min(prices),
        "median": statistics.median(prices),
        "maximum": max(prices),
        "range": max(prices) - min(prices),
        "dispersion_ratio": round(dispersion, 6),
        "time_span_hours": round(span_hours, 6),
        "latest_age_hours": round(age_hours, 6),
        "observation_type_counts": dict(semantics),
        "quality": quality,
        "short_window_change": None,
        "longer_window_change": None,
        "volatility": None if len(prices) < 3 else round(dispersion, 6),
    }
    if len(prices) >= 2:
        result["short_window_change"] = round((prices[-1] - prices[-2]) / prices[-2], 6)
    if span_hours >= 24 and len(prices) >= 3:
        result["longer_window_change"] = round((prices[-1] - prices[0]) / prices[0], 6)
    return result


def evidence_quality(
    count: int,
    distinct_times: int,
    span_hours: float,
    age_hours: float,
    dispersion: float,
    exact_identity: bool,
    semantics: Counter[str],
) -> str:
    if not exact_identity or count < 2 or distinct_times < 2 or age_hours < 0:
        return "INSUFFICIENT"
    if count < 4 or distinct_times < 3 or span_hours < 24 or age_hours > 48:
        return "EARLY"
    meaningful = sum(semantics[k] for k in OBSERVATION_TYPES - {"USER_REPORTED_OTHER"})
    if meaningful < 3 or age_hours > 24:
        return "EARLY"
    if (
        count >= 8
        and distinct_times >= 5
        and span_hours >= 72
        and age_hours <= 12
        and dispersion <= 0.15
    ):
        return "STRONG"
    return "USABLE"


def calibrate_decision(
    stats: dict[str, Any],
    intrinsic_class: str,
    *,
    gross_cost: int | None,
    resale_value: int | None = None,
    budget: int | None = None,
) -> dict[str, Any]:
    quality = stats.get("quality", "INSUFFICIENT")
    if stats.get("observation_count", 0) <= 1:
        return {
            "decision": "PRICE CHECK REQUIRED",
            "reason": "another qualified observation is required",
        }
    if quality in {"INSUFFICIENT", "EARLY"}:
        return {"decision": "INSUFFICIENT MARKET DATA", "reason": f"evidence quality is {quality}"}
    net_cost = None if gross_cost is None or resale_value is None else gross_cost - resale_value
    spend = gross_cost if net_cost is None else max(0, net_cost)
    if budget is not None and spend is not None and spend > budget:
        return {
            "decision": "WAIT",
            "reason": "net/gross cost exceeds supplied budget",
            "net_cost": net_cost,
        }
    if intrinsic_class in {"PREMIUM", "OVERPAY"}:
        return {
            "decision": "WAIT",
            "reason": f"intrinsic contextual class is {intrinsic_class}",
            "net_cost": net_cost,
        }
    if quality != "STRONG":
        return {
            "decision": "WAIT",
            "reason": "usable evidence supports monitoring, not BUY",
            "net_cost": net_cost,
        }
    if intrinsic_class not in {"STRONG VALUE", "VALUE"}:
        return {
            "decision": "WAIT",
            "reason": "intrinsic value is not favorable enough",
            "net_cost": net_cost,
        }
    if stats.get("dispersion_ratio", 1) > 0.15:
        return {"decision": "WAIT", "reason": "market dispersion is too high", "net_cost": net_cost}
    if gross_cost is None or (budget is not None and spend > budget):
        return {
            "decision": "WAIT",
            "reason": "cost or affordability is unresolved",
            "net_cost": net_cost,
        }
    return {
        "decision": "BUY",
        "reason": "all independent evidence layers passed",
        "net_cost": net_cost,
    }


def watch_boundaries(stats: dict[str, Any]) -> dict[str, Any]:
    if stats.get("quality") not in {"USABLE", "STRONG"}:
        return {"status": "UNAVAILABLE", "reason": "usable longitudinal evidence required"}
    return {
        "status": "WATCH",
        "re_evaluate_at_or_below_median": stats["median"],
        "re_evaluate_at_observed_floor": stats["minimum"],
        "warning": "re-evaluation triggers are not BUY commands",
    }


def summarize_history(rows: list[dict[str, Any]], as_of: str | None = None) -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[row["card_id"]].append(row)
    return {card_id: history_statistics(card_rows, as_of) for card_id, card_rows in groups.items()}


def snapshot_report(items: list[dict[str, Any]]) -> str:
    lines = [
        "# Operation Pancake Market Snapshot",
        "",
        "| Candidate | Current | Intrinsic | Latest | Samples | Quality | Net | Decision | Next |",
        "|---|---|---:|---:|---:|---|---:|---|---|",
    ]
    for row in items:
        lines.append(
            "| {candidate} | {current} | {intrinsic} | {latest} | {samples} | {quality} | "
            "{net} | {decision} | {next} |".format(
                candidate=row["candidate"],
                current=row["current"],
                intrinsic=row["intrinsic_valuation"],
                latest=row.get("latest_price", "—"),
                samples=row.get("sample_count", 0),
                quality=row.get("quality", "INSUFFICIENT"),
                net=row.get("net_cost", "—"),
                decision=row["decision"],
                next=row.get("next_required_evidence", "new timestamped observation"),
            )
        )
    return "\n".join(lines) + "\n"


def prioritize_collection(values: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Minimize burden by checking favorable intrinsic opportunities first."""
    class_order = {"STRONG VALUE": 0, "VALUE": 1, "FAIR": 2, "PREMIUM": 3, "OVERPAY": 4}
    return sorted(
        values,
        key=lambda row: (
            class_order.get(row.get("relative_valuation"), 5),
            -float(row.get("value_index", 0)),
            row.get("candidate", ""),
        ),
    )
