from __future__ import annotations

from collections import Counter
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest

from operation_pancake.production.attributes import AttributeIntelligence
from operation_pancake.production.gm import optimize_budget
from operation_pancake.production.market_campaign import (
    enrich_observation,
    evidence_quality,
)

ROOT = Path(__file__).resolve().parents[1]


def test_e15_parse_module_imports_without_optional_requests():
    path = ROOT / "scripts/e15_historical_te_population_validation_v2.py"
    spec = spec_from_file_location("e15_lazy_dependency", path)
    module = module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    assert callable(module.parse)


def test_alternative_search_discloses_profile_and_evidence_differences():
    intelligence = AttributeIntelligence(ROOT)
    target = next(
        row["card_id"]
        for row in intelligence.ranked
        if row["player_name"] == "Bray Hubbard" and row["position_rank"] == 1
    )
    alternative = intelligence.alternatives(target, 0.25)[0]
    assert alternative["player_name"] == "Jay Green"
    assert {
        "score_confidence",
        "attribute_coverage",
        "different_archetype",
        "profile_challenges",
    } <= alternative.keys()
    assert "DIFFERENT ARCHETYPE" in alternative["profile_challenges"]


@pytest.mark.parametrize("price", [0, -1, 1.5, True, "100"])
def test_adversarial_market_prices_fail_closed(price):
    card = {"card_id": "card:test", "player_name": "Test"}
    with pytest.raises((TypeError, ValueError)):
        enrich_observation(card, price, "VISIBLE_LISTING")


def test_future_and_conflicting_evidence_cannot_be_strong():
    semantics = Counter({"VISIBLE_LISTING": 8})
    assert evidence_quality(8, 8, 72, -1, 0.01, True, semantics) == "INSUFFICIENT"
    assert evidence_quality(8, 8, 72, 1, 0.8, True, semantics) == "USABLE"


def test_optimizer_scale_invariants_protected_assets_and_ties():
    candidates = [
        {"card_id": f"c{i:02d}", "net_cost": 10 + i, "score_improvement": 1 + i / 10}
        for i in range(30)
    ]
    candidates.append(
        {"card_id": "protected", "net_cost": 1, "score_improvement": 100, "protected": True}
    )
    first = optimize_budget(candidates, 300)
    second = optimize_budget(candidates, 300)
    assert first == second
    assert first["spent"] <= 300
    assert all(row["card_id"] != "protected" for row in first["selected"])
    tie = optimize_budget(
        [
            {"card_id": "a", "net_cost": 50, "score_improvement": 2},
            {"card_id": "b", "net_cost": 50, "score_improvement": 2},
        ],
        50,
    )
    assert tie["selected"][0]["card_id"] == "a"
