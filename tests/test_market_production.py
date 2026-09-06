import json
from pathlib import Path

import pytest

from operation_pancake.production.engine import load_population
from operation_pancake.production.market import (
    MoneyballEngine,
    analyze_ltd,
    deduplicate,
    ingest_market_file,
    normalize_observation,
    resolve_observations,
    risk_flags,
    training_economics,
)

ROOT = Path(__file__).resolve().parents[1]


def observed(**overrides):
    values = {
        "external_card_id": "ext-1",
        "price": 100000,
        "currency": "CUT_COINS",
        "source": "TEST",
        "observed_at": "2026-08-20T00:00:00-07:00",
        "observation_type": "USER_SUPPLIED_OBSERVATION",
        "provenance": "test fixture",
    }
    values.update(overrides)
    return normalize_observation(values, "test")


def test_market_schema_validates_price_and_timezone():
    assert observed().observed_price == 100000
    with pytest.raises(ValueError, match="positive"):
        observed(price=0)
    with pytest.raises(ValueError, match="timezone"):
        observed(observed_at="2026-08-20T00:00:00")


def test_json_csv_ingestion_rejection_and_deduplication(tmp_path):
    good = {
        "external_card_id": "x",
        "price": 10,
        "currency": "CUT_COINS",
        "source": "USER",
        "observed_at": "2026-08-20T00:00:00Z",
        "observation_type": "DISPLAY_PRICE",
        "provenance": "manual",
    }
    path = tmp_path / "prices.json"
    path.write_text(json.dumps([good, good, {**good, "price": -1}]))
    rows, rejected = ingest_market_file(path)
    assert len(rows) == 1 and len(rejected) == 1
    csv_path = tmp_path / "prices.csv"
    csv_path.write_text(
        "external_card_id,price,currency,source,observed_at,observation_type,provenance\n"
        "x,10,CUT_COINS,USER,2026-08-20T00:00:00Z,DISPLAY_PRICE,manual\n"
    )
    assert len(ingest_market_file(csv_path)[0]) == 1


def test_exact_card_resolution_wins_and_ambiguous_signature_is_rejected():
    population = load_population(ROOT)
    card = population[0]
    exact = observed(external_card_id=card["source_card_id"])
    assert resolve_observations([exact], population)[0]["classification"] == "EXACT"
    ambiguous = observed(
        external_card_id="missing", player_name="Dante Moore", position="QB", overall=None
    )
    result = resolve_observations([ambiguous], population)[0]
    assert result["classification"] == "AMBIGUOUS" and result["canonical_card_id"] is None


def test_freshness_confidence_and_risk_flags_are_transparent():
    stale = observed(observed_at="2026-08-13T00:00:00-07:00", low=50000, high=150000)
    flags = risk_flags(stale, "2026-08-20T00:00:00-07:00")
    assert {"STALE PRICE", "SINGLE OBSERVATION", "HIGH SPREAD", "INSUFFICIENT DATA"} <= set(flags)


def test_moneyball_handles_price_resale_budget_and_no_price():
    engine = MoneyballEngine()
    assert (
        engine.evaluate(5, 6, 20, None, "2026-08-20T00:00:00Z")["status"] == "PRICE CHECK REQUIRED"
    )
    result = engine.evaluate(
        5,
        6,
        20,
        observed(sample_count=3),
        "2026-08-20T01:00:00-07:00",
        current_resale_value=20000,
        coin_budget=90000,
        classification_thresholds={"elite": 0.04, "good": 0.03, "fair": 0.01},
    )
    assert result["net_upgrade_cost"] == 80000 and result["affordable"] is True
    assert result["improvement_per_1000_coins"] == 0.0625
    assert result["value_classification"] == "ELITE VALUE"


def test_training_and_ltd_interfaces_do_not_predict_without_evidence():
    training = training_economics(116000, 84, "Core Rare")
    assert training["training_value"] == 1160 and training["coins_per_training"] == 100
    platinum = training_economics(400000, 84, "Platinum Rare")
    assert platinum["coin_quicksell_floor"] == 350000
    ltd = analyze_ltd(500000, 450000, 350000, "2026-08-20T00:00:00Z", "2026-08-10")
    assert ltd["downside_to_floor"] == 100000
    assert ltd["depreciation_prediction"] is None


def test_repository_observations_are_real_exact_and_stale():
    rows, rejected = ingest_market_file(
        ROOT / "data/research/cfb27_op_x_003/market_observations.json"
    )
    resolved = resolve_observations(rows, load_population(ROOT))
    assert len(rows) == 8 and not rejected
    assert all(row["classification"] == "EXACT" for row in resolved)
    assert all("STALE PRICE" in risk_flags(row, "2026-08-20T00:00:00-07:00") for row in rows)


def test_deduplication_preserves_distinct_timestamped_history():
    first = observed()
    second = observed(observed_at="2026-08-20T01:00:00-07:00")
    assert len(deduplicate([first, first, second])) == 2
