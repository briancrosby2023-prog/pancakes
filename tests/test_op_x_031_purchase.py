from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from operation_pancake.production.market_campaign import enrich_observation
from operation_pancake.production.purchase import (
    PurchaseIntelligence,
    detect_decision_change,
    empirical_upgrade_tier,
)

ROOT = Path(__file__).resolve().parents[1]
CARD_IDS = {
    "Anthony Donkoh": "card:05b737e0828809d8a979",
    "Brendan Black": "card:f35e84cba0d56c4270c3",
    "Bray Hubbard": "card:f26cd7a4829a431b0af5",
    "Cormani McClain": "card:2a79a6e3f272a16ec712",
    "Dashawn Spears": "card:4595176827b3dc5e510c",
    "E'Marion Harris": "card:4bd7645117856f967450",
    "Kobe Black": "card:7084891b08e603666bea",
    "Samson Okunlola": "card:0dfef086dfd8d85794d6",
}


@pytest.fixture(scope="module")
def purchase():
    return PurchaseIntelligence(ROOT)


def ids(purchase, current, candidate):
    left, right = CARD_IDS[current], CARD_IDS[candidate]
    ranked_ids = {row["card_id"] for row in purchase.gm.ranked}
    assert {left, right} <= ranked_ids
    return left, right


def test_purchase_object_complete_deterministic_and_market_safe(purchase):
    left, right = ids(purchase, "Anthony Donkoh", "Brendan Black")
    report = purchase.report(left, right)
    assert report == purchase.report(left, right)
    assert {
        "football",
        "why",
        "roster",
        "intrinsic_value",
        "alternatives",
        "market",
        "cost",
        "moneyball",
        "decision",
    } <= report.keys()
    assert report["decision"]["gm_action"] == "PRICE CHECK REQUIRED"
    assert report["market"]["evidence_quality"] == "CONTEXT_ONLY"
    assert report["cost"]["net_upgrade_cost"] is None


def test_decision_hierarchy_identity_unsupported_and_non_upgrade(purchase):
    assert purchase.report("bad", "worse")["decision"]["gm_action"] == "UNRESOLVED IDENTITY"
    unsupported = next(
        row["card_id"] for row in purchase.attributes.scored_all if row["score"] is None
    )
    valid = purchase.gm.ranked[0]["card_id"]
    assert purchase.report(unsupported, valid)["decision"]["gm_action"] == "UNSUPPORTED MODEL"
    family = purchase.gm.ranked[0]["position_family"]
    peers = [row for row in purchase.gm.ranked if row["position_family"] == family]
    assert (
        purchase.report(peers[0]["card_id"], peers[-1]["card_id"])["decision"]["gm_action"]
        == "KEEP"
    )


def test_empirical_upgrade_tiers_are_distribution_derived():
    reference = [{"score_gain": i, "rank_gain": i} for i in range(1, 11)]
    assert empirical_upgrade_tier(1, 1, reference)["tier"] == "MARGINAL"
    assert empirical_upgrade_tier(10, 10, reference)["tier"] == "TRANSFORMATIVE"


def test_alternative_challenge_and_target_premium(purchase):
    left, right = ids(purchase, "Dashawn Spears", "Bray Hubbard")
    report = purchase.report(left, right)
    best = report["alternatives"]["best_near_equivalent"]
    assert best["player_name"] == "Gerod Holliman"
    assert "target_attribute_advantages" in best and "market_evidence" in best
    premium = report["alternatives"]["target_premium"]
    assert premium["score_premium"] == 0.019231
    assert report["alternatives"]["target_premium"]["price_premium"] is None


def test_attribute_and_market_stories_are_separate(purchase):
    left, right = ids(purchase, "Cormani McClain", "Kobe Black")
    report = purchase.report(left, right)
    assert len(report["why"]["primary_attribute_drivers"]) <= 3
    assert report["market"]["latest_price"] == 4_360_000
    assert report["intrinsic_value"]["relative_valuation_class"] == "OVERPAY"
    assert "market" not in repr(report["why"]).lower()


def test_render_is_concise_and_unknown_fields_remain_unknown(purchase):
    left, right = ids(purchase, "Anthony Donkoh", "Brendan Black")
    report = purchase.report(left, right)
    text = purchase.render(report)
    assert "PANCAKE GM - PURCHASE REPORT" in text and "PRICE CHECK REQUIRED" in text
    assert report["cost"]["resale_value"] is None
    assert len(text.splitlines()) <= 15


def test_moneyball_quality_and_efficiency_rankings_use_distinct_metrics(purchase):
    reports = [
        purchase.report(*ids(purchase, "Dashawn Spears", "Bray Hubbard")),
        purchase.report(*ids(purchase, "Samson Okunlola", "E'Marion Harris")),
    ]
    quality = sorted(reports, key=lambda row: -row["football"]["score_gain"])
    contextual_efficiency = sorted(
        reports,
        key=lambda row: -(row["football"]["score_gain"] * 1000 / row["cost"]["candidate_price"]),
    )
    assert quality[0]["candidate"]["player_name"] == "Bray Hubbard"
    assert contextual_efficiency[0]["candidate"]["player_name"] == "E'Marion Harris"


def test_budget_integration_and_keep_coins(purchase):
    pairs = [
        ids(purchase, "Anthony Donkoh", "Brendan Black"),
        ids(purchase, "Samson Okunlola", "E'Marion Harris"),
    ]
    reports = [purchase.report(*pair) for pair in pairs]
    assert purchase.optimize_reports(reports, 50_000)["keep_coins"] is True
    selected = purchase.optimize_reports(reports, 200_000)
    assert selected["selected"] and selected["rank_gain"] > 0


def test_change_detection_ignores_timestamp_only_changes(purchase):
    left, right = ids(purchase, "Anthony Donkoh", "Brendan Black")
    previous = purchase.report(left, right)
    timestamp_only = deepcopy(previous)
    timestamp_only["market"]["observation_age_hours"] = 2
    assert detect_decision_change(previous, timestamp_only) is None
    changed = deepcopy(previous)
    changed["decision"]["gm_action"] = "WAIT"
    assert detect_decision_change(previous, changed)["new_action"] == "WAIT"


def test_observation_refresh_changes_report_without_fixture_contamination(purchase):
    left, right = ids(purchase, "Anthony Donkoh", "Brendan Black")
    previous = purchase.report(left, right)
    card = purchase.gm.cards[right]
    purchase.history_by_card[right] = [
        enrich_observation(
            card,
            price,
            "DISPLAYED_MARKET_PRICE",
            observed_at=timestamp,
            ingested_at=timestamp,
        )
        for price, timestamp in (
            (55_000, "2026-08-20T00:00:00-07:00"),
            (56_000, "2026-08-20T12:00:00-07:00"),
            (54_000, "2026-08-21T00:00:00-07:00"),
            (55_000, "2026-08-21T12:00:00-07:00"),
        )
    ]
    refreshed = purchase.report(left, right, as_of="2026-08-21T13:00:00-07:00")
    assert refreshed["market"]["evidence_quality"] == "USABLE"
    assert refreshed["decision"]["gm_action"] == "WAIT"
    assert detect_decision_change(previous, refreshed)["new_action"] == "WAIT"
    purchase.history_by_card.pop(right)


def test_shopping_board_and_evidence_optimization(purchase):
    board = purchase.shopping_board()
    assert board and all("gm_action" in row and "best_alternative" in row for row in board)
    five = [purchase.report(current, candidate) for current, candidate in purchase.valuations]
    priority = purchase.evidence_priority(five)
    assert priority[0]["candidate"] == "Brendan Black"
