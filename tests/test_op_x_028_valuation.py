from __future__ import annotations

from copy import deepcopy

from operation_pancake.production.valuation import (
    percentile_of,
    population_value_curves,
    price_sensitivity,
    relative_value_classes,
    scarcity_context,
    upgrade_value,
)


def rows():
    return [
        {
            "card_id": f"c{i}",
            "position_family": "G",
            "archetype": "Power",
            "score": float(i),
            "position_rank": 11 - i,
            "score_confidence": "HIGH",
        }
        for i in range(1, 11)
    ]


def test_percentiles_and_curves_are_position_normalized():
    data = rows() + [
        {
            "card_id": "qb",
            "position_family": "QB",
            "archetype": "Pocket",
            "score": 1000.0,
            "position_rank": 1,
            "score_confidence": "HIGH",
        }
    ]
    curves = population_value_curves(data)
    assert percentile_of(5, [row["score"] for row in rows()]) == 50
    assert curves["positions"]["G"]["thresholds"]["p50"] == 5.5
    assert curves["positions"]["QB"]["thresholds"]["p50"] == 1000


def test_scarcity_and_elite_tail_geometry_are_empirical():
    data = rows()
    scarcity = scarcity_context(data[-1], data)
    curves = population_value_curves(data)
    assert scarcity["alternatives_above_candidate"] == 0
    assert scarcity["scarcity_index"] == 0.9
    assert curves["positions"]["G"]["score_distance_between_bands"]["p98_to_p99"] < 1


def test_upgrade_value_is_deterministic_confidence_adjusted_and_price_free():
    data = rows()
    curves = population_value_curves(data)
    high = upgrade_value(data[4], data[9], data, curves)
    assert high == upgrade_value(data[4], data[9], data, curves)
    assert "price" not in repr(high).lower()
    low_candidate = deepcopy(data[9])
    low_candidate["score_confidence"] = "LOW"
    low = upgrade_value(data[4], low_candidate, data, curves)
    assert low["value_index"] < high["value_index"]
    assert high["candidate_above_replacement"] > high["current_above_replacement"]


def test_price_sensitivity_is_downstream_and_monotonic():
    data = rows()
    value = upgrade_value(data[4], data[9], data, population_value_curves(data))
    curve = price_sensitivity(value, [10_000, 50_000])
    assert curve[0]["value_index_per_1000"] > curve[1]["value_index_per_1000"]
    assert (
        value["value_index"]
        == upgrade_value(data[4], data[9], data, population_value_curves(data))["value_index"]
    )


def test_relative_classes_use_only_declared_opportunity_set():
    values = [
        {"candidate": name, "value_index": value, "observed_price": 100_000}
        for name, value in zip("abcde", (50, 40, 30, 20, 10), strict=True)
    ]
    classified = relative_value_classes(values)
    assert [row["relative_valuation"] for row in classified] == [
        "STRONG VALUE",
        "VALUE",
        "FAIR",
        "PREMIUM",
        "OVERPAY",
    ]


def test_unsupported_and_incomparable_are_explicit():
    data = rows()
    curves = population_value_curves(data)
    unsupported = deepcopy(data[0])
    unsupported["score"] = None
    assert upgrade_value(unsupported, data[1], data, curves)["status"] == "UNSUPPORTED MODEL"
    other = deepcopy(data[1])
    other["position_family"] = "QB"
    assert upgrade_value(data[0], other, data, curves)["status"] == "INCOMPARABLE"
