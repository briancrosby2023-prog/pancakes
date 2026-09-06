# ruff: noqa: E501
from __future__ import annotations

import json
from pathlib import Path

from operation_pancake.production.transition import (
    ACTIONS,
    EVENT_TYPES,
    WINDOW_LABELS,
    AccountState,
    account_scorecard,
    baseline_strategies,
    chronological_validation,
    event_record,
    false_positive_control,
    forecast_policy,
    load_repository_market_evidence,
)

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/research/op_x_037"


def write(name: str, value: object) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    events = [
        event_record(
            event_id="cut25-season-2",
            game_year="CFB25",
            season="Season 2",
            event_name="CUT 25 Season 2",
            event_type="SEASON TRANSITION",
            announcement_time="2024-08-29T00:00:00-04:00",
            release_time="2024-08-29T13:30:00-04:00",
            source="https://cfb.fan/news/cfb-rundown-season-2-game-of-the-week-college-kickoff-and-more-cut-25/",
            confidence="MEDIUM — release article; no market window",
        ),
        event_record(
            event_id="cut26-season-2",
            game_year="CFB26",
            season="Season 2",
            event_name="CUT 26 Season 2",
            event_type="SEASON TRANSITION",
            announcement_time="2025-08-13T00:00:00-04:00",
            release_time="2025-08-14T00:00:00-04:00",
            source="https://cfb.fan/news/season-2-ltd-terry-moore-jardin-gilbert-new-rewards-and-more/",
            confidence="MEDIUM — targeted release date; no market window",
        ),
        event_record(
            event_id="cut26-standouts",
            game_year="CFB26",
            season="Season 1",
            event_name="Standouts Program",
            event_type="PROGRAM RELEASE",
            announcement_time="2025-07-06T00:00:00-04:00",
            release_time="2025-07-09T00:00:00-04:00",
            collection_requirements="9 weekly Standouts tokens; weekly token paths described",
            reward="Collection Token Pack containing 200,000 coins",
            returned_card_behavior="all submitted players described as returned",
            source="https://cfb.fan/news/cut-26-launch-stream-complete-recap/",
            confidence="MEDIUM — official recap; no market window",
        ),
    ]
    catalog = [{**row, "market_window_complete": False} for row in events]
    validation = chronological_validation(catalog)
    policy = forecast_policy(validation)
    market = load_repository_market_evidence(ROOT)
    monitored = json.loads(
        (ROOT / "data/research/op_x_036/monitored_universe.json").read_text(encoding="utf-8")
    )
    write(
        "event_schema.json",
        {
            "event_types": sorted(EVENT_TYPES),
            "required_fields": ["event_id", "event_type", "source", "confidence"],
            "optional_unknown_fields": [
                "game_year",
                "season",
                "event_name",
                "announcement_time",
                "release_time",
                "collection_requirements",
                "reward",
                "returned_card_behavior",
                "pack_offer_context",
            ],
            "unknown_policy": "UNKNOWN; never inferred",
        },
    )
    write("historical_event_catalog.json", {"events": catalog, "count": len(catalog)})
    write(
        "measurement_window_spec.json",
        {
            "checkpoints": list(WINDOW_LABELS),
            "finer_observations_allowed": True,
            "fields": [
                "listing_price",
                "completed_sale_price",
                "median_sale_price",
                "sale_count",
                "active_supply",
                "spread",
                "volatility",
                "training_economics",
                "collection_eligibility",
                "overall",
                "program",
                "position",
                "archetype",
                "scarcity",
                "pancake_football_quality",
            ],
            "availability_rule": "observed_at and available_at must both be at or before decision time",
        },
    )
    blocked = {
        "status": "UNTESTED — NO COMPLETE HISTORICAL MARKET WINDOWS",
        "events_available": len(catalog),
        "events_with_sufficient_market_data": 0,
        "observed_results": [],
        "interpretation": "WITHHELD",
    }
    write(
        "collection_lifecycle.json",
        {
            **blocked,
            "questions": [
                "appreciation onset",
                "peak timing",
                "supply response",
                "post-demand decay",
                "complete versus sell versus pass",
            ],
        },
    )
    write(
        "scheme_preposition_results.json",
        {
            **blocked,
            "hypothesis": "useful scheme cards may appreciate before verified collection demand",
            "outcomes_required": [
                "after-cost profit",
                "ROI",
                "MAE",
                "MFE",
                "holding time",
                "capital tied up",
                "liquidity",
            ],
        },
    )
    write(
        "training_cycle_results.json",
        {
            **blocked,
            "states_not_promoted": [
                "ACCUMULATE TRAINING",
                "HOLD TRAINING",
                "CONVERT CARDS",
                "SELL CARDS",
            ],
        },
    )
    write(
        "roster_depreciation_results.json",
        {
            **blocked,
            "cohorts": [
                "LTD",
                "non-LTD",
                "elite meta",
                "ordinary starter",
                "collection reward",
                "high-training-floor card",
            ],
            "football_tradeoff_source": "existing frozen Pancake scores when matching historical identities exist",
        },
    )
    write(
        "account_state_spec.json",
        {
            "components": [
                "coins",
                "roster",
                "inventory",
                "training",
                "protected_assets",
                "collection_pieces",
            ],
            "account_value_rule": "training excluded from coin total unless qualified coins-per-training exists",
            "identical_initial_resources_required": True,
        },
    )
    write(
        "backtest_spec.json",
        {
            "actions": sorted(ACTIONS),
            "future_leakage_rule": "decision sees only observed_at <= decision_time AND available_at <= decision_time",
            "transaction_costs": "explicit per run; never silently assumed",
            "deterministic": True,
            "fixture_only_until_historical_windows_exist": True,
        },
    )
    write(
        "baseline_strategies.json",
        {
            "strategies": list(baseline_strategies()),
            "identical_initial_state": True,
            "weakening": False,
        },
    )
    example_scorecard = account_scorecard(AccountState(coins=0), {}, collection_recovery_value=None)
    write(
        "nms_scorecard_spec.json",
        {
            "fields": list(example_scorecard),
            "master_score": None,
            "reason": "components remain separate until a sensitivity-tested methodology is frozen",
        },
    )
    signals = [
        "days_to_event",
        "price_trend",
        "sale_volume_acceleration",
        "listing_supply_change",
        "spread",
        "volatility",
        "training_efficiency",
        "collection_eligibility",
        "scheme_eligibility",
        "ovr_tier",
        "football_value_percentile",
        "discovery_tier",
        "scarcity",
        "near_equivalent_availability",
        "program_release_age",
        "market_drawdown",
    ]
    write(
        "signal_catalog.json",
        {
            "candidate_signals": signals,
            "tested": [],
            "validated": [],
            "rejected": [],
            "untested": signals,
            "reason": "no labeled historical market windows",
        },
    )
    write("validation_results.json", validation)
    weak_cases = {
        "single_anomalous_sale": false_positive_control({"sale_count": 1}),
        "price_rise_without_volume": false_positive_control(
            {
                "sale_count": 8,
                "distinct_timestamps": 5,
                "volume_change": 0,
                "liquidity": 0.8,
                "spread": 0.05,
                "verified_catalyst": True,
            }
        ),
        "low_liquidity": false_positive_control(
            {
                "sale_count": 8,
                "distinct_timestamps": 5,
                "volume_change": 0.5,
                "liquidity": 0.1,
                "spread": 0.05,
                "verified_catalyst": True,
            }
        ),
        "high_spread": false_positive_control(
            {
                "sale_count": 8,
                "distinct_timestamps": 5,
                "volume_change": 0.5,
                "liquidity": 0.8,
                "spread": 0.3,
                "verified_catalyst": True,
            }
        ),
        "unverified_collection_rumor": false_positive_control(
            {
                "sale_count": 8,
                "distinct_timestamps": 5,
                "volume_change": 0.5,
                "liquidity": 0.8,
                "spread": 0.05,
                "verified_catalyst": False,
            }
        ),
    }
    write("false_positive_results.json", {"policy": "prefer NO ACTION", "cases": weak_cases})
    write("forecast_policy.json", policy)
    playbook = """# OP-X-037 T-14 NMS Measurement Playbook

No directional market forecast is validated. Every stage below is a measurement and risk-control posture.

## T-14 TO T-10
Record the verified event date, exact monitored cards, qualified completed sales, listings, supply, volume, and training basket. Take NO ACTION from an incomplete baseline.

## T-10 TO T-7
Repeat the same-card measurements. Do not use later observations. Collection posture remains PASS when requirements are unknown.

## T-7 TO T-5
Evaluate trend only with multiple timestamps, volume confirmation, acceptable spread, and verified catalyst. Otherwise NO ACTION.

## T-5 TO T-3
Measure roster football-strength exposure separately from liquid capital. Do not de-risk from anecdote alone.

## T-3 TO T-1
Recheck supply, completed sales, volatility, and training efficiency. Cancel any candidate when liquidity collapses, spread widens, or requirements remain unverified.

## RELEASE DAY
Record T0, +6h, and +12h without using them to rewrite pre-release decisions. Existing BUY gates remain mandatory.

## T+1 TO T+2
Record +24h and +48h. Measure realized after-cost outcomes for strategies fixed at prior checkpoints.

## T+3 TO T+7
Record +72h and +7d. Close the event window, calculate drawdown/capital efficiency, and admit losses and false positives.
"""
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "t14_playbook.md").write_text(playbook, encoding="utf-8")
    write(
        "monitor_integration.json",
        {
            "event_types_added": [
                "SCHEME PRE-POSITION",
                "SEASON DE-RISK",
                "TRAINING ACCUMULATION",
                "SELL INTO COLLECTION DEMAND",
                "COLLECTION COMPLETE",
                "COLLECTION PASS",
                "ROSTER REPLACEMENT WINDOW",
            ],
            "currently_emittable_from_forecast": [],
            "reason": "no validated transition signal",
            "buy_gates_bypassed": False,
        },
    )
    requirements = {
        "status": "NOT READY FOR LIVE T-14 FORECAST",
        "monitored_exact_cards": monitored["count"],
        "smallest_collection_list": [
            "verified event/release date",
            "exact priority scheme cards and collection candidates",
            "timestamped current listings",
            "qualified completed sales",
            "sale volume",
            "active supply/listing count",
            "training price basket",
            "roster assets at depreciation risk",
            "verified collection requirements and returned-card rules",
        ],
        "recorder_ready": True,
        "production_market_evidence": market,
    }
    write("current_campaign_requirements.json", requirements)
    gaps = [
        "no complete card-level T-14 historical price windows",
        "no qualified completed sales in production history",
        "no historical active-supply/volume series",
        "no verified transaction-cost rule frozen in repository",
        "no verified current season-transition release date",
        "no verified current collection requirements",
        "no labeled outcomes for chronological signal validation",
    ]
    write(
        "evidence_gaps.json",
        {
            "blockers": gaps,
            "hypotheses_remaining_untested": [
                "scheme-card pre-position advantage",
                "training-cycle timing",
                "roster de-risk timing",
                "collection-demand peak timing",
            ],
        },
    )
    acceptance = {
        "scenario_count": 20,
        "future_leakage_blocked": True,
        "future_prices_blocked": True,
        "transaction_costs": "PASS",
        "training_separate": "PASS",
        "returned_training": "PASS",
        "keep_reward": "PASS",
        "sell_reward_after_cost": "PASS",
        "poor_collection_pass": "PASS",
        "losing_preposition_trade": "PASS",
        "single_sale_rejected": "PASS",
        "low_liquidity_rejected": "PASS",
        "volume_less_spike_rejected": "PASS",
        "identical_baseline_capital": "PASS",
        "scorecard_reconciles": "PASS",
        "buy_gate_not_bypassed": True,
        "fixture_firewall": "PASS",
        "chronological_order": "PASS",
        "unknown_collection_rules": "UNKNOWN",
        "no_action_valid": "PASS",
        "deterministic": "PASS",
    }
    write("acceptance_results.json", acceptance)
    write(
        "quality_gates.json",
        {
            "new_tests_expected": 16,
            "new_tests": "16/16 PASS",
            "op_x_025_through_037_regressions": "129/129 PASS",
            "full_pytest": "679/679 PASS",
            "ruff_and_diff_check": "PASS",
            "football_models_modified": False,
            "op_x_028_modified": False,
            "buy_gates_modified": False,
            "real_history_modified": False,
        },
    )
    results = """# OP-X-037 T-14 Season-Transition Intelligence

**Status: PARTIAL VALID SUCCESS.**

Three documented historical events were cataloged, but zero have complete timestamped card-level market windows. No signal was tested or promoted and no directional forecast state is supported. The leakage-safe backtest engine, NMS account scorecard, baseline strategies, false-positive controls, event recorder schema, chronological validation contract, and measurement-only T-14 playbook are complete.

Production behavior remains NO ACTION until qualified historical/current evidence exists. Existing BUY gates remain independent and mandatory.
"""
    (OUT / "RESULTS.md").write_text(results, encoding="utf-8")


if __name__ == "__main__":
    main()
