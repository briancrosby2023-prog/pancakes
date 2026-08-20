from __future__ import annotations

import itertools
from pathlib import Path

import pytest

from operation_pancake.production.engine import ProductionEngine
from operation_pancake.production.gm import (
    ACTIONS,
    GMProduct,
    manual_price_payload,
    optimize_budget,
)
from operation_pancake.production.market import MoneyballEngine, normalize_observation
from operation_pancake.production.registry import build_model_registry

ROOT = Path(__file__).resolve().parents[1]
AS_OF = "2026-08-20T12:00:00-07:00"


def _brute_force(candidates, budget):
    eligible = [
        row
        for row in candidates
        if row.get("net_cost") is not None
        and row["net_cost"] >= 0
        and row.get("score_improvement", 0) > 0
        and not row.get("protected", False)
    ]
    choices = []
    for size in range(len(eligible) + 1):
        for subset in itertools.combinations(eligible, size):
            spent = sum(int(row["net_cost"]) for row in subset)
            if spent <= budget:
                gain = sum(float(row["score_improvement"]) for row in subset)
                choices.append((gain, -spent, [row["card_id"] for row in subset]))
    return max(choices)


@pytest.mark.parametrize(
    ("candidates", "budget"),
    [
        ([{"card_id": "premium", "net_cost": 100, "score_improvement": 8}], 100),
        (
            [
                {"card_id": "premium", "net_cost": 100, "score_improvement": 5},
                {"card_id": "a", "net_cost": 45, "score_improvement": 3},
                {"card_id": "b", "net_cost": 45, "score_improvement": 3},
            ],
            100,
        ),
        ([{"card_id": "zero", "net_cost": 50, "score_improvement": 0}], 100),
        ([{"card_id": "missing", "net_cost": None, "score_improvement": 9}], 100),
        (
            [{"card_id": "protected", "net_cost": 10, "score_improvement": 9, "protected": True}],
            100,
        ),
        ([{"card_id": "boundary", "net_cost": 100, "score_improvement": 2}], 100),
        ([{"card_id": "expensive", "net_cost": 101, "score_improvement": 20}], 100),
        ([{"card_id": "resale", "net_cost": 60, "score_improvement": 4}], 60),
        (
            [
                {"card_id": "first", "net_cost": 50, "score_improvement": 5},
                {"card_id": "second", "net_cost": 50, "score_improvement": 5},
            ],
            50,
        ),
    ],
)
def test_budget_optimizer_matches_independent_brute_force(candidates, budget):
    expected_gain, expected_negative_spend, _expected_ids = _brute_force(candidates, budget)
    actual = optimize_budget(candidates, budget)
    assert actual["score_improvement"] == expected_gain
    assert actual["spent"] == -expected_negative_spend
    if {row["card_id"] for row in candidates} == {"first", "second"}:
        assert [row["card_id"] for row in actual["selected"]] == ["first"]


def test_manual_market_validation_preserves_valid_rows_and_rejects_invalid_rows():
    rows = [
        {"canonical_card_id": "valid", "observed_price": 1000, "provenance": "TEST DATA"},
        {"canonical_card_id": "zero", "observed_price": 0},
        {"canonical_card_id": "negative", "observed_price": -1},
        {"canonical_card_id": "fractional", "observed_price": 1.5},
        {
            "canonical_card_id": "naive",
            "observed_price": 100,
            "observed_at": "2026-08-20T12:00:00",
        },
        {"canonical_card_id": "malformed"},
    ]
    result = manual_price_payload(rows, AS_OF)
    assert len(result["accepted"]) == 1
    assert len(result["rejected"]) == 5
    assert result["accepted"][0]["provenance"] == "TEST DATA"


def test_moneyball_keeps_football_and_market_evidence_independent():
    engine = MoneyballEngine()
    missing = engine.evaluate(5, 6, 4, None, AS_OF)
    assert missing["status"] == "PRICE CHECK REQUIRED"
    fresh = normalize_observation(
        {
            "canonical_card_id": "fixture",
            "observed_price": 10_000,
            "observed_at": AS_OF,
            "sample_count": 3,
            "source": "TEST DATA",
            "provenance": "OP-X-026 TEST DATA",
        },
        "OP-X-026 TEST DATA",
    )
    evaluated = engine.evaluate(5, 6, 4, fresh, AS_OF, 2_000, 10_000)
    assert evaluated["score_improvement"] == 5
    assert evaluated["net_upgrade_cost"] == 8_000
    assert evaluated["affordable"] is True
    stale = normalize_observation(
        {
            "canonical_card_id": "fixture",
            "observed_price": 10_000,
            "observed_at": "2026-08-18T12:00:00-07:00",
            "sample_count": 3,
            "source": "TEST DATA",
            "provenance": "OP-X-026 TEST DATA",
        },
        "OP-X-026 TEST DATA",
    )
    stale_result = engine.evaluate(5, 6, 4, stale, AS_OF)
    assert stale_result["status"] == "PRICE CHECK REQUIRED"
    assert "STALE PRICE" in stale_result["risk_flags"]
    worse = engine.evaluate(-1, -1, -1, fresh, AS_OF)
    assert worse["score_improvement"] < 0
    assert worse["status"] != "BUY"


def test_lookup_ambiguity_filters_and_unknown_identity():
    gm = GMProduct(ROOT)
    ambiguous = gm.lookup(player_name="Nikai Martinez")
    assert ambiguous["status"] == "AMBIGUOUS CARD VERSION"
    exact = gm.lookup(card_id=ambiguous["matches"][0]["card_id"])
    assert exact["card"]["card_id"] == ambiguous["matches"][0]["card_id"]
    narrowed = gm.lookup(
        player_name="Nikai Martinez",
        position=ambiguous["matches"][0]["position"],
        overall=ambiguous["matches"][0]["native_overall"],
        program=ambiguous["matches"][0]["program"],
    )
    assert narrowed["status"] != "AMBIGUOUS CARD VERSION"
    assert gm.lookup(card_id="not-a-card")["status"] == "UNRESOLVED IDENTITY"


def test_research_production_firewall_and_action_vocabulary():
    registry = build_model_registry(ROOT)
    engine = ProductionEngine(registry)
    evidence = " ".join(
        path for model in registry["models"] for path in model.get("evidence_paths", [])
    )
    assert "op_x_024" not in evidence.casefold()
    assert engine.route("TE", "Pure Blocker")["status"] == "DIAGNOSTIC_ONLY"
    assert engine.route("C", "Agile")["status"] == "ROUTED"
    assert engine.route("QB", "Pure Runner")["status"] == "UNSUPPORTED"
    assert {
        "KEEP",
        "START",
        "BENCH",
        "UPGRADE",
        "BUY",
        "WAIT",
        "SELL/REPLACE",
        "BUDGET UPGRADE",
        "PREMIUM UPGRADE",
        "PRICE CHECK REQUIRED",
        "INSUFFICIENT ATTRIBUTES",
        "UNRESOLVED IDENTITY",
        "UNSUPPORTED MODEL",
        "INSUFFICIENT MARKET DATA",
    } <= ACTIONS
