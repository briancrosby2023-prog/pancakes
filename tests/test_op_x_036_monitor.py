from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from operation_pancake.production.market_campaign import calibrate_decision, history_statistics
from operation_pancake.production.monitor import (
    canonical_cards,
    collection_evaluate,
    evaluate_hit_list,
    flip_check,
    hit_list_mutation,
    monitor_run,
    monitored_universe,
    preposition_evaluate,
    reconcile_events,
    top_targets,
    training_check,
)

ROOT = Path(__file__).resolve().parents[1]
AS_OF = "2026-08-20T20:00:00+00:00"


@pytest.fixture(scope="module")
def cards() -> dict:
    return canonical_cards(ROOT)


def observations(
    card_id: str, prices: list[int], *, kind: str = "LOWEST_VISIBLE_LISTING"
) -> list[dict]:
    base = datetime(2026, 8, 17, 20, tzinfo=timezone.utc)
    return [
        {
            "card_id": card_id,
            "observed_price": price,
            "user_observed_at": (base + timedelta(hours=index * 24)).isoformat(),
            "observation_type": kind,
            "identity_confidence": "EXACT",
            "evidence_scope": "FIXTURE",
        }
        for index, price in enumerate(prices)
    ]


def test_hit_list_is_exact_persistent_shape_and_mutable(cards: dict) -> None:
    card_id = "card:f35e84cba0d56c4270c3"
    entries = hit_list_mutation(
        [], "ADD", card_id, cards, now=AS_OF, target_buy_price=100, watch_price=120
    )
    assert entries[0]["player"] == "Brendan Black"
    assert entries[0]["enabled"] is True
    entries = hit_list_mutation(entries, "DISABLE", card_id, cards, now=AS_OF)
    assert entries[0]["enabled"] is False
    entries = hit_list_mutation(entries, "UPDATE", card_id, cards, now=AS_OF, target_buy_price=90)
    assert entries[0]["target_buy_price"] == 90
    assert hit_list_mutation(entries, "REMOVE", card_id, cards, now=AS_OF) == []


def test_hit_list_rejects_ambiguous_or_duplicate_identity(cards: dict) -> None:
    with pytest.raises(ValueError, match="unresolved canonical"):
        hit_list_mutation([], "ADD", "Brendan Black", cards, now=AS_OF)
    card_id = "card:f35e84cba0d56c4270c3"
    entries = hit_list_mutation([], "ADD", card_id, cards, now=AS_OF)
    with pytest.raises(ValueError, match="already exists"):
        hit_list_mutation(entries, "ADD", card_id, cards, now=AS_OF)


def test_top_25_is_dynamic_price_independent_and_deterministic() -> None:
    first = top_targets(ROOT)
    assert first == top_targets(ROOT)
    assert len(first) == 25
    assert len([row for row in first if row["monitor_tier"] == "TOP 10"]) == 10
    assert all(row["selection_basis"] == "PRICE-INDEPENDENT FOOTBALL INTELLIGENCE" for row in first)


def test_universe_deduplicates_sources(cards: dict) -> None:
    top = top_targets(ROOT)[0]
    hit = hit_list_mutation([], "ADD", top["card_id"], cards, now=AS_OF, reason="personal")
    universe = monitored_universe(ROOT, hit, [], AS_OF)
    matches = [row for row in universe if row["card_id"] == top["card_id"]]
    assert len(matches) == 1
    assert {"PERSONAL HIT LIST", "TOP 10"}.issubset(matches[0]["sources"])


def test_hit_list_buy_target_and_watch_threshold_are_events(cards: dict) -> None:
    ids = ["card:f35e84cba0d56c4270c3", "card:223972d9a434a9d9fb4c"]
    entries = hit_list_mutation(
        [], "ADD", ids[0], cards, now=AS_OF, target_buy_price=100, watch_price=120
    )
    entries = hit_list_mutation(
        entries, "ADD", ids[1], cards, now=AS_OF, target_buy_price=80, watch_price=120
    )
    history = observations(ids[0], [99]) + observations(ids[1], [110])
    evaluated, alerts = evaluate_hit_list(entries, history, AS_OF)
    assert {row["opportunity_type"] for row in alerts} == {"BUY TARGET", "WATCH TARGET"}
    assert all("BUY GATES NOT SATISFIED" in row["risk_flags"] for row in alerts)
    assert {row["alert_state"] for row in evaluated} == {
        "BUY TARGET CROSSED",
        "WATCH TARGET CROSSED",
    }


def test_alert_dedup_and_material_price_change() -> None:
    base = {
        "card_id": "card:x",
        "opportunity_type": "WATCH TARGET",
        "observed_price": 100,
        "threshold": 110,
        "reason": "threshold",
    }
    events, state = reconcile_events([base], {}, AS_OF)
    assert len(events) == 1
    assert reconcile_events([base], state, AS_OF)[0] == []
    changed = {**base, "observed_price": 90}
    assert len(reconcile_events([changed], state, AS_OF)[0]) == 1


def test_flip_requires_qualified_completed_sales() -> None:
    listing = observations("card:x", [100, 110, 120, 130])
    assert flip_check(80, listing, AS_OF, tax_rate=0.10)["alert"] is False
    assert flip_check(80, listing, AS_OF, tax_rate=0.10)["status"] == "INSUFFICIENT EVIDENCE"


def test_qualified_flip_profit_roi_and_tax() -> None:
    sales = observations("card:x", [200, 200, 200, 200], kind="COMPLETED_SALE")
    result = flip_check(100, sales, AS_OF, tax_rate=0.10)
    assert result["status"] == "FLIP"
    assert result["net_proceeds"] == 180
    assert result["projected_profit"] == 80
    assert result["roi"] == 0.8


def test_training_comparison_and_unsupported_ovr() -> None:
    result = training_check(
        116000, 84, "Core Rare", [{"price": 200000, "overall": 84, "program": "Core Rare"}]
    )
    assert result["coins_per_training"] == 100
    assert result["rank"] == 1 and result["alert"] is True
    unsupported = training_check(100, 99, "Core Rare", [])
    assert unsupported["status"] == "UNSUPPORTED" and unsupported["alert"] is False


def definition(**overrides: object) -> dict:
    return {
        "collection_id": "fixture:collection",
        "required_number": 14,
        "returns_cards": True,
        "returned_cards_sellable": False,
        "reward_sellable": True,
        **overrides,
    }


def test_collection_keep_beats_direct_alternative() -> None:
    result = collection_evaluate(
        definition(reward_sellable=False),
        {
            "piece_costs": [100] * 14,
            "returned_cards": [],
            "reward_score_gain": 5,
            "direct_alternative_cost": 2000,
        },
    )
    assert result["decision"] == "KEEP REWARD"
    assert result["effective_collection_cost"] == 1400


def test_collection_sell_needs_legitimate_returned_recovery() -> None:
    inputs = {
        "piece_costs": [100] * 14,
        "returned_cards": [{"training": 10}] * 14,
        "qualified_coins_per_training": 5,
        "reward_sale_price": 800,
        "tax_rate": 0.10,
    }
    with_recovery = collection_evaluate(definition(), inputs)
    without_recovery = collection_evaluate(
        definition(), {**inputs, "qualified_coins_per_training": None}
    )
    assert with_recovery["decision"] == "SELL REWARD"
    assert without_recovery["decision"] == "PASS"


def test_fourteen_returned_cards_keep_training_and_coins_distinct() -> None:
    result = collection_evaluate(
        definition(reward_sellable=False),
        {
            "piece_costs": [100] * 14,
            "returned_cards": [{"training": 10}] * 14,
            "qualified_coins_per_training": 5,
        },
    )
    assert result["nominal_returned_training"] == 140
    assert result["training_market_replacement_value"] == 700
    assert result["warning"].startswith("training is reported separately")


def test_collection_passes_on_unknown_or_poor_rules() -> None:
    assert collection_evaluate({}, {})["decision"] == "PASS"
    result = collection_evaluate(
        definition(),
        {
            "piece_costs": [1000] * 14,
            "returned_cards": [],
            "reward_sale_price": 100,
            "tax_rate": 0.10,
        },
    )
    assert result["decision"] == "PASS"


def test_preposition_is_non_predictive() -> None:
    watch = preposition_evaluate({"collection_eligibility": True, "market_quality": "EARLY"})
    accumulate = preposition_evaluate(
        {
            "collection_eligibility": True,
            "market_quality": "USABLE",
            "at_or_below_accumulate_threshold": True,
        }
    )
    assert watch["action"] == "WATCH" and accumulate["action"] == "ACCUMULATE"
    assert watch["guaranteed_profit"] is False and watch["forecast"] is None
    assert "T-14" in watch["timeline_fields"] and "+7d" in watch["timeline_fields"]


def test_monitor_run_deduplicates_and_preserves_hit_list(cards: dict) -> None:
    card_id = top_targets(ROOT)[0]["card_id"]
    hit = hit_list_mutation([], "ADD", card_id, cards, now=AS_OF, target_buy_price=100)
    history = observations(card_id, [90])
    first = monitor_run(ROOT, hit, history, {}, AS_OF)
    second = monitor_run(ROOT, first["hit_list"], history, first["alert_state"], AS_OF)
    assert first["events"]
    assert second["events"] == []
    assert first["hit_list"][0]["card_id"] == card_id


def test_partial_evidence_does_not_authorize_buy() -> None:
    stats = history_statistics(observations("card:x", [100]), AS_OF)
    assert calibrate_decision(stats, "VALUE", gross_cost=100, budget=100)["decision"] != "BUY"
