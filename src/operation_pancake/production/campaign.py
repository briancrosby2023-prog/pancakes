"""Adaptive manual market campaign and evidence-limited arbitrage services."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from .engine import load_population
from .market_campaign import enrich_observation, history_statistics


def parse_compact_snapshot(
    text: str,
    cards: dict[str, dict[str, Any]],
    *,
    observed_at: str,
    ingested_at: str,
    observation_type: str = "LOWEST_VISIBLE_LISTING",
    fixture: bool = False,
) -> list[dict[str, Any]]:
    """Parse newline-separated ``CARD_ID PRICE`` observations."""
    observations = []
    for line_number, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        parts = stripped.split()
        if len(parts) != 2:
            raise ValueError(f"line {line_number}: expected CARD_ID PRICE")
        card_id, raw_price = parts
        if card_id not in cards:
            raise ValueError(f"line {line_number}: unresolved canonical card ID {card_id}")
        if not raw_price.isdecimal():
            raise ValueError(f"line {line_number}: price must be a positive integer")
        observations.append(
            enrich_observation(
                cards[card_id],
                int(raw_price),
                observation_type,
                observed_at=observed_at,
                ingested_at=ingested_at,
                fixture=fixture,
                reject_future=True,
            )
        )
    return observations


def evidence_blocker(stats: dict[str, Any]) -> str:
    quality = stats.get("quality", "INSUFFICIENT")
    count = stats.get("observation_count", 0)
    distinct = stats.get("distinct_observation_times", 0)
    span = stats.get("time_span_hours", 0)
    if count == 0:
        return "NO DATA — NEED FIRST OBSERVATION"
    if count < 2:
        return "WAIT — NEED 1 MORE OBSERVATION"
    if distinct < 3:
        return f"WAIT — NEED {3 - distinct} MORE DISTINCT TIMESTAMPS"
    if span < 24:
        return "WAIT — NEED 24-HOUR SPAN"
    if stats.get("latest_age_hours", 0) > 48:
        return "WAIT — MARKET EVIDENCE STALE"
    if stats.get("dispersion_ratio", 0) > 0.15:
        return "WAIT — PRICE VOLATILE"
    if quality == "USABLE":
        return "WAIT — NEED STRONG EVIDENCE FOR BUY"
    return "ALL MARKET EVIDENCE GATES SATISFIED" if quality == "STRONG" else f"WAIT — {quality}"


def movement(stats: dict[str, Any]) -> dict[str, Any]:
    count = stats.get("observation_count", 0)
    change = stats.get("short_window_change")
    dispersion = stats.get("dispersion_ratio", 0)
    if count < 2 or change is None:
        direction = "INSUFFICIENT HISTORY"
    elif dispersion > 0.15:
        direction = "VOLATILE"
    elif change > 0.03:
        direction = "RISING"
    elif change < -0.03:
        direction = "FALLING"
    else:
        direction = "STABLE"
    return {
        "latest": stats.get("latest"),
        "median": stats.get("median"),
        "minimum": stats.get("minimum"),
        "maximum": stats.get("maximum"),
        "absolute_change": stats.get("absolute_change"),
        "percentage_change": change,
        "direction": direction,
        "dispersion": stats.get("dispersion_ratio"),
        "volatility": stats.get("volatility"),
        "time_span_hours": stats.get("time_span_hours"),
    }


def campaign_round(
    round_id: str,
    requested: list[str],
    observations: list[dict[str, Any]],
    prior_prices: dict[str, int] | None = None,
) -> dict[str, Any]:
    observed = {row["card_id"]: row for row in observations}
    prior_prices = prior_prices or {}
    return {
        "round_id": round_id,
        "observation_time": min((row["user_observed_at"] for row in observations), default=None),
        "cards_requested": requested,
        "cards_observed": sorted(observed),
        "cards_missing": sorted(set(requested) - set(observed)),
        "changes_from_prior": {
            card_id: row["observed_price"] - prior_prices[card_id]
            for card_id, row in observed.items()
            if card_id in prior_prices
        },
    }


def build_campaign(root: Path, history: list[dict[str, Any]], as_of: str) -> dict[str, Any]:
    population = load_population(root)
    cards = {row["card_id"]: row for row in population}
    requests = json.loads((root / "data/research/op_x_034/price_request_priority.json").read_text())
    reports = json.loads(
        (root / "data/research/op_x_031/current_purchase_reports.json").read_text()
    )
    report_by_target = {row["candidate"]["card_id"]: row for row in reports}
    sets = []
    unique = set()
    for request in requests:
        current = report_by_target[request["target"]]["current_player"]["card_id"]
        row = {**request, "current_player_resale": current}
        sets.append(row)
        unique.update(
            value
            for key, value in row.items()
            if key
            in {
                "target",
                "current_player_resale",
                "best_lower_ovr_substitute",
                "best_near_equivalent",
            }
            and value
        )
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in history:
        grouped[row["card_id"]].append(row)
    states = []
    movements = []
    for card_id in sorted(unique):
        stats = history_statistics(grouped.get(card_id, []), as_of)
        states.append(
            {
                "card_id": card_id,
                "player_name": cards[card_id]["player_name"],
                "state": "NO DATA" if not stats.get("observation_count") else stats["quality"],
                "statistics": stats,
                "next_state_blocker": evidence_blocker(stats),
            }
        )
        movements.append({"card_id": card_id, **movement(stats)})
    priority = sorted(
        states,
        key=lambda row: (
            0
            if "RESALE" in row["next_state_blocker"]
            else row["statistics"].get("observation_count", 0),
            row["card_id"],
        ),
    )
    score_rows = json.loads(
        (root / "data/research/op_x_034/football_value_index.json").read_text()
    )["cards"]
    score_by_id = {row["card_id"]: row for row in score_rows}
    latest = {
        card_id: sorted(rows, key=lambda row: row["user_observed_at"])[-1]["observed_price"]
        for card_id, rows in grouped.items()
    }
    premiums = []
    arbitrage = []
    for request in sets:
        target = request["target"]
        for role in ("best_lower_ovr_substitute", "best_near_equivalent"):
            alternative = request.get(role)
            if not alternative:
                continue
            if target in latest and alternative in latest:
                football_delta = score_by_id[target]["score"] - score_by_id[alternative]["score"]
                price_delta = latest[target] - latest[alternative]
                premiums.append(
                    {
                        "target": target,
                        "alternative": alternative,
                        "target_price_premium": price_delta,
                        "target_football_score_premium": football_delta,
                        "target_rank_premium": score_by_id[alternative]["position_rank"]
                        - score_by_id[target]["position_rank"],
                        "target_percentile_premium": score_by_id[target]["position_percentile"]
                        - score_by_id[alternative]["position_percentile"],
                        "coins_per_additional_pancake_point": None
                        if football_delta <= 0
                        else round(price_delta / football_delta, 6),
                        "market_states": [
                            next(row["state"] for row in states if row["card_id"] == target),
                            next(row["state"] for row in states if row["card_id"] == alternative),
                        ],
                    }
                )
                if (
                    latest[alternative] <= latest[target]
                    and score_by_id[alternative]["score"] >= score_by_id[target]["score"] - 1
                ):
                    arbitrage.append(
                        {
                            "target": target,
                            "candidate": alternative,
                            "classification": "MARKET VALUE CANDIDATE",
                            "football_evidence": score_by_id[alternative],
                            "market_evidence": {
                                "target_price": latest[target],
                                "candidate_price": latest[alternative],
                            },
                            "identity_confidence": "EXACT",
                            "market_quality": next(
                                row["state"] for row in states if row["card_id"] == alternative
                            ),
                            "risk_flags": ["BUY GATES STILL APPLY"],
                        }
                    )
    frontiers = {}
    for position in sorted({row["position_family"] for row in score_rows}):
        priced = [
            row
            for row in score_rows
            if row["position_family"] == position and row["card_id"] in latest
        ]
        frontier = [
            row
            for row in priced
            if not any(
                other["score"] >= row["score"]
                and latest[other["card_id"]] <= latest[row["card_id"]]
                and other["card_id"] != row["card_id"]
                for other in priced
            )
        ]
        frontiers[position] = {
            "efficient_frontier": [
                {"card_id": row["card_id"], "score": row["score"], "price": latest[row["card_id"]]}
                for row in frontier
            ],
            "insufficient_evidence": [
                row["card_id"]
                for row in score_rows
                if row["position_family"] == position and row["card_id"] not in latest
            ],
        }
    board = [
        {
            "card_id": row["card_id"],
            "player": row["player_name"],
            "latest_price": latest.get(row["card_id"]),
            "market_state": row["state"],
            "price_trend": next(
                item["direction"] for item in movements if item["card_id"] == row["card_id"]
            ),
            "football_tier": score_by_id.get(row["card_id"], {}).get("discovery_tier"),
            "score": score_by_id.get(row["card_id"], {}).get("score"),
            "rank": score_by_id.get(row["card_id"], {}).get("position_rank"),
            "gm_action": "PRICE CHECK REQUIRED"
            if row["state"] in {"NO DATA", "INSUFFICIENT", "EARLY"}
            else "WAIT",
            "next_evidence": row["next_state_blocker"],
        }
        for row in states
    ]
    return {
        "comparison_sets": sets,
        "unique_targets": sorted(unique),
        "states": states,
        "movements": movements,
        "adaptive_priority": priority,
        "premiums": premiums,
        "arbitrage": arbitrage,
        "frontiers": frontiers,
        "market_board": board,
    }
