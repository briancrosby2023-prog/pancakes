"""Leakage-safe season-transition measurement and NMS backtesting services."""

from __future__ import annotations

import copy
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable

from .market import parse_timestamp
from .monitor import collection_evaluate

WINDOW_LABELS = (
    "T-14",
    "T-10",
    "T-7",
    "T-5",
    "T-3",
    "T-2",
    "T-1",
    "T0",
    "T+6h",
    "T+12h",
    "T+24h",
    "T+48h",
    "T+72h",
    "T+7d",
)
EVENT_TYPES = {
    "SEASON TRANSITION",
    "MAJOR COLLECTION RELEASE",
    "SCHEME COLLECTION",
    "PROGRAM RELEASE",
    "LTD RELEASE",
    "PACK/OFFER CHANGE",
    "TRAINING-RELATED EVENT",
    "OVR-TIER CHANGE",
    "OTHER DOCUMENTED MARKET CATALYST",
}
ACTIONS = {
    "BUY",
    "SELL",
    "HOLD",
    "ACCUMULATE",
    "COMPLETE COLLECTION",
    "KEEP REWARD",
    "SELL REWARD",
    "CONVERT TO TRAINING",
    "PASS",
}


@dataclass(slots=True)
class AccountState:
    coins: int
    roster: dict[str, dict[str, Any]] = field(default_factory=dict)
    inventory: dict[str, dict[str, Any]] = field(default_factory=dict)
    training: int = 0
    protected_assets: set[str] = field(default_factory=set)
    collection_pieces: dict[str, dict[str, Any]] = field(default_factory=dict)
    realized_costs: int = 0

    def clone(self) -> "AccountState":
        return copy.deepcopy(self)


def event_record(**values: Any) -> dict[str, Any]:
    event_type = values.get("event_type")
    if event_type not in EVENT_TYPES:
        raise ValueError(f"unsupported event type: {event_type}")
    release = values.get("release_time")
    announcement = values.get("announcement_time")
    if release not in {None, "UNKNOWN"}:
        parse_timestamp(release)
    if announcement not in {None, "UNKNOWN"}:
        parse_timestamp(announcement)
    return {
        "event_id": values["event_id"],
        "game_year": values.get("game_year", "UNKNOWN"),
        "season": values.get("season", "UNKNOWN"),
        "event_name": values.get("event_name", "UNKNOWN"),
        "event_type": event_type,
        "announcement_time": announcement or "UNKNOWN",
        "release_time": release or "UNKNOWN",
        "collection_requirements": values.get("collection_requirements", "UNKNOWN"),
        "reward": values.get("reward", "UNKNOWN"),
        "returned_card_behavior": values.get("returned_card_behavior", "UNKNOWN"),
        "pack_offer_context": values.get("pack_offer_context", "UNKNOWN"),
        "source": values.get("source", "UNKNOWN"),
        "confidence": values.get("confidence", "LOW"),
    }


def checkpoint_time(release_time: str, label: str) -> datetime:
    release = parse_timestamp(release_time)
    offsets = {
        "T-14": timedelta(days=-14),
        "T-10": timedelta(days=-10),
        "T-7": timedelta(days=-7),
        "T-5": timedelta(days=-5),
        "T-3": timedelta(days=-3),
        "T-2": timedelta(days=-2),
        "T-1": timedelta(days=-1),
        "T0": timedelta(0),
        "T+6h": timedelta(hours=6),
        "T+12h": timedelta(hours=12),
        "T+24h": timedelta(hours=24),
        "T+48h": timedelta(hours=48),
        "T+72h": timedelta(hours=72),
        "T+7d": timedelta(days=7),
    }
    if label not in offsets:
        raise ValueError(f"unknown checkpoint: {label}")
    return release + offsets[label]


def observations_available(
    rows: list[dict[str, Any]], decision_time: datetime
) -> list[dict[str, Any]]:
    """Return only evidence published/observed at or before the decision."""
    output = []
    for row in rows:
        observed = parse_timestamp(row["observed_at"])
        available = parse_timestamp(row.get("available_at", row["observed_at"]))
        if observed <= decision_time and available <= decision_time:
            output.append(copy.deepcopy(row))
    return sorted(output, key=lambda row: (row["observed_at"], row.get("record_id", "")))


def price_at_or_before(
    rows: list[dict[str, Any]], card_id: str, decision_time: datetime
) -> int | None:
    visible = [
        row for row in observations_available(rows, decision_time) if row["card_id"] == card_id
    ]
    return visible[-1]["price"] if visible else None


def account_scorecard(
    state: AccountState,
    qualified_prices: dict[str, int],
    *,
    qualified_coins_per_training: float | None = None,
    collection_recovery_value: int | None = None,
    peak_qualified_value: int | None = None,
) -> dict[str, Any]:
    roster_value = sum(qualified_prices.get(card_id, 0) for card_id in state.roster)
    inventory_value = sum(qualified_prices.get(card_id, 0) for card_id in state.inventory)
    roster_strength = sum(float(row.get("pancake_score", 0)) for row in state.roster.values())
    training_value = (
        None
        if qualified_coins_per_training is None
        else round(state.training * qualified_coins_per_training)
    )
    qualified_total = (
        None
        if training_value is None or collection_recovery_value is None
        else state.coins
        + roster_value
        + inventory_value
        + training_value
        + collection_recovery_value
    )
    drawdown = (
        None
        if qualified_total is None or peak_qualified_value is None or peak_qualified_value <= 0
        else round((peak_qualified_value - qualified_total) / peak_qualified_value, 6)
    )
    return {
        "liquid_coins": state.coins,
        "roster_pancake_strength": round(roster_strength, 6),
        "roster_market_value": roster_value,
        "inventory_market_value": inventory_value,
        "training_inventory": state.training,
        "qualified_training_replacement_value": training_value,
        "collection_recovery_value": collection_recovery_value,
        "total_qualified_account_value": qualified_total,
        "drawdown": drawdown,
        "capital_at_risk": inventory_value + roster_value,
        "realized_transaction_costs": state.realized_costs,
    }


def apply_action(
    state: AccountState,
    action: dict[str, Any],
    visible_prices: dict[str, int],
    *,
    transaction_cost_rate: float,
) -> AccountState:
    result = state.clone()
    kind = action["action"]
    if kind not in ACTIONS:
        raise ValueError(f"unsupported action: {kind}")
    card_id = action.get("card_id")
    if kind in {"BUY", "ACCUMULATE"}:
        price = visible_prices.get(card_id)
        if price is None or price > result.coins:
            return result
        result.coins -= price
        result.inventory[card_id] = {"acquisition_cost": price, **action.get("card", {})}
    elif kind == "SELL" and card_id in result.inventory and card_id not in result.protected_assets:
        price = visible_prices.get(card_id)
        if price is None:
            return result
        fee = round(price * transaction_cost_rate)
        result.coins += price - fee
        result.realized_costs += fee
        result.inventory.pop(card_id)
    elif kind == "CONVERT TO TRAINING" and card_id in result.inventory:
        training = result.inventory[card_id].get("training")
        if training is not None:
            result.training += int(training)
            result.inventory.pop(card_id)
    return result


Strategy = Callable[[str, AccountState, list[dict[str, Any]]], list[dict[str, Any]]]


def run_backtest(
    initial: AccountState,
    release_time: str,
    rows: list[dict[str, Any]],
    checkpoints: list[str],
    strategy: Strategy,
    *,
    transaction_cost_rate: float,
) -> dict[str, Any]:
    state = initial.clone()
    timeline = []
    card_ids = sorted({row["card_id"] for row in rows})
    for label in checkpoints:
        decision_time = checkpoint_time(release_time, label)
        visible = observations_available(rows, decision_time)
        prices = {
            card_id: price
            for card_id in card_ids
            if (price := price_at_or_before(rows, card_id, decision_time)) is not None
        }
        actions = strategy(label, state.clone(), copy.deepcopy(visible))
        for action in actions:
            state = apply_action(
                state,
                action,
                prices,
                transaction_cost_rate=transaction_cost_rate,
            )
        timeline.append(
            {
                "checkpoint": label,
                "decision_time": decision_time.isoformat(),
                "available_record_ids": [row.get("record_id") for row in visible],
                "actions": actions,
                "state": asdict(state),
            }
        )
    return {"initial_state": asdict(initial), "timeline": timeline, "final_state": asdict(state)}


def baseline_strategies() -> dict[str, Strategy]:
    def hold(
        _label: str, _state: AccountState, _rows: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        return [{"action": "HOLD"}]

    def pass_strategy(
        _label: str, _state: AccountState, _rows: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        return [{"action": "PASS"}]

    return {
        "DO NOTHING / HOLD": hold,
        "BUY BEST OVR": pass_strategy,
        "BUY BEST PANCAKE FOOTBALL VALUE": pass_strategy,
        "LIQUIDATE EARLY": pass_strategy,
        "COLLECTION PRE-POSITION": pass_strategy,
        "TRAINING PRE-POSITION": pass_strategy,
        "PANCAKE MULTI-SIGNAL": pass_strategy,
    }


def false_positive_control(signal: dict[str, Any]) -> dict[str, Any]:
    reasons = []
    if signal.get("sale_count", 0) < 3:
        reasons.append("INSUFFICIENT SALES")
    if signal.get("distinct_timestamps", 0) < 2:
        reasons.append("ANOMALOUS SINGLE OBSERVATION")
    if signal.get("volume_change") is None or signal.get("volume_change", 0) <= 0:
        reasons.append("NO VOLUME CONFIRMATION")
    if signal.get("liquidity", 0) < 0.25:
        reasons.append("LOW LIQUIDITY")
    if signal.get("spread", 1) > 0.15:
        reasons.append("HIGH SPREAD")
    if signal.get("verified_catalyst") is not True:
        reasons.append("CATALYST UNVERIFIED")
    return {
        "state": "NO ACTION" if reasons else "ELIGIBLE FOR VALIDATION",
        "confidence": "LOW" if reasons else "TESTABLE",
        "reasons": reasons,
    }


def chronological_validation(events: list[dict[str, Any]]) -> dict[str, Any]:
    dated = [row for row in events if row.get("release_time") not in {None, "UNKNOWN"}]
    ordered = sorted(dated, key=lambda row: parse_timestamp(row["release_time"]))
    folds = [
        {
            "train_event_ids": [row["event_id"] for row in ordered[:index]],
            "test_event_id": ordered[index]["event_id"],
        }
        for index in range(1, len(ordered))
    ]
    sufficient = [row for row in ordered if row.get("market_window_complete") is True]
    return {
        "event_order": [row["event_id"] for row in ordered],
        "folds": folds,
        "sufficient_market_events": len(sufficient),
        "forecast_promoted": len(sufficient) >= 3,
        "status": "VALIDATION BLOCKED — INSUFFICIENT HISTORICAL MARKET WINDOWS"
        if len(sufficient) < 3
        else "READY FOR EXPANDING-WINDOW VALIDATION",
    }


def forecast_policy(validation: dict[str, Any]) -> dict[str, Any]:
    if not validation.get("forecast_promoted"):
        return {
            "model": "NO FORECAST",
            "supported_states": [],
            "production_action": "NO ACTION",
            "reason": validation["status"],
            "buy_gate_bypass": False,
        }
    return {
        "model": "UNFITTED — VALIDATION IMPLEMENTATION REQUIRED",
        "supported_states": [],
        "production_action": "NO ACTION",
        "buy_gate_bypass": False,
    }


def collection_result(definition: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    return collection_evaluate(definition, inputs)


def load_repository_market_evidence(root: Path) -> dict[str, Any]:
    path = root / "data/production/market/user_observation_history.json"
    rows = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
    return {
        "path": str(path.relative_to(root)),
        "records": len(rows),
        "completed_sales": sum(row.get("observation_type") == "COMPLETED_SALE" for row in rows),
        "fixture_records": sum(row.get("evidence_scope") == "FIXTURE" for row in rows),
    }
