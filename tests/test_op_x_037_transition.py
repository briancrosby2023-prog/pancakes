from __future__ import annotations

from pathlib import Path

import pytest

from operation_pancake.production.market_campaign import append_history
from operation_pancake.production.transition import (
    AccountState,
    account_scorecard,
    baseline_strategies,
    checkpoint_time,
    chronological_validation,
    collection_result,
    event_record,
    false_positive_control,
    forecast_policy,
    observations_available,
    run_backtest,
)

RELEASE = "2026-08-20T20:00:00+00:00"
ROOT = Path(__file__).resolve().parents[1]


def row(record_id: str, label: str, price: int) -> dict:
    return {
        "record_id": record_id,
        "card_id": "card:x",
        "observed_at": checkpoint_time(RELEASE, label).isoformat(),
        "price": price,
    }


def test_t7_cannot_access_t1_and_backtest_never_uses_future_price() -> None:
    rows = [row("early", "T-7", 100), row("future", "T-1", 200)]

    def strategy(label: str, _state: AccountState, visible: list[dict]) -> list[dict]:
        if label == "T-7":
            assert [item["record_id"] for item in visible] == ["early"]
            return [{"action": "BUY", "card_id": "card:x"}]
        return [{"action": "HOLD"}]

    result = run_backtest(
        AccountState(coins=1000),
        RELEASE,
        rows,
        ["T-7", "T-1"],
        strategy,
        transaction_cost_rate=0.10,
    )
    assert result["timeline"][0]["state"]["coins"] == 900
    assert "future" not in result["timeline"][0]["available_record_ids"]


def test_available_at_prevents_late_publication_leakage() -> None:
    value = row("late", "T-7", 100)
    value["available_at"] = checkpoint_time(RELEASE, "T-1").isoformat()
    assert observations_available([value], checkpoint_time(RELEASE, "T-7")) == []


def test_transaction_costs_reduce_realized_profit() -> None:
    rows = [row("buy", "T-7", 100), row("sell", "T0", 200)]

    def strategy(label: str, _state: AccountState, _visible: list[dict]) -> list[dict]:
        return [{"action": "BUY" if label == "T-7" else "SELL", "card_id": "card:x"}]

    result = run_backtest(
        AccountState(coins=1000), RELEASE, rows, ["T-7", "T0"], strategy, transaction_cost_rate=0.10
    )
    assert result["final_state"]["coins"] == 1080
    assert result["final_state"]["realized_costs"] == 20


def test_preposition_trade_can_lose_money() -> None:
    rows = [row("buy", "T-7", 100), row("sell", "T0", 80)]

    def strategy(label: str, _state: AccountState, _visible: list[dict]) -> list[dict]:
        return [{"action": "BUY" if label == "T-7" else "SELL", "card_id": "card:x"}]

    result = run_backtest(
        AccountState(coins=1000), RELEASE, rows, ["T-7", "T0"], strategy, transaction_cost_rate=0.10
    )
    assert result["final_state"]["coins"] == 972


def test_training_is_distinct_and_scorecard_reconciles_components() -> None:
    state = AccountState(
        coins=100, roster={"r": {"pancake_score": 80}}, inventory={"i": {}}, training=10
    )
    unavailable = account_scorecard(state, {"r": 200, "i": 50}, collection_recovery_value=20)
    assert unavailable["qualified_training_replacement_value"] is None
    assert unavailable["total_qualified_account_value"] is None
    scored = account_scorecard(
        state, {"r": 200, "i": 50}, qualified_coins_per_training=2, collection_recovery_value=20
    )
    assert scored["training_inventory"] == 10
    assert scored["qualified_training_replacement_value"] == 20
    assert scored["total_qualified_account_value"] == 390


def test_returned_training_recovery_and_keep_reward_football_comparison() -> None:
    keep = collection_result(
        {
            "required_number": 2,
            "returns_cards": True,
            "returned_cards_sellable": False,
            "reward_sellable": False,
        },
        {
            "piece_costs": [100, 100],
            "returned_cards": [{"training": 10}, {"training": 10}],
            "qualified_coins_per_training": 2,
            "reward_score_gain": 2,
            "direct_alternative_cost": 300,
        },
    )
    assert keep["decision"] == "KEEP REWARD"
    assert keep["nominal_returned_training"] == 20
    assert keep["training_market_replacement_value"] == 40


def test_sell_reward_after_cost_and_poor_collection_pass() -> None:
    profitable = collection_result(
        {"required_number": 2, "returns_cards": False, "reward_sellable": True},
        {"piece_costs": [100, 100], "reward_sale_price": 300, "tax_rate": 0.10},
    )
    poor = collection_result(
        {"required_number": 2, "returns_cards": False, "reward_sellable": True},
        {"piece_costs": [200, 200], "reward_sale_price": 300, "tax_rate": 0.10},
    )
    assert profitable["decision"] == "SELL REWARD" and profitable["expected_profit"] == 70
    assert poor["decision"] == "PASS"


def test_false_positive_rejects_anomaly_low_liquidity_and_volume_less_spike() -> None:
    result = false_positive_control(
        {
            "sale_count": 1,
            "distinct_timestamps": 1,
            "volume_change": 0,
            "liquidity": 0.1,
            "spread": 0.3,
            "verified_catalyst": False,
        }
    )
    assert result["state"] == "NO ACTION"
    assert {"INSUFFICIENT SALES", "LOW LIQUIDITY", "NO VOLUME CONFIRMATION"}.issubset(
        result["reasons"]
    )


def test_false_positive_only_becomes_eligible_with_all_evidence() -> None:
    result = false_positive_control(
        {
            "sale_count": 8,
            "distinct_timestamps": 5,
            "volume_change": 0.5,
            "liquidity": 0.8,
            "spread": 0.05,
            "verified_catalyst": True,
        }
    )
    assert result == {"state": "ELIGIBLE FOR VALIDATION", "confidence": "TESTABLE", "reasons": []}


def test_baselines_share_identical_initial_capital_and_no_action_is_valid() -> None:
    initial = AccountState(coins=1000)
    outputs = [
        run_backtest(initial, RELEASE, [], ["T-7"], strategy, transaction_cost_rate=0.10)
        for strategy in baseline_strategies().values()
    ]
    assert all(item["initial_state"]["coins"] == 1000 for item in outputs)
    assert baseline_strategies()["DO NOTHING / HOLD"]("T-7", initial, []) == [{"action": "HOLD"}]


def test_chronological_validation_preserves_event_order() -> None:
    events = [
        {"event_id": "later", "release_time": "2026-08-20T00:00:00+00:00"},
        {"event_id": "earlier", "release_time": "2025-08-20T00:00:00+00:00"},
    ]
    result = chronological_validation(events)
    assert result["event_order"] == ["earlier", "later"]
    assert result["folds"][0] == {"train_event_ids": ["earlier"], "test_event_id": "later"}


def test_insufficient_history_promotes_no_forecast_or_buy_bypass() -> None:
    validation = chronological_validation([])
    policy = forecast_policy(validation)
    assert policy["model"] == "NO FORECAST"
    assert policy["supported_states"] == []
    assert policy["production_action"] == "NO ACTION"
    assert policy["buy_gate_bypass"] is False


def test_unknown_collection_rules_remain_unknown() -> None:
    assert collection_result({}, {}) == {
        "decision": "PASS",
        "status": "UNKNOWN RULES OR INCOMPLETE INPUTS",
    }


def test_event_catalog_validates_type_and_unknown_fields() -> None:
    event = event_record(event_id="e1", event_type="SEASON TRANSITION")
    assert event["release_time"] == "UNKNOWN"
    assert event["collection_requirements"] == "UNKNOWN"
    with pytest.raises(ValueError, match="unsupported event type"):
        event_record(event_id="e2", event_type="RUMOR")


def test_fixture_observations_cannot_enter_real_history(tmp_path: Path) -> None:
    fixture = [{"observation_id": "x", "evidence_scope": "FIXTURE"}]
    with pytest.raises(ValueError, match="fixture observations"):
        append_history(tmp_path / "history.json", fixture)


def test_repeated_backtest_is_deterministic() -> None:
    initial = AccountState(coins=1000)
    strategy = baseline_strategies()["DO NOTHING / HOLD"]
    first = run_backtest(
        initial,
        RELEASE,
        [row("x", "T-7", 100)],
        ["T-7", "T0"],
        strategy,
        transaction_cost_rate=0.10,
    )
    assert first == run_backtest(
        initial,
        RELEASE,
        [row("x", "T-7", 100)],
        ["T-7", "T0"],
        strategy,
        transaction_cost_rate=0.10,
    )
