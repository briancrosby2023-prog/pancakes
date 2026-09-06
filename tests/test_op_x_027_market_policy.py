from __future__ import annotations

from pathlib import Path

import pytest

from operation_pancake.production.engine import load_population
from operation_pancake.production.gm import manual_price_payload
from operation_pancake.production.market import (
    CanonicalMarketObservation,
    buy_wait_policy,
    risk_flags,
)

ROOT = Path(__file__).resolve().parents[1]


def market(**overrides):
    value = {
        "candidate_price": 50_000,
        "score_improvement": 5,
        "affordable": True,
        "value_classification": "GOOD VALUE",
        "market_confidence": "HIGH",
        "risk_flags": [],
    }
    value.update(overrides)
    return value


@pytest.mark.parametrize(
    ("value", "identity", "model", "source", "policy", "expected"),
    [
        (None, "EXACT", "ROUTED", "PUBLIC", "role-v1", "PRICE CHECK REQUIRED"),
        (market(), "EXACT", "ROUTED", "TEST DATA", "role-v1", "INSUFFICIENT MARKET DATA"),
        (market(), "AMBIGUOUS", "ROUTED", "PUBLIC", "role-v1", "INSUFFICIENT MARKET DATA"),
        (
            market(),
            "EXACT",
            "DIAGNOSTIC_ONLY",
            "PUBLIC",
            "role-v1",
            "INSUFFICIENT MARKET DATA",
        ),
        (market(score_improvement=-1), "EXACT", "ROUTED", "PUBLIC", "role-v1", "WAIT"),
        (
            market(risk_flags=["STALE PRICE"], market_confidence="LOW"),
            "EXACT",
            "ROUTED",
            "PUBLIC",
            "role-v1",
            "INSUFFICIENT MARKET DATA",
        ),
        (market(), "EXACT", "ROUTED", "PUBLIC", None, "WAIT"),
        (market(affordable=False), "EXACT", "ROUTED", "PUBLIC", "role-v1", "WAIT"),
        (market(), "EXACT", "ROUTED", "PUBLIC", "role-v1", "BUY"),
    ],
)
def test_false_buy_controls(value, identity, model, source, policy, expected):
    result = buy_wait_policy(
        value,
        identity_classification=identity,
        model_status=model,
        evidence_source=source,
        threshold_policy_id=policy,
    )
    assert result["action"] == expected


def test_manual_ingestion_rejects_ambiguous_and_unknown_identity():
    population = load_population(ROOT)
    result = manual_price_payload(
        [
            {
                "player_name": "Nikai Martinez",
                "observed_price": 10_000,
                "provenance": "OP-X-027 TEST DATA",
            },
            {
                "canonical_card_id": "unknown",
                "observed_price": 10_000,
                "provenance": "OP-X-027 TEST DATA",
            },
        ],
        "2026-08-20T12:00:00-07:00",
        population,
    )
    assert not result["accepted"]
    assert len(result["rejected"]) == 2


def test_manual_ingestion_accepts_exact_identity_and_preserves_provenance():
    population = load_population(ROOT)
    card = population[0]
    result = manual_price_payload(
        [
            {
                "canonical_card_id": card["card_id"],
                "observed_price": 10_000,
                "source": "USER_SUPPLIED",
                "provenance": "OP-X-027 TEST DATA",
            }
        ],
        "2026-08-20T12:00:00-07:00",
        population,
    )
    assert len(result["accepted"]) == 1
    assert result["accepted"][0]["provenance"] == "OP-X-027 TEST DATA"


def test_future_timestamp_is_insufficient_market_evidence():
    observation = CanonicalMarketObservation(
        observation_id="observation:test",
        external_card_id=None,
        card_id="card:test",
        player_name="Test Player",
        position="RG",
        overall=85,
        program="Test",
        observed_price=10_000,
        currency="CUT_COINS",
        source="USER_SUPPLIED",
        source_url=None,
        observed_at="2026-08-21T12:00:00-07:00",
        observation_type="manual",
        platform="XBOX",
        sample_count=2,
        low=None,
        median=None,
        high=None,
        liquidity_proxy=None,
        confidence="HIGH",
        provenance="OP-X-027 TEST DATA",
    )
    flags = risk_flags(observation, "2026-08-20T12:00:00-07:00")
    assert "FUTURE TIMESTAMP" in flags
    assert "INSUFFICIENT DATA" in flags
