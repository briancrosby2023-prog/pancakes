from __future__ import annotations

from pathlib import Path

import pytest

from operation_pancake.production.attributes import (
    AttributeIntelligence,
    population_attribute_stats,
)

ROOT = Path(__file__).resolve().parents[1]
CARD_IDS = {
    "Anthony Donkoh": "card:05b737e0828809d8a979",
    "Brendan Black": "card:f35e84cba0d56c4270c3",
}


@pytest.fixture(scope="module")
def intelligence():
    return AttributeIntelligence(ROOT)


def target(intelligence, name):
    card_id = CARD_IDS[name]
    assert any(row["card_id"] == card_id for row in intelligence.ranked)
    return card_id


def test_contributions_reconcile_and_are_deterministic(intelligence):
    card_id = target(intelligence, "Brendan Black")
    first = intelligence.contribution(card_id)
    assert abs(first["reconciliation_error"]) < 1e-6
    assert first == intelligence.contribution(card_id)
    assert all(row["marginal_pancake_value"]["1"] > 0 for row in first["contributions"])


def test_attribute_percentile_scarcity_and_position_normalization(intelligence):
    guard = intelligence.contribution(target(intelligence, "Brendan Black"))
    assert all(0 <= row["attribute_percentile"] <= 100 for row in guard["contributions"])
    assert all(
        row["peer_count"] > 0 and row["count_at_or_above"] > 0 for row in guard["contributions"]
    )
    assert guard["position_family"] == "G"


def test_comparison_reconciles_positive_and_negative_tradeoffs(intelligence):
    current = target(intelligence, "Anthony Donkoh")
    candidate = target(intelligence, "Brendan Black")
    result = intelligence.compare(current, candidate)
    assert result["status"] == "DECOMPOSED"
    assert abs(result["reconciliation_error"]) < 1e-6
    assert any(row["score_contribution_change"] > 0 for row in result["attributes"])


def test_near_equivalents_and_attribute_upgrade_search(intelligence):
    card_id = target(intelligence, "Anthony Donkoh")
    assert intelligence.alternatives(card_id, 1.0)
    upgrades = intelligence.attribute_upgrades(card_id, "RBK", min_score_gain=1)
    assert upgrades and all(row["attribute_gain"] > 0 for row in upgrades)


def test_partial_unsupported_and_diagnostic_states_are_explicit(intelligence):
    incomplete = next(row for row in intelligence.scored_all if row["score"] is None)
    result = intelligence.contribution(incomplete["card_id"])
    assert result["status"] in {"INSUFFICIENT_ATTRIBUTES", "UNSUPPORTED", "DIAGNOSTIC_ONLY"}
    diagnostic = next(
        row for row in intelligence.scored_all if row["routing"]["status"] == "DIAGNOSTIC_ONLY"
    )
    assert intelligence.contribution(diagnostic["card_id"])["status"] == "DIAGNOSTIC_ONLY"


def test_population_differentiation_uses_frozen_effective_coefficients(intelligence):
    stats = population_attribute_stats(intelligence)
    assert stats
    assert all(row["differentiation_index"] >= 0 for row in stats.values())
    assert all("effective_coefficient" in row for row in stats.values())
