from __future__ import annotations

import json
from pathlib import Path

from operation_pancake.production.discovery import DiscoveryIntelligence, build_discovery

ROOT = Path(__file__).resolve().parents[1]


def test_discovery_covers_only_scored_population_and_is_price_independent() -> None:
    methodology = json.loads(
        (ROOT / "data/research/op_x_034/discovery_methodology.json").read_text()
    )
    cards = json.loads((ROOT / "data/research/op_x_034/football_value_index.json").read_text())[
        "cards"
    ]
    assert len(cards) == 8184
    assert methodology["price_independent"] is True
    assert methodology["cross_position_raw_score_comparison"] is False
    assert all(row["market_status"] == "PRICE CHECK REQUIRED" for row in cards)


def test_weights_are_bounded_and_sum_to_one() -> None:
    methodology = json.loads(
        (ROOT / "data/research/op_x_034/discovery_methodology.json").read_text()
    )
    weights = methodology["football_value_index_weights"]
    assert sum(weights.values()) == 1
    assert max(weights.values()) <= 0.25


def test_tiers_are_empirical_exhaustive_and_ordered() -> None:
    tiers = json.loads((ROOT / "data/research/op_x_034/discovery_tiers.json").read_text())
    assert sum(tiers["counts"].values()) == 8184
    assert tiers["empirical"] is True
    thresholds = tiers["thresholds"]
    assert thresholds["INTERESTING"] < thresholds["STRONG"] < thresholds["ELITE"]
    assert thresholds["ELITE"] < thresholds["EXTREME"]


def test_network_discloses_profile_difference_and_unsupported_is_safe() -> None:
    service = DiscoveryIntelligence(ROOT)
    scenario = json.loads((ROOT / "data/research/op_x_034/acceptance_scenarios.json").read_text())
    differing = scenario["material_profile_disclosure"]
    assert differing["profile_disclosure_required"] is True
    unsupported = scenario["unsupported_preserved"]
    assert unsupported["routing"]["status"] == "UNSUPPORTED"
    assert service.alternatives(unsupported["card_id"])["target"] is None


def test_partial_evidence_and_price_absence_are_explicit() -> None:
    scenario = json.loads((ROOT / "data/research/op_x_034/acceptance_scenarios.json").read_text())
    assert scenario["partial_disclosed"]["score_confidence"] == "LOW"
    assert scenario["price_absence"] == "PRICE CHECK REQUIRED"


def test_discovery_queries_are_position_and_ovr_bounded() -> None:
    service = DiscoveryIntelligence(ROOT)
    rows = service.discover("CB", 82, 10)
    assert len(rows) == 10
    assert all(row["position_family"] == "CB" and row["overall"] <= 82 for row in rows)


def test_build_is_deterministic_for_selected_outputs() -> None:
    first = build_discovery(ROOT)
    second = build_discovery(ROOT)
    assert first["thresholds"] == second["thresholds"]
    assert first["position_boards"] == second["position_boards"]
    assert first["cells"] == second["cells"]
