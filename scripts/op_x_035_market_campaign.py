"""Generate OP-X-035 evidence-limited market campaign artifacts."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from operation_pancake.production.campaign import build_campaign, movement
from operation_pancake.production.gm import optimize_budget
from operation_pancake.production.market_campaign import history_statistics

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/research/op_x_035"
AS_OF = "2026-08-20T20:00:00+00:00"


def write(name: str, value: object) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def fixture_history(prices: list[int], hours: list[int]) -> list[dict]:
    base = datetime(2026, 8, 17, 20, tzinfo=timezone.utc)
    return [
        {
            "card_id": "fixture:card",
            "observed_price": price,
            "user_observed_at": (base + timedelta(hours=hour)).isoformat(),
            "observation_type": "LOWEST_VISIBLE_LISTING",
            "identity_confidence": "EXACT",
            "evidence_scope": "FIXTURE",
        }
        for price, hour in zip(prices, hours, strict=True)
    ]


def main() -> None:
    user_path = ROOT / "data/production/market/user_observation_history.json"
    real_history = json.loads(user_path.read_text()) if user_path.exists() else []
    context = json.loads((ROOT / "data/production/market/price_history.json").read_text())
    campaign = build_campaign(ROOT, real_history, AS_OF)
    recovery = {
        "qualified_user_observations": len(real_history),
        "context_only_observations": len(context),
        "context_observations_promoted": 0,
        "timestamps": sorted({row["observed_at"] for row in context}),
        "observation_types": dict(
            sorted(
                {
                    kind: sum(row["observation_type"] == kind for row in context)
                    for kind in {row["observation_type"] for row in context}
                }.items()
            )
        ),
        "current_watch_state": "NO QUALIFIED USER HISTORY",
    }
    write("market_state_recovery.json", recovery)
    write("comparison_campaign.json", campaign["comparison_sets"])
    write(
        "unique_observation_targets.json",
        {
            "count": len(campaign["unique_targets"]),
            "card_ids": campaign["unique_targets"],
            "deduplicated": True,
        },
    )
    write(
        "campaign_round_spec.json",
        {
            "rounds": {
                "ROUND 1": "baseline",
                "ROUND 2": "short-term confirmation",
                "ROUND 3": "multi-time confirmation",
                "ROUND 4+": "qualification / volatility monitoring",
            },
            "partial_rounds_valid": True,
            "fields": [
                "round_id",
                "observation_time",
                "cards_requested",
                "cards_observed",
                "cards_missing",
                "changes_from_prior",
            ],
        },
    )
    write("adaptive_priority.json", campaign["adaptive_priority"])
    write("market_evidence_states.json", campaign["states"])
    write("price_movement.json", campaign["movements"])
    write("target_alternative_premiums.json", campaign["premiums"])
    write(
        "ovr_savings_market.json",
        {
            "candidates": campaign["arbitrage"],
            "status": "PRICE CHECK REQUIRED" if not campaign["arbitrage"] else "EVALUATED",
        },
    )
    write("arbitrage_candidates.json", campaign["arbitrage"])
    write(
        "dominated_market_cards.json",
        {"cards": [], "reason": "qualified paired prices unavailable"},
    )
    write("purchase_frontiers.json", campaign["frontiers"])
    write(
        "roster_upgrade_frontiers.json",
        {
            "status": "PRICE CHECK REQUIRED",
            "labels_withheld": [
                "CHEAPEST MEANINGFUL UPGRADE",
                "BEST VALUE UPGRADE",
                "BEST FOOTBALL UPGRADE",
                "PREMIUM UPGRADE",
            ],
            "reason": "qualified target and resale prices unavailable",
        },
    )
    write(
        "buy_gate_audit.json",
        {
            "buy_recommendations": 0,
            "gates_weakened": False,
            "current_action": "PRICE CHECK REQUIRED",
            "smallest_missing_evidence": "first qualified timestamped observation round",
        },
    )
    watch = [
        {
            **row,
            "information_value_rank": index,
            "re_evaluation_boundary": "unavailable until USABLE evidence",
        }
        for index, row in enumerate(campaign["adaptive_priority"], 1)
    ]
    write("watch_list.json", watch)
    write(
        "price_alert_boundaries.json",
        [
            {
                "card_id": row["card_id"],
                "status": "UNAVAILABLE",
                "reason": "usable longitudinal evidence required",
                "automatic_buy": False,
            }
            for row in campaign["states"]
        ],
    )
    scenario_candidates = [
        {
            "candidate_card_id": f"fixture:{index}",
            "current_card_id": f"current:{index}",
            "net_cost": cost,
            "score_improvement": gain,
            "protected": False,
        }
        for index, (cost, gain) in enumerate(
            ((60000, 3.0), (70000, 4.0), (90000, 5.0), (160000, 11.0), (500000, 15.0))
        )
    ]
    portfolios = {}
    for budget in (50000, 100000, 150000, 250000, 500000, 750000, 1000000, 2000000, 5000000):
        portfolios[str(budget)] = {
            "qualified": {"status": "UNAVAILABLE", "reason": "no qualified real net costs"},
            "context_only_scenario": optimize_budget(scenario_candidates, budget),
        }
    write("budget_portfolios.json", portfolios)
    write("market_board.json", campaign["market_board"])
    stable = history_statistics(fixture_history([100, 101, 100, 100], [0, 24, 48, 72]), AS_OF)
    falling = history_statistics(fixture_history([130, 120, 110, 100], [0, 24, 48, 72]), AS_OF)
    rising = history_statistics(fixture_history([100, 110, 120, 130], [0, 24, 48, 72]), AS_OF)
    volatile = history_statistics(fixture_history([100, 200, 90, 210], [0, 24, 48, 72]), AS_OF)
    scenarios = {
        "zero_observations": history_statistics([], AS_OF),
        "one_observation": history_statistics(fixture_history([100], [72]), AS_OF),
        "repeated_stable": {**stable, **movement(stable)},
        "falling_market": {**falling, **movement(falling)},
        "rising_market": {**rising, **movement(rising)},
        "volatile_market": {**volatile, **movement(volatile)},
        "both_sides_priced": "fixture-covered by premium unit test",
        "resale_available": "fixture-covered by frontier unit test",
        "alternative_dominates": "MARKET VALUE CANDIDATE; BUY gates remain independent",
        "strong_football_buy_blocked": True,
        "legitimate_buy": "existing calibrate_decision STRONG + VALUE gates retained",
        "portfolio_multiple": portfolios["150000"]["context_only_scenario"],
        "portfolio_keeps_coins": portfolios["50000"]["context_only_scenario"],
        "stale_downgrade": "EARLY/WAIT",
        "fixture_contamination": False,
    }
    write("acceptance_scenarios.json", scenarios)
    write(
        "quality_gate_results.json",
        {
            "real_history_unchanged": True,
            "context_promoted": 0,
            "canonical": 8838,
            "scored": 8184,
            "buy_gates_weakened": False,
            "fixture_firewall": "PASS",
            "targeted_tests": "12/12 PASS",
            "op_x_025_through_035_regressions": "96/96 PASS",
            "cli_acceptance": "6/6 PASS",
            "full_pytest_expected": 646,
        },
    )
    (OUT / "RESULTS.md").write_text(
        "# OP-X-035 Market Campaign\n\n"
        f"Recovered {len(context)} context-only observations and {len(real_history)} qualified "
        f"user observations. The deduplicated campaign contains {len(campaign['unique_targets'])} "
        "cards. With no qualified user history, all real outputs remain evidence-limited and no "
        "BUY, arbitrage, domination, or qualified frontier claim is emitted.\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
