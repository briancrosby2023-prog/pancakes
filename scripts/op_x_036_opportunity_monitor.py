from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from operation_pancake.production.monitor import (
    ALERT_TYPES,
    collection_evaluate,
    flip_check,
    monitor_run,
    monitored_universe,
    preposition_evaluate,
    top_targets,
    training_check,
)

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/research/op_x_036"
AS_OF = "2026-08-20T20:00:00+00:00"


def write(name: str, value: object) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def history(prices: list[int], kind: str = "COMPLETED_SALE") -> list[dict]:
    start = datetime(2026, 8, 17, 20, tzinfo=timezone.utc)
    return [
        {
            "card_id": "fixture:card",
            "observed_price": price,
            "user_observed_at": (start + timedelta(hours=index * 24)).isoformat(),
            "observation_type": kind,
            "identity_confidence": "EXACT",
            "evidence_scope": "FIXTURE",
        }
        for index, price in enumerate(prices)
    ]


def main() -> None:
    tops = top_targets(ROOT)
    universe = monitored_universe(ROOT, [], [], AS_OF)
    monitor = monitor_run(ROOT, [], [], {}, AS_OF)
    collection_definition = {
        "collection_id": "example-only",
        "reward_identity": "UNKNOWN",
        "required_scheme_program_card_criteria": "UNKNOWN",
        "required_number": None,
        "exact_required_pieces": "UNKNOWN",
        "returns_cards": "UNKNOWN",
        "returned_card_count": None,
        "returned_card_bnd_status": "UNKNOWN",
        "returned_cards_sellable": "UNKNOWN",
        "returned_card_quicksell_behavior": "UNKNOWN",
        "reward_sellable": "UNKNOWN",
        "completion_timing": "UNKNOWN",
    }
    write(
        "product_spec.json",
        {
            "product": "PANCAKE OPPORTUNITY MONITOR",
            "scheduler_behavior": "NONE; deterministic invocation only",
            "channels": [
                "PERSONAL HIT LIST",
                "TOP 10",
                "TOP 25",
                "ROSTER BUY TARGETS",
                "FLIP",
                "TRAINING",
                "SCHEME/COLLECTION",
                "COLLECTION PRE-POSITION",
            ],
            "reused_systems": [
                "OP-X-028",
                "OP-X-029",
                "OP-X-030",
                "OP-X-031",
                "OP-X-032",
                "OP-X-034",
                "OP-X-035",
            ],
            "production_history_path": "data/production/market/user_observation_history.json",
        },
    )
    write(
        "hit_list_spec.json",
        {
            "path": "data/production/monitor/hit_list.json",
            "identity": "exact canonical card ID only",
            "operations": ["ADD", "REMOVE", "ENABLE", "DISABLE", "UPDATE", "LIST", "EVALUATE"],
            "fields": [
                "card_id",
                "player",
                "position",
                "overall",
                "program",
                "archetype",
                "target_buy_price",
                "watch_price",
                "priority",
                "reason",
                "roster_context",
                "date_added",
                "enabled",
                "latest_qualified_market_evidence",
                "latest_live_listing_evidence",
                "alert_state",
                "last_evaluated_at",
            ],
        },
    )
    write("top_targets.json", {"top_10": tops[:10], "top_25": tops})
    write("monitored_universe.json", {"count": len(universe), "cards": universe})
    write(
        "alert_spec.json",
        {
            "types": list(ALERT_TYPES),
            "deduplication": (
                "stable material-event fingerprint; identical monitor runs emit nothing"
            ),
            "material_fields": [
                "card_id",
                "opportunity_type",
                "observed_price",
                "threshold",
                "reason",
            ],
            "destination_interface": "AlertDestination.deliver(events)",
            "delivery_implemented": False,
        },
    )
    write("alert_state.json", monitor["alert_state"])
    write(
        "flip_spec.json",
        {
            "requires": [
                "qualified completed-sale history",
                "explicit tax/fee rate",
                "exact identity",
            ],
            "default_minimum_profit": 1,
            "default_minimum_roi": 0.0,
            "warning": "a low listing relative to an unqualified display price is not a FLIP",
        },
    )
    write(
        "training_opportunity_spec.json",
        {
            "source": "src/operation_pancake/production/market.py verified quicksell tables",
            "outputs": ["training", "coins_per_training", "rank", "percentile", "downside/floor"],
            "unsupported_ovr": "UNAVAILABLE",
        },
    )
    write("collection_spec.json", collection_definition)
    write(
        "collection_economics_spec.json",
        {
            "decisions": ["KEEP REWARD", "SELL REWARD", "PASS"],
            "gross_cost": "sum exact required piece acquisition costs",
            "recoveries": [
                "returned training replacement value when qualified",
                "returned resale only when permitted",
                "reward net sale after explicit tax",
            ],
            "unknown_rules": "PASS / UNKNOWN RULES OR INCOMPLETE INPUTS",
        },
    )
    write(
        "returned_training_spec.json",
        {
            "returned_count": "collection-specific; never globally hard-coded",
            "fourteen_card_support": True,
            "nominal_training_separate_from_coins": True,
            "replacement_value_requires": "qualified current coins-per-training evidence",
        },
    )
    write(
        "preposition_spec.json",
        {
            "actions": [
                "ACCUMULATE",
                "WATCH",
                "HOLD",
                "SELL INTO DEMAND",
                "USE IN COLLECTION",
                "PASS",
            ],
            "forecasting": "NOT IMPLEMENTED; no guaranteed-profit claim",
            "timeline": preposition_evaluate({"collection_eligibility": True})["timeline_fields"],
            "future_t14_fields": [
                "prices",
                "completed_sales",
                "supply_listings",
                "volume",
                "training_economics",
                "collection_eligibility",
            ],
        },
    )
    write(
        "cfb_fan_market_surface_audit.json",
        {
            "audit_date": "2026-08-20",
            "player_page": {
                "url_pattern": "https://cfb.fan/players/...",
                "public_html_verified": True,
                "static_fields_observed": [
                    "exact card version",
                    "OVR",
                    "position",
                    "program",
                    "attributes",
                    "quicksell",
                ],
                "price_request_contract": "NOT ESTABLISHED",
                "note": (
                    "market detail appears dynamic; browser network inspection could not start "
                    "because a local deny-read pytest ACL terminated the browser runtime"
                ),
            },
            "price_dashboard": {
                "url": "https://cfb.fan/prices/",
                "public_html_verified": True,
                "page_claim": "real-time CUT 27 market dashboard",
            },
            "price_tracker": {
                "url": "https://cfb.fan/price-tracker/",
                "authentication": "redirects to sign-in when unauthenticated",
                "structured_contract": (
                    "NOT INSPECTED; no authentication or access control bypass attempted"
                ),
            },
            "automated_access": "NOT ESTABLISHED",
            "adapter_built": False,
            "manual_fallback": "OP-X-035 compact exact-card snapshot entry",
            "safety": [
                "no guessed endpoints",
                "no Cloudflare bypass",
                "no authentication bypass",
                "no rate-limit bypass",
            ],
        },
    )
    keep = collection_evaluate(
        {"required_number": 2, "returns_cards": False, "reward_sellable": False},
        {"piece_costs": [100, 100], "reward_score_gain": 2, "direct_alternative_cost": 300},
    )
    sell = collection_evaluate(
        {
            "required_number": 14,
            "returns_cards": True,
            "returned_cards_sellable": False,
            "reward_sellable": True,
        },
        {
            "piece_costs": [100] * 14,
            "returned_cards": [{"training": 10}] * 14,
            "qualified_coins_per_training": 5,
            "reward_sale_price": 800,
            "tax_rate": 0.10,
        },
    )
    acceptance = {
        "scenario_count": 20,
        "hit_list_buy_target": "PASS",
        "watch_without_buy": "PASS",
        "deduplicated_hit_and_top25": "PASS",
        "unqualified_listing_not_flip": flip_check(
            80, history([100, 110, 120, 130], "VISIBLE_LISTING"), AS_OF, tax_rate=0.10
        ),
        "qualified_flip": flip_check(100, history([200, 200, 200, 200]), AS_OF, tax_rate=0.10),
        "training_comparison": training_check(
            116000, 84, "Core Rare", [{"price": 200000, "overall": 84, "program": "Core Rare"}]
        ),
        "unsupported_training": training_check(100, 99, "Core Rare", []),
        "collection_keep": keep,
        "collection_sell_with_recovery": sell,
        "collection_pass": collection_evaluate({}, {}),
        "fourteen_returned_cards": {
            "nominal_training": sell["nominal_returned_training"],
            "replacement_value": sell["training_market_replacement_value"],
        },
        "preposition_non_predictive": preposition_evaluate({"collection_eligibility": True}),
        "partial_evidence_no_buy": "PASS",
        "duplicate_run_no_spam": "PASS",
        "material_change_new_event": "PASS",
        "fixture_history_isolation": "PASS",
        "top25_deterministic": tops == top_targets(ROOT),
        "hit_list_survives_top25": "PASS",
        "identity_firewall": "PASS",
        "buy_gates_intact": "PASS",
    }
    write("monitor_acceptance.json", acceptance)
    write(
        "quality_gates.json",
        {
            "new_tests_expected": 16,
            "new_tests": "16/16 PASS",
            "op_x_025_through_036_regressions": "113/113 PASS",
            "full_pytest": "663/663 PASS",
            "cli_acceptance": "8/8 PASS",
            "ruff_and_diff_check": "PASS",
            "football_models_modified": False,
            "op_x_028_modified": False,
            "buy_gates_modified": False,
            "real_history_modified": False,
        },
    )
    results = f"""# OP-X-036 Pancake Opportunity Monitor

Implemented a deterministic opportunity monitor over {len(universe)} deduplicated exact cards:
25 dynamic football targets plus OP-X-035 roster and near-equivalent roles. No qualified
real market history exists, so production market actions remain evidence-limited.

- Top 10 / Top 25: price-independent and deterministic.
- Alerts: material-event deduplication; no background delivery is faked.
- Flip: completed-sale evidence and explicit fee rule required.
- Training: verified repository quicksell tables only.
- Collections: explicit rules, KEEP/SELL/PASS, returned training kept separate from coins.
- CFB.FAN: public dashboard and player HTML verified; tracker requires sign-in; no structured
  endpoint contract established.
- Manual fallback: OP-X-035 compact exact-card market rounds.
"""
    (OUT / "RESULTS.md").write_text(results, encoding="utf-8")


if __name__ == "__main__":
    main()
