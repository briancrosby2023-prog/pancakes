"""Campaign-based longitudinal market recorder with strict evidence semantics."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import statistics
from collections import Counter
from datetime import timedelta
from pathlib import Path
from typing import Any

from .market import CORE_TRAINING_QUICKSELL, parse_timestamp
from .market_campaign import history_statistics
from .monitor import canonical_cards, load_json, monitor_run, save_json
from .transition import WINDOW_LABELS, checkpoint_time

RECORDER_HISTORY = "data/production/market/longitudinal_observations.json"
CAMPAIGN_STATE = "data/production/market/campaigns.json"
RECORDER_STATE = "data/production/market/recorder_state.json"
SEMANTICS = {
    "LIVE_LISTING": {"unit": "CUT_COINS", "class": "LISTING"},
    "LOWEST_VISIBLE_LISTING": {"unit": "CUT_COINS", "class": "LISTING"},
    "DISPLAYED_MARKET_PRICE": {"unit": "CUT_COINS", "class": "DISPLAY"},
    "COMPLETED_SALE": {"unit": "CUT_COINS", "class": "SALE"},
    "MEDIAN_COMPLETED_SALE": {"unit": "CUT_COINS", "class": "SALE_STATISTIC"},
    "PRICE_TRACKER_VALUE": {"unit": "CUT_COINS", "class": "TRACKER"},
    "SUPPLY_COUNT": {"unit": "COUNT", "class": "SUPPLY"},
    "SALE_VOLUME": {"unit": "COUNT", "class": "VOLUME"},
    "TRAINING_BASKET": {"unit": "CUT_COINS", "class": "TRAINING"},
    "COLLECTION_COMPONENT": {"unit": "CUT_COINS", "class": "COLLECTION"},
    "CURRENT_PLAYER_RESALE": {"unit": "CUT_COINS", "class": "RESALE"},
}
PRICE_TYPES = {key for key, value in SEMANTICS.items() if value["unit"] == "CUT_COINS"}
CAMPAIGN_TYPES = {
    "PERSONAL HIT LIST",
    "PANCAKE TOP 10",
    "PANCAKE TOP 25",
    "ROSTER UPGRADES",
    "NEAR-EQUIVALENT ALTERNATIVES",
    "SCHEME / COLLECTION",
    "TRAINING BASKET",
    "EVENT WINDOW",
    "SEASON TRANSITION",
}


def stable_id(parts: list[Any]) -> str:
    digest = hashlib.sha256(
        json.dumps(parts, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()[:20]
    return f"recorder:{digest}"


def default_campaign(root: Path, now: str) -> dict[str, Any]:
    universe = load_json(root / "data/research/op_x_036/monitored_universe.json", {"cards": []})
    targets = []
    for row in universe["cards"]:
        sources = row["sources"]
        if "PERSONAL HIT LIST" in sources or "TOP 10" in sources or "ROSTER BUY TARGET" in sources:
            priority, tier = 1, "TIER 1"
        elif "TOP 25" in sources or "NEAR-EQUIVALENT ALTERNATIVE" in sources:
            priority, tier = 2, "TIER 2"
        else:
            priority, tier = 3, "TIER 3"
        targets.append(
            {
                "card_id": row["card_id"],
                "priority": priority,
                "tier": tier,
                "reasons": row["reasons"],
                "sources": sources,
            }
        )
    return {
        "campaign_id": "pancake-default-monitored-universe-v1",
        "campaign_type": "PANCAKE TOP 25",
        "schema_version": 1,
        "cards": sorted(targets, key=lambda row: (row["priority"], row["card_id"])),
        "reason": "deduplicated OP-X-036 monitored universe",
        "start_time": now,
        "end_time": None,
        "desired_cadence_minutes": {"1": 60, "2": 240, "3": 720},
        "observation_types_requested": [
            "LOWEST_VISIBLE_LISTING",
            "COMPLETED_SALE",
            "SUPPLY_COUNT",
            "SALE_VOLUME",
        ],
        "event_id": None,
        "priority": 1,
        "active": True,
        "last_successful_observation": None,
        "next_due_observation": now,
        "sample_sufficiency": "NO DATA",
    }


def deduplicated_targets(campaigns: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for campaign in campaigns:
        if not campaign.get("active", True):
            continue
        for target in campaign.get("cards", []):
            row = merged.setdefault(
                target["card_id"],
                {
                    "card_id": target["card_id"],
                    "campaign_ids": [],
                    "reasons": [],
                    "sources": [],
                    "priority": 99,
                },
            )
            row["campaign_ids"].append(campaign["campaign_id"])
            row["priority"] = min(
                row["priority"], target.get("priority", campaign.get("priority", 99))
            )
            for key in ("reasons", "sources"):
                for value in target.get(key, []):
                    if value not in row[key]:
                        row[key].append(value)
    return sorted(merged.values(), key=lambda row: (row["priority"], row["card_id"]))


def normalize_record(
    raw: dict[str, Any],
    cards: dict[str, dict[str, Any]],
    campaigns: dict[str, dict[str, Any]],
    *,
    ingested_at: str,
    fixture: bool = False,
) -> dict[str, Any]:
    card_id = raw.get("card_id")
    if card_id not in cards:
        raise ValueError("ambiguous or unresolved canonical card identity")
    observation_type = raw.get("observation_type")
    if observation_type not in SEMANTICS:
        raise ValueError("unsupported observation semantics")
    value = raw.get("value")
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError("observation value must be a positive integer")
    observed_at = raw.get("observed_at")
    if not observed_at:
        raise ValueError("observed_at is required")
    observed = parse_timestamp(observed_at)
    ingested = parse_timestamp(ingested_at)
    available_at = raw.get("available_at", observed_at)
    available = parse_timestamp(available_at)
    if observed > ingested or available > ingested:
        raise ValueError("future timestamp rejected")
    if available < observed:
        raise ValueError("timestamp reversal rejected")
    campaign_id = raw.get("campaign_id")
    if campaign_id not in campaigns:
        raise ValueError("unknown campaign")
    allowed = {row["card_id"] for row in campaigns[campaign_id].get("cards", [])}
    if card_id not in allowed:
        raise ValueError("campaign/card mismatch")
    platform = raw.get("platform", "UNKNOWN")
    expected_platform = campaigns[campaign_id].get("platform")
    if expected_platform and expected_platform != platform:
        raise ValueError("platform mismatch")
    card = cards[card_id]
    identity = {
        "card_id": card_id,
        "player_name": card.get("player_name"),
        "position": card.get("position"),
        "overall": card.get("native_overall"),
        "program": card.get("program"),
        "archetype": card.get("archetype"),
    }
    record_id = stable_id(
        [
            card_id,
            value,
            observation_type,
            observed_at,
            available_at,
            raw.get("source"),
            platform,
            campaign_id,
        ]
    )
    return {
        "observation_id": record_id,
        **identity,
        "value": value,
        "observed_price": value if observation_type in PRICE_TYPES else None,
        "observation_type": observation_type,
        "source_semantics": SEMANTICS[observation_type],
        "source": raw.get("source", "USER_BROWSER_ASSISTED"),
        "observed_at": observed_at,
        "user_observed_at": observed_at,
        "ingested_at": ingested_at,
        "available_at": available_at,
        "platform": platform,
        "provenance": raw.get("provenance", "USER_EXPORT"),
        "confidence": raw.get("confidence", "USER_ATTESTED"),
        "identity_confidence": "EXACT",
        "campaign_id": campaign_id,
        "event_id": campaigns[campaign_id].get("event_id"),
        "evidence_scope": "FIXTURE" if fixture else "REAL",
        "sequence": raw.get("sequence"),
        "listing_age_minutes": raw.get("listing_age_minutes"),
        "second_lowest_listing": raw.get("second_lowest_listing"),
    }


def parse_browser_export(text: str, format_name: str) -> list[dict[str, Any]]:
    if format_name == "json":
        payload = json.loads(text)
        if not isinstance(payload, list):
            raise ValueError("JSON export must be a list")
        return payload
    if format_name == "csv":
        return list(csv.DictReader(io.StringIO(text)))
    raise ValueError("supported import formats are json and csv")


def append_records(path: Path, rows: list[dict[str, Any]], *, production: bool) -> dict[str, Any]:
    if production and any(row.get("evidence_scope") != "REAL" for row in rows):
        raise ValueError("fixture observations cannot enter production history")
    existing = load_json(path, [])
    by_id = {row["observation_id"]: row for row in existing}
    before = len(by_id)
    for row in rows:
        by_id.setdefault(row["observation_id"], row)
    result = sorted(by_id.values(), key=lambda row: (row["observed_at"], row["observation_id"]))
    save_json(path, result)
    return {
        "existing": before,
        "appended": len(result) - before,
        "total": len(result),
        "records": result,
    }


def completed_sale_statistics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    sales = sorted(
        (
            row
            for row in rows
            if row["observation_type"] in {"COMPLETED_SALE", "MEDIAN_COMPLETED_SALE"}
        ),
        key=lambda row: row["observed_at"],
    )
    values = [row["value"] for row in sales]
    if not values:
        return {"count": 0, "status": "NO DATA"}
    times = [parse_timestamp(row["observed_at"]) for row in sales]
    intervals = [(b - a).total_seconds() / 3600 for a, b in zip(times, times[1:], strict=False)]
    return {
        "count": len(values),
        "median": statistics.median(values),
        "mean": round(statistics.mean(values), 6),
        "minimum": min(values),
        "maximum": max(values),
        "range": max(values) - min(values),
        "dispersion": 0.0
        if len(values) < 2
        else round(statistics.pstdev(values) / statistics.mean(values), 6),
        "trend": None if len(values) < 2 else round((values[-1] - values[0]) / values[0], 6),
        "mean_hours_between_sales": None if not intervals else round(statistics.mean(intervals), 6),
        "sale_velocity_per_day": None
        if not intervals or sum(intervals) == 0
        else round((len(values) - 1) * 24 / sum(intervals), 6),
    }


def listing_statistics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    listings = [row for row in rows if SEMANTICS[row["observation_type"]]["class"] == "LISTING"]
    supplies = [row["value"] for row in rows if row["observation_type"] == "SUPPLY_COUNT"]
    prices = [row["value"] for row in listings]
    return {
        "listing_samples": len(listings),
        "supply_samples": len(supplies),
        "lowest_listing": min(prices) if prices else None,
        "second_lowest_listing": next(
            (
                row.get("second_lowest_listing")
                for row in reversed(listings)
                if row.get("second_lowest_listing") is not None
            ),
            None,
        ),
        "latest_supply_count": supplies[-1] if supplies else None,
    }


def sample_sufficiency(
    rows: list[dict[str, Any]], as_of: str, event: dict[str, Any] | None = None
) -> dict[str, Any]:
    price_rows = [row for row in rows if row["observation_type"] in PRICE_TYPES]
    compatible = [
        {**row, "observed_price": row["value"], "user_observed_at": row["observed_at"]}
        for row in price_rows
    ]
    stats = history_statistics(compatible, as_of)
    types = Counter(row["observation_type"] for row in rows)
    coverage = event_checkpoint_coverage(event, rows) if event else None
    return {
        "state": "NO DATA" if not rows else stats.get("quality", "INSUFFICIENT"),
        "observations": len(rows),
        "distinct_times": len({row["observed_at"] for row in rows}),
        "timespan_hours": stats.get("time_span_hours", 0),
        "freshness_hours": stats.get("latest_age_hours"),
        "sale_samples": types["COMPLETED_SALE"] + types["MEDIAN_COMPLETED_SALE"],
        "listing_samples": types["LIVE_LISTING"] + types["LOWEST_VISIBLE_LISTING"],
        "supply_samples": types["SUPPLY_COUNT"],
        "volume_samples": types["SALE_VOLUME"],
        "event_checkpoint_coverage": coverage,
    }


def register_event(raw: dict[str, Any]) -> dict[str, Any]:
    if not raw.get("release_time"):
        raise ValueError("verified release_time is required")
    parse_timestamp(raw["release_time"])
    if not raw.get("source") or not raw.get("confidence"):
        raise ValueError("event source and confidence are required")
    return {
        **raw,
        "checkpoints": {
            label: checkpoint_time(raw["release_time"], label).isoformat()
            for label in WINDOW_LABELS
        },
        "unknown_fields": raw.get("unknown_fields", []),
    }


def event_checkpoint_coverage(
    event: dict[str, Any] | None, rows: list[dict[str, Any]]
) -> dict[str, Any] | None:
    if not event:
        return None
    checkpoints = event["checkpoints"]
    observed = {row.get("checkpoint") for row in rows if row.get("checkpoint")}
    return {
        "observed": [label for label in checkpoints if label in observed],
        "missing": [label for label in checkpoints if label not in observed],
    }


def training_basket(card_rows: list[dict[str, Any]], version: str) -> dict[str, Any]:
    unsupported = [
        row["card_id"] for row in card_rows if row["overall"] not in CORE_TRAINING_QUICKSELL
    ]
    if unsupported:
        raise ValueError(f"unsupported training quicksell tiers: {unsupported}")
    return {
        "basket_version": version,
        "composition_frozen": True,
        "cards": [
            {**row, "training": CORE_TRAINING_QUICKSELL[row["overall"]]} for row in card_rows
        ],
    }


def longitudinal_export(
    rows: list[dict[str, Any]], events: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    return [
        {
            "observation_id": row["observation_id"],
            "card_id": row["card_id"],
            "value": row["value"],
            "observation_type": row["observation_type"],
            "observed_at": row["observed_at"],
            "available_at": row["available_at"],
            "event_time": events.get(row.get("event_id"), {}).get("release_time"),
            "campaign_id": row["campaign_id"],
            "event_id": row.get("event_id"),
            "platform": row["platform"],
            "source": row["source"],
            "provenance": row["provenance"],
            "confidence": row["confidence"],
        }
        for row in sorted(rows, key=lambda item: (item["available_at"], item["observation_id"]))
    ]


def run_snapshot(
    root: Path,
    raw_rows: list[dict[str, Any]],
    campaigns: list[dict[str, Any]],
    state: dict[str, Any],
    *,
    ingested_at: str,
    fixture: bool = False,
    persist: bool = False,
) -> dict[str, Any]:
    cards = canonical_cards(root)
    campaign_map = {row["campaign_id"]: row for row in campaigns if row.get("active", True)}
    accepted, failures = [], []
    for index, raw in enumerate(raw_rows):
        try:
            accepted.append(
                normalize_record(raw, cards, campaign_map, ingested_at=ingested_at, fixture=fixture)
            )
        except (TypeError, ValueError, KeyError) as error:
            failures.append({"index": index, "reason": str(error), "retry_eligible": True})
    history_path = root / RECORDER_HISTORY
    existing = load_json(history_path, [])
    combined = {row["observation_id"]: row for row in [*existing, *accepted]}
    records = sorted(combined.values(), key=lambda row: (row["observed_at"], row["observation_id"]))
    if persist:
        append_records(history_path, accepted, production=True)
    price_history = [
        {**row, "observed_price": row["value"], "user_observed_at": row["observed_at"]}
        for row in records
        if row["observation_type"] in PRICE_TYPES
    ]
    monitor = monitor_run(
        root,
        load_json(root / "data/production/monitor/hit_list.json", []),
        price_history,
        state.get("alert_state", {}),
        ingested_at,
    )
    return {
        "accepted": len(accepted),
        "failures": failures,
        "partial_success": bool(accepted) and bool(failures),
        "records": records,
        "new_events": monitor["events"],
        "alert_state": monitor["alert_state"],
        "deterministic_key": stable_id([row["observation_id"] for row in records]),
    }


def scheduler_state(
    campaign: dict[str, Any], now: str, *, success: bool, failure_reason: str | None = None
) -> dict[str, Any]:
    current = parse_timestamp(now)
    cadence = (
        int(campaign.get("desired_cadence_minutes", 240))
        if isinstance(campaign.get("desired_cadence_minutes"), int)
        else 240
    )
    failures = 0 if success else int(campaign.get("consecutive_failures", 0)) + 1
    return {
        **campaign,
        "last_run": now,
        "next_due": (current + timedelta(minutes=cadence)).isoformat(),
        "last_success": now if success else campaign.get("last_success"),
        "last_failure": None if success else now,
        "failure_reason": failure_reason,
        "consecutive_failures": failures,
    }
