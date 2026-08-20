from __future__ import annotations

import json
from collections import Counter

import pytest

from operation_pancake.production.market_campaign import (
    OBSERVATION_TYPES,
    append_history,
    calibrate_decision,
    enrich_observation,
    evidence_quality,
    history_statistics,
    prioritize_collection,
    snapshot_report,
    watch_boundaries,
)


def card():
    return {
        "card_id": "card:exact",
        "player_name": "Player",
        "position": "RG",
        "native_overall": 85,
        "program": "Prime",
        "archetype": "Power",
    }


def observation(
    price=100_000, kind="DISPLAYED_MARKET_PRICE", at="2026-08-20T10:00:00-07:00", fixture=False
):
    return enrich_observation(
        card(),
        price,
        kind,
        observed_at=at,
        ingested_at="2026-08-20T10:01:00-07:00",
        fixture=fixture,
    )


def test_manual_validation_identity_enrichment_and_timestamp_semantics():
    row = observation()
    assert row["player_name"] == "Player" and row["identity_confidence"] == "EXACT"
    assert row["source_published_at"] is None
    assert row["user_observed_at"] != row["ingested_at"]
    with pytest.raises(ValueError):
        enrich_observation({}, 1, "VISIBLE_LISTING")
    with pytest.raises(ValueError):
        observation(price=0)


@pytest.mark.parametrize("kind", sorted(OBSERVATION_TYPES))
def test_observation_types_are_preserved(kind):
    assert observation(kind=kind)["observation_type"] == kind


def test_append_only_deduplication_and_fixture_firewall(tmp_path):
    path = tmp_path / "history.json"
    first = observation()
    assert append_history(path, [first])["appended"] == 1
    assert append_history(path, [first])["appended"] == 0
    second = observation(at="2026-08-20T11:00:00-07:00")
    assert append_history(path, [second])["total"] == 2
    assert len(json.loads(path.read_text())) == 2
    with pytest.raises(ValueError, match="fixture"):
        append_history(path, [observation(fixture=True)])


def series(prices, hours):
    return [
        observation(price, at=f"2026-08-{20 + hour // 24:02d}T{hour % 24:02d}:00:00-07:00")
        for price, hour in zip(prices, hours, strict=True)
    ]


def test_statistics_states_changes_and_volatility():
    one = history_statistics(series([100], [0]), "2026-08-20T01:00:00-07:00")
    assert one["quality"] == "INSUFFICIENT" and one["volatility"] is None
    early = history_statistics(series([100, 101], [0, 1]), "2026-08-20T02:00:00-07:00")
    assert early["quality"] == "EARLY"
    usable = history_statistics(
        series([100, 101, 99, 100], [0, 12, 24, 36]), "2026-08-21T13:00:00-07:00"
    )
    assert usable["quality"] == "USABLE" and usable["longer_window_change"] == 0
    volatile = history_statistics(
        series([100, 200, 50, 220], [0, 24, 48, 72]), "2026-08-23T01:00:00-07:00"
    )
    assert volatile["volatility"] > 0.45


def test_strong_quality_requires_real_span_freshness_and_stability():
    semantics = Counter({"COMPLETED_SALE": 8})
    assert evidence_quality(8, 5, 72, 1, 0.1, True, semantics) == "STRONG"
    assert evidence_quality(8, 5, 72, 30, 0.1, True, semantics) == "EARLY"
    assert evidence_quality(8, 5, 72, 1, 0.1, False, semantics) == "INSUFFICIENT"


def test_decision_firewall_buy_wait_and_resale_net_cost():
    strong = {"quality": "STRONG", "observation_count": 8, "dispersion_ratio": 0.05}
    buy = calibrate_decision(strong, "STRONG VALUE", gross_cost=100, resale_value=25, budget=80)
    assert buy["decision"] == "BUY" and buy["net_cost"] == 75
    assert calibrate_decision(strong, "OVERPAY", gross_cost=100)["decision"] == "WAIT"
    assert (
        calibrate_decision(
            {"quality": "EARLY", "observation_count": 2}, "STRONG VALUE", gross_cost=100
        )["decision"]
        == "INSUFFICIENT MARKET DATA"
    )


def test_watch_boundaries_need_usable_evidence():
    assert watch_boundaries({"quality": "EARLY"})["status"] == "UNAVAILABLE"
    watch = watch_boundaries({"quality": "USABLE", "median": 90, "minimum": 80})
    assert watch["re_evaluate_at_or_below_median"] == 90
    assert "not BUY" in watch["warning"]


def test_snapshot_report_is_readable():
    report = snapshot_report(
        [
            {
                "candidate": "Candidate",
                "current": "Starter",
                "intrinsic_valuation": "VALUE",
                "latest_price": 100,
                "sample_count": 2,
                "quality": "EARLY",
                "net_cost": 80,
                "decision": "INSUFFICIENT MARKET DATA",
            }
        ]
    )
    assert "Candidate" in report and "INSUFFICIENT MARKET DATA" in report


def test_collection_priority_favors_actionable_intrinsic_value():
    rows = [
        {"candidate": "Expensive", "relative_valuation": "OVERPAY", "value_index": 99},
        {"candidate": "Actionable", "relative_valuation": "STRONG VALUE", "value_index": 20},
        {"candidate": "Middle", "relative_valuation": "FAIR", "value_index": 50},
    ]
    assert [row["candidate"] for row in prioritize_collection(rows)] == [
        "Actionable",
        "Middle",
        "Expensive",
    ]
