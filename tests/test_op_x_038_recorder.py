from __future__ import annotations

import json
from pathlib import Path

import pytest

from operation_pancake.production.market_campaign import calibrate_decision, history_statistics
from operation_pancake.production.monitor import reconcile_events
from operation_pancake.production.recorder import (
    append_records,
    canonical_cards,
    completed_sale_statistics,
    deduplicated_targets,
    default_campaign,
    event_checkpoint_coverage,
    listing_statistics,
    longitudinal_export,
    normalize_record,
    parse_browser_export,
    register_event,
    run_snapshot,
    sample_sufficiency,
    scheduler_state,
    training_basket,
)
from operation_pancake.production.transition import checkpoint_time, observations_available

ROOT = Path(__file__).resolve().parents[1]
NOW = "2026-08-20T21:00:00+00:00"
OBSERVED = "2026-08-20T20:00:00+00:00"


@pytest.fixture(scope="module")
def cards() -> dict:
    return canonical_cards(ROOT)


@pytest.fixture
def campaign() -> dict:
    return default_campaign(ROOT, "2026-08-20T00:00:00+00:00")


def raw(card_id: str, campaign_id: str, **changes: object) -> dict:
    return {
        "card_id": card_id,
        "value": 100,
        "observation_type": "LOWEST_VISIBLE_LISTING",
        "observed_at": OBSERVED,
        "source": "fixture",
        "platform": "XBOX",
        "campaign_id": campaign_id,
        **changes,
    }


def normalized(cards: dict, campaign: dict, **changes: object) -> dict:
    card_id = campaign["cards"][0]["card_id"]
    return normalize_record(
        raw(card_id, campaign["campaign_id"], **changes),
        cards,
        {campaign["campaign_id"]: campaign},
        ingested_at=NOW,
        fixture=True,
    )


def test_same_card_in_three_campaigns_is_one_target_with_all_reasons(campaign: dict) -> None:
    card = campaign["cards"][0]
    campaigns = []
    for index in range(3):
        campaigns.append(
            {
                "campaign_id": f"c{index}",
                "active": True,
                "priority": index + 1,
                "cards": [
                    {
                        "card_id": card["card_id"],
                        "reasons": [f"reason {index}"],
                        "sources": [f"source {index}"],
                    }
                ],
            }
        )
    targets = deduplicated_targets(campaigns)
    assert len(targets) == 1
    assert targets[0]["reasons"] == ["reason 0", "reason 1", "reason 2"]
    assert targets[0]["campaign_ids"] == ["c0", "c1", "c2"]


def test_default_campaign_contains_39_exact_deduplicated_cards(campaign: dict) -> None:
    assert len(campaign["cards"]) == 39
    assert len({row["card_id"] for row in campaign["cards"]}) == 39
    assert {row["tier"] for row in campaign["cards"]}.issubset({"TIER 1", "TIER 2", "TIER 3"})


def test_sale_and_listing_semantics_remain_distinct(cards: dict, campaign: dict) -> None:
    listing = normalized(cards, campaign)
    sale = normalized(cards, campaign, observation_type="COMPLETED_SALE")
    assert listing["source_semantics"]["class"] == "LISTING"
    assert sale["source_semantics"]["class"] == "SALE"
    assert listing["observation_type"] != sale["observation_type"]


def test_completed_sale_statistics_never_include_listing(cards: dict, campaign: dict) -> None:
    rows = [
        normalized(cards, campaign),
        normalized(cards, campaign, observation_type="COMPLETED_SALE"),
    ]
    assert completed_sale_statistics(rows)["count"] == 1
    assert listing_statistics(rows)["listing_samples"] == 1


def test_duplicate_does_not_grow_but_later_same_or_new_price_does(
    tmp_path: Path, cards: dict, campaign: dict
) -> None:
    first = normalized(cards, campaign)
    path = tmp_path / "history.json"
    assert append_records(path, [first], production=False)["appended"] == 1
    assert append_records(path, [first], production=False)["appended"] == 0
    same_later = normalized(cards, campaign, observed_at="2026-08-20T20:30:00+00:00")
    new_later = normalized(cards, campaign, observed_at="2026-08-20T20:45:00+00:00", value=90)
    result = append_records(path, [same_later, new_later], production=False)
    assert result["appended"] == 2 and result["total"] == 3


def test_future_ambiguous_and_impossible_records_rejected(cards: dict, campaign: dict) -> None:
    campaigns = {campaign["campaign_id"]: campaign}
    card_id = campaign["cards"][0]["card_id"]
    with pytest.raises(ValueError, match="future"):
        normalize_record(
            raw(card_id, campaign["campaign_id"], observed_at="2026-08-21T00:00:00+00:00"),
            cards,
            campaigns,
            ingested_at=NOW,
        )
    with pytest.raises(ValueError, match="unresolved"):
        normalize_record(
            raw("Player Name", campaign["campaign_id"]), cards, campaigns, ingested_at=NOW
        )
    with pytest.raises(ValueError, match="positive integer"):
        normalize_record(
            raw(card_id, campaign["campaign_id"], value=-1), cards, campaigns, ingested_at=NOW
        )


def test_malformed_semantics_platform_and_campaign_mismatch_rejected(
    cards: dict, campaign: dict
) -> None:
    card_id = campaign["cards"][0]["card_id"]
    campaigns = {campaign["campaign_id"]: campaign}
    with pytest.raises(ValueError, match="unsupported observation"):
        normalize_record(
            raw(card_id, campaign["campaign_id"], observation_type="GENERIC_PRICE"),
            cards,
            campaigns,
            ingested_at=NOW,
        )
    strict = {**campaign, "platform": "PLAYSTATION"}
    with pytest.raises(ValueError, match="platform mismatch"):
        normalize_record(
            raw(card_id, campaign["campaign_id"]),
            cards,
            {campaign["campaign_id"]: strict},
            ingested_at=NOW,
        )
    other = next(
        value for value in cards if value not in {row["card_id"] for row in campaign["cards"]}
    )
    with pytest.raises(ValueError, match="campaign/card mismatch"):
        normalize_record(raw(other, campaign["campaign_id"]), cards, campaigns, ingested_at=NOW)


def test_partial_failure_does_not_abort_snapshot(campaign: dict) -> None:
    card_id = campaign["cards"][0]["card_id"]
    rows = [raw(card_id, campaign["campaign_id"]), raw("unknown", campaign["campaign_id"])]
    result = run_snapshot(ROOT, rows, [campaign], {}, ingested_at=NOW, fixture=True, persist=False)
    assert result["accepted"] == 1
    assert result["partial_success"] is True
    assert len(result["failures"]) == 1


def test_last_known_record_is_not_relabelled_fresh(cards: dict, campaign: dict) -> None:
    old = normalized(cards, campaign, observed_at="2026-08-10T20:00:00+00:00")
    status = sample_sufficiency([old], NOW)
    assert old["observed_at"] == "2026-08-10T20:00:00+00:00"
    assert status["freshness_hours"] == 241.0


def test_event_t7_cannot_see_t3_and_checkpoints_calculate() -> None:
    event = register_event(
        {
            "event_id": "e",
            "event_name": "verified",
            "event_type": "SEASON TRANSITION",
            "release_time": "2026-09-01T12:00:00+00:00",
            "source": "official",
            "confidence": "HIGH",
        }
    )
    assert event["checkpoints"]["T-7"] == "2026-08-25T12:00:00+00:00"
    rows = [
        {"record_id": "t3", "card_id": "x", "price": 1, "observed_at": event["checkpoints"]["T-3"]}
    ]
    assert observations_available(rows, checkpoint_time(event["release_time"], "T-7")) == []


def test_missing_event_checkpoint_remains_missing() -> None:
    event = register_event(
        {
            "event_id": "e",
            "event_type": "PROGRAM RELEASE",
            "release_time": "2026-09-01T12:00:00+00:00",
            "source": "official",
            "confidence": "HIGH",
        }
    )
    coverage = event_checkpoint_coverage(event, [{"checkpoint": "T-7"}])
    assert coverage["observed"] == ["T-7"]
    assert "T-3" in coverage["missing"] and "T0" in coverage["missing"]


def test_event_registration_never_invents_date() -> None:
    with pytest.raises(ValueError, match="release_time"):
        register_event({"event_id": "e", "source": "official", "confidence": "HIGH"})


def test_training_basket_uses_supported_tiers_and_keeps_training_distinct() -> None:
    basket = training_basket([{"card_id": "a", "overall": 84}], "v1")
    assert basket["cards"][0]["training"] == 1160
    assert "coins" not in basket["cards"][0]
    with pytest.raises(ValueError, match="unsupported"):
        training_basket([{"card_id": "x", "overall": 99}], "v1")


def test_fixture_cannot_enter_production_recorder(
    tmp_path: Path, cards: dict, campaign: dict
) -> None:
    with pytest.raises(ValueError, match="fixture observations"):
        append_records(tmp_path / "production.json", [normalized(cards, campaign)], production=True)


def test_browser_assisted_json_and_csv_import() -> None:
    payload = [{"card_id": "x", "value": 1}]
    assert parse_browser_export(json.dumps(payload), "json") == payload
    parsed = parse_browser_export("card_id,value\nx,1\n", "csv")
    assert parsed[0]["card_id"] == "x" and parsed[0]["value"] == "1"
    with pytest.raises(ValueError, match="must be a list"):
        parse_browser_export("{}", "json")


def test_campaign_sufficiency_counts_each_semantic(cards: dict, campaign: dict) -> None:
    rows = [
        normalized(cards, campaign, observation_type="COMPLETED_SALE"),
        normalized(cards, campaign, observation_type="SUPPLY_COUNT"),
        normalized(cards, campaign, observation_type="SALE_VOLUME"),
        normalized(cards, campaign),
    ]
    status = sample_sufficiency(rows, NOW)
    assert status["sale_samples"] == 1
    assert status["listing_samples"] == 1
    assert status["supply_samples"] == 1
    assert status["volume_samples"] == 1


def test_repeated_snapshot_is_deterministic(campaign: dict) -> None:
    card_id = campaign["cards"][0]["card_id"]
    rows = [raw(card_id, campaign["campaign_id"])]
    first = run_snapshot(ROOT, rows, [campaign], {}, ingested_at=NOW, fixture=True, persist=False)
    second = run_snapshot(ROOT, rows, [campaign], {}, ingested_at=NOW, fixture=True, persist=False)
    assert first["deterministic_key"] == second["deterministic_key"]
    assert first["records"] == second["records"]


def test_alert_dedup_and_material_change_remain_intact() -> None:
    event = {
        "card_id": "x",
        "opportunity_type": "WATCH TARGET",
        "observed_price": 100,
        "threshold": 110,
        "reason": "watch",
    }
    emitted, state = reconcile_events([event], {}, NOW)
    assert len(emitted) == 1 and reconcile_events([event], state, NOW)[0] == []
    assert len(reconcile_events([{**event, "observed_price": 90}], state, NOW)[0]) == 1


def test_buy_gate_is_unchanged() -> None:
    stats = history_statistics([], NOW)
    assert calibrate_decision(stats, "VALUE", gross_cost=100, budget=100)["decision"] != "BUY"


def test_longitudinal_export_preserves_leakage_fields(cards: dict, campaign: dict) -> None:
    value = normalized(cards, campaign)
    event = {"e": {"release_time": "2026-09-01T00:00:00+00:00"}}
    value["event_id"] = "e"
    exported = longitudinal_export([value], event)[0]
    assert exported["observed_at"] == OBSERVED
    assert exported["available_at"] == OBSERVED
    assert exported["event_time"] == "2026-09-01T00:00:00+00:00"
    assert "mtime" not in exported


def test_scheduler_tracks_success_and_failure(campaign: dict) -> None:
    scheduled = {**campaign, "desired_cadence_minutes": 60}
    success = scheduler_state(scheduled, NOW, success=True)
    failure = scheduler_state(
        success, "2026-08-20T22:00:00+00:00", success=False, failure_reason="source failed"
    )
    assert success["next_due"] == "2026-08-20T22:00:00+00:00"
    assert failure["consecutive_failures"] == 1
    assert failure["last_success"] == NOW
