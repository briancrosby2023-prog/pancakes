"""Generate OP-X-029 campaign controls and fixture-only acceptance evidence."""

from __future__ import annotations

import json
from pathlib import Path

from operation_pancake.production.market_campaign import (
    OBSERVATION_TYPES,
    calibrate_decision,
    enrich_observation,
    history_statistics,
    prioritize_collection,
    snapshot_report,
    watch_boundaries,
)

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data/research/op_x_029"


def write(name: str, payload: object) -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    text = (
        payload
        if isinstance(payload, str)
        else json.dumps(payload, indent=2, sort_keys=True) + "\n"
    )
    (OUTPUT / name).write_text(text, encoding="utf-8")


def fixtures(card: dict) -> dict:
    def rows(
        prices: list[int], hours: list[int], kind: str = "DISPLAYED_MARKET_PRICE"
    ) -> list[dict]:
        return [
            enrich_observation(
                card,
                price,
                kind,
                observed_at=f"2026-08-{20 + hour // 24:02d}T{hour % 24:02d}:00:00-07:00",
                ingested_at=f"2026-08-{20 + hour // 24:02d}T{hour % 24:02d}:01:00-07:00",
                source="OP_X_029_FIXTURE",
                fixture=True,
            )
            for price, hour in zip(prices, hours, strict=True)
        ]

    scenarios = {
        "one_observation": rows([100_000], [0]),
        "same_day": rows([100_000, 99_000, 101_000], [0, 2, 4]),
        "multi_day_stable": rows([100_000, 101_000, 99_000, 100_000], [0, 12, 24, 36]),
        "falling": rows([120_000, 110_000, 100_000, 90_000], [0, 24, 48, 72]),
        "rising": rows([90_000, 100_000, 110_000, 120_000], [0, 24, 48, 72]),
        "high_volatility": rows([100_000, 200_000, 50_000, 220_000], [0, 24, 48, 72]),
        "listing_sale_disagreement": (
            rows([120_000, 125_000], [0, 24], "VISIBLE_LISTING")
            + rows([95_000, 97_000], [12, 36], "COMPLETED_SALE")
        ),
        "stale": rows([100_000, 101_000, 99_000, 100_000], [0, 24, 48, 72]),
    }
    output = {}
    for name, observations in scenarios.items():
        as_of = "2026-08-23T01:00:00-07:00"
        if name == "stale":
            as_of = "2026-08-30T00:00:00-07:00"
        stats = history_statistics(observations, as_of)
        output[name] = {
            "history_persisted": False,
            "statistics": stats,
            "watch": watch_boundaries(stats),
        }
    strong_rows = rows(
        [100_000, 101_000, 99_000, 100_000, 98_000, 99_000, 97_000, 98_000],
        [0, 12, 24, 36, 48, 60, 72, 84],
        "COMPLETED_SALE",
    )
    strong = history_statistics(strong_rows, "2026-08-23T13:00:00-07:00")
    output["decision_evolution"] = [
        calibrate_decision(
            output["one_observation"]["statistics"], "STRONG VALUE", gross_cost=100_000
        ),
        calibrate_decision(
            output["multi_day_stable"]["statistics"], "STRONG VALUE", gross_cost=100_000
        ),
        calibrate_decision(
            strong, "STRONG VALUE", gross_cost=98_000, resale_value=20_000, budget=100_000
        ),
    ]
    output["strong_with_resale"] = {
        "statistics": strong,
        "gross_cost": 98_000,
        "resale": 20_000,
        "net_cost": 78_000,
    }
    return output


def main() -> None:
    valuations = json.loads(
        (ROOT / "data/research/op_x_028/current_target_valuations.json").read_text(encoding="utf-8")
    )["targets"]
    by_candidate = {row["candidate"]: row for row in valuations}
    priority_names = [row["candidate"] for row in prioritize_collection(valuations)]
    priority = []
    for rank, name in enumerate(priority_names, 1):
        row = by_candidate[name]
        priority.append(
            {
                "priority": rank,
                "candidate": name,
                "current": row["current"],
                "candidate_card_id": row["candidate_card_id"],
                "current_card_id": row["current_card_id"],
                "intrinsic_valuation": row["relative_valuation"],
                "value_index": row["value_index"],
                "reason": "highest decision value among favorable classes"
                if rank <= 2
                else "lower urgency because current contextual class is less favorable",
            }
        )
    write(
        "campaign_spec.json",
        {
            "history": "data/production/market/user_observation_history.json",
            "append_only": True,
            "default_source": "USER_OBSERVED_CFB_FAN",
            "rapid_entry": (
                "operation-pancake-gm market-snapshot snapshot.json --type DISPLAYED_MARKET_PRICE"
            ),
            "candidate_and_resale_cards": priority,
            "frozen_intrinsic_commit": "1efe088731c9844b43d99373579794e22ab2dbfa",
            "frozen_intrinsic_sha256": (
                "55ab8e89d5f42ba38ba558968452eb6f00eb22f63876d678d2564eb8fab3c889"
            ),
        },
    )
    write(
        "observation_schema.json",
        {
            "required_user_input": [
                "exact card or unambiguous campaign card",
                "observed_price",
                "observation_type",
            ],
            "observation_types": sorted(OBSERVATION_TYPES),
            "automatic_fields": [
                "canonical identity fields",
                "user_observed_at",
                "ingested_at",
                "source",
                "source_confidence",
                "identity_confidence",
            ],
            "timestamp_semantics": {
                "user_observed_at": "time user saw display",
                "source_published_at": "null unless source explicitly supplies it",
            },
        },
    )
    write(
        "sample_sufficiency.json",
        {
            "INSUFFICIENT": (
                "fewer than 2 observations/times, unresolved identity, or future timestamp"
            ),
            "EARLY": (
                "fewer than 4 observations, fewer than 3 times, under 24h span, or over 48h age"
            ),
            "USABLE": (
                "at least 4 observations, 3 times, 24h span, meaningful semantics, latest <=24h"
            ),
            "STRONG": "at least 8 observations, 5 times, 72h span, latest <=12h, dispersion <=15%",
            "rationale": (
                "thresholds require independent temporal breadth and resist rapid duplicate checks"
            ),
        },
    )
    write(
        "calibration_framework.json",
        {
            "questions": [
                "position within recent range",
                "freshness",
                "sample sufficiency",
                "stability",
                "intrinsic favorability",
                "roster improvement",
                "affordability",
            ],
            "buy_gate": "STRONG market evidence + STRONG VALUE/VALUE + stable + affordable",
            "wait_gate": (
                "usable but not buy-qualified, unfavorable intrinsic class, or unaffordable"
            ),
            "no_forced_buy": True,
        },
    )
    write(
        "decision_firewall.json",
        {
            "intrinsic": "unchanged OP-X-028 artifact/index",
            "market": "OP-X-029 append-only observations and statistics",
            "roster": "validated production score/rank improvement",
            "decision": "explicit combination only; no layer mutates another",
        },
    )
    fixture = fixtures(
        {
            "card_id": "fixture:brendan",
            "player_name": "Brendan Black",
            "position": "RG",
            "native_overall": 85,
            "program": "Prime Prospects",
            "archetype": "Raw Strength",
        }
    )
    write("fixture_acceptance.json", fixture)
    write("collection_priority.json", priority)
    first = {
        "observation_type": "DISPLAYED_MARKET_PRICE",
        "candidate_prices": {row["candidate_card_id"]: None for row in priority[:2]},
        "optional_resale_listings": {row["current_card_id"]: None for row in priority[:2]},
        "plain_language": [
            "Brendan Black — displayed market price",
            "E'Marion Harris — displayed market price",
            "Anthony Donkoh — lowest visible listing (optional resale)",
            "Samson Okunlola — lowest visible listing (optional resale)",
        ],
    }
    write("first_snapshot_request.json", first)
    historical = json.loads(
        (ROOT / "data/research/op_x_027/current_market_summary.json").read_text(encoding="utf-8")
    )
    write(
        "op_x_027_contextual_history.json",
        {
            "admissibility": "CONTEXT_ONLY_NOT_QUALIFIED_OP_X_029_HISTORY",
            "timestamp_quality": "capture time exists; source-published time absent",
            "source": historical,
        },
    )
    report_rows = [
        {
            "candidate": row["candidate"],
            "current": row["current"],
            "intrinsic_valuation": row["intrinsic_valuation"],
            "sample_count": 0,
            "quality": "INSUFFICIENT",
            "decision": "PRICE CHECK REQUIRED",
            "next_required_evidence": "timestamped user observation",
        }
        for row in priority
    ]
    write("MARKET_SNAPSHOT.md", snapshot_report(report_rows))


if __name__ == "__main__":
    main()
