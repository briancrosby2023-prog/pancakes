"""Position-normalized intrinsic player and upgrade valuation.

Market price is deliberately absent from intrinsic value calculations. Coin inputs
are accepted only by the separate price-sensitivity and relative-classification
functions.
"""

from __future__ import annotations

from bisect import bisect_right
from collections import defaultdict
from typing import Any, Iterable

PERCENTILE_BANDS = (50, 75, 90, 95, 98, 99)
PRICE_GRID = (
    10_000,
    25_000,
    50_000,
    75_000,
    100_000,
    150_000,
    250_000,
    500_000,
    750_000,
    1_000_000,
    2_000_000,
    5_000_000,
)
VALUE_INDEX_WEIGHTS = {
    "score_gain": 0.25,
    "percentile_gain": 0.25,
    "rank_gain": 0.15,
    "scarcity": 0.15,
    "roster_need": 0.20,
}
CONFIDENCE_FACTORS = {"HIGH": 1.0, "MEDIUM": 0.85, "LOW": 0.65}


def _quantile(values: list[float], percentile: float) -> float:
    if not values:
        raise ValueError("cannot calculate a quantile for an empty population")
    ordered = sorted(values)
    location = (len(ordered) - 1) * percentile / 100
    lower = int(location)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = location - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def percentile_of(score: float, scores: Iterable[float]) -> float:
    """Return an empirical within-group percentile including ties at their upper edge."""
    ordered = sorted(scores)
    if not ordered:
        raise ValueError("scores cannot be empty")
    return round(100 * bisect_right(ordered, score) / len(ordered), 6)


def population_value_curves(ranked: list[dict[str, Any]]) -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    archetypes: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in ranked:
        if row.get("score") is None:
            continue
        groups[row["position_family"]].append(row)
        archetypes[(row["position_family"], row["archetype"])].append(row)

    def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
        scores = [float(row["score"]) for row in rows]
        thresholds = {f"p{p}": round(_quantile(scores, p), 6) for p in PERCENTILE_BANDS}
        transitions = {}
        for left, right in zip(PERCENTILE_BANDS, PERCENTILE_BANDS[1:], strict=False):
            transitions[f"p{left}_to_p{right}"] = round(
                thresholds[f"p{right}"] - thresholds[f"p{left}"], 6
            )
        return {
            "population_size": len(rows),
            "replacement_level": thresholds["p50"],
            "starter_quality": {"p75": thresholds["p75"], "p90": thresholds["p90"]},
            "elite": {key: thresholds[key] for key in ("p90", "p95", "p98", "p99")},
            "thresholds": thresholds,
            "score_distance_between_bands": transitions,
        }

    return {
        "method": "empirical linear-interpolated score quantiles within production position family",
        "positions": {family: summarize(rows) for family, rows in sorted(groups.items())},
        "archetypes": {
            f"{family}|{archetype}": summarize(rows)
            for (family, archetype), rows in sorted(archetypes.items())
        },
    }


def scarcity_context(candidate: dict[str, Any], ranked: list[dict[str, Any]]) -> dict[str, Any]:
    peers = [
        row
        for row in ranked
        if row["position_family"] == candidate["position_family"] and row.get("score") is not None
    ]
    role_peers = [row for row in peers if row["archetype"] == candidate["archetype"]]
    score = float(candidate["score"])
    above = sorted((float(row["score"]) for row in peers if row["score"] > score))
    below = sorted((float(row["score"]) for row in peers if row["score"] < score), reverse=True)
    comparable = [row for row in peers if abs(float(row["score"]) - score) <= 0.5]
    role_above = [row for row in role_peers if row["score"] > score]
    tail_percentile = percentile_of(score, [float(row["score"]) for row in peers])
    scarcity_index = 1 - len(comparable) / len(peers)
    return {
        "position_family": candidate["position_family"],
        "archetype": candidate["archetype"],
        "population_size": len(peers),
        "archetype_population_size": len(role_peers),
        "alternatives_above_candidate": len(above),
        "archetype_alternatives_above_candidate": len(role_above),
        "comparable_cards_within_half_score": len(comparable),
        "distance_to_next_better": None if not above else round(above[0] - score, 6),
        "distance_to_next_lower": None if not below else round(score - below[0], 6),
        "elite_tail_percentile": tail_percentile,
        "scarcity_index": round(scarcity_index, 6),
    }


def upgrade_value(
    current: dict[str, Any],
    candidate: dict[str, Any],
    ranked: list[dict[str, Any]],
    curves: dict[str, Any],
) -> dict[str, Any]:
    if current.get("score") is None or candidate.get("score") is None:
        return {"status": "UNSUPPORTED MODEL", "value_index": None}
    if current["position_family"] != candidate["position_family"]:
        return {"status": "INCOMPARABLE", "value_index": None}
    family = current["position_family"]
    peers = [float(row["score"]) for row in ranked if row["position_family"] == family]
    current_percentile = percentile_of(float(current["score"]), peers)
    candidate_percentile = percentile_of(float(candidate["score"]), peers)
    score_gain = float(candidate["score"]) - float(current["score"])
    rank_gain = int(current["position_rank"]) - int(candidate["position_rank"])
    position = curves["positions"][family]
    score_span = max(position["thresholds"]["p90"] - position["thresholds"]["p50"], 0.000001)
    scarcity = scarcity_context(candidate, ranked)
    components = {
        "score_gain": max(0.0, min(1.0, score_gain / score_span)),
        "percentile_gain": max(0.0, min(1.0, (candidate_percentile - current_percentile) / 25)),
        "rank_gain": max(0.0, min(1.0, rank_gain / len(peers))),
        "scarcity": scarcity["scarcity_index"],
        "roster_need": max(0.0, min(1.0, (100 - current_percentile) / 25)),
    }
    confidence = candidate.get("score_confidence", "LOW")
    confidence_factor = CONFIDENCE_FACTORS.get(confidence, 0.5)
    unadjusted = 100 * sum(VALUE_INDEX_WEIGHTS[key] * components[key] for key in components)
    value_index = unadjusted * confidence_factor
    elite = position["thresholds"]["p95"]
    replacement = position["replacement_level"]
    return {
        "status": "VALUED",
        "position_family": family,
        "score_gain": round(score_gain, 6),
        "score_gain_percent": round(100 * score_gain / float(current["score"]), 6),
        "current_percentile": current_percentile,
        "candidate_percentile": candidate_percentile,
        "percentile_gain": round(candidate_percentile - current_percentile, 6),
        "rank_gain": rank_gain,
        "replacement_level_score": replacement,
        "current_above_replacement": round(float(current["score"]) - replacement, 6),
        "candidate_above_replacement": round(float(candidate["score"]) - replacement, 6),
        "distance_toward_elite": round(
            min(float(candidate["score"]), elite) - min(float(current["score"]), elite), 6
        ),
        "scarcity": scarcity,
        "roster_need": round(components["roster_need"], 6),
        "confidence": confidence,
        "confidence_factor": confidence_factor,
        "value_index_components": {key: round(value, 6) for key, value in components.items()},
        "value_index_unadjusted": round(unadjusted, 6),
        "value_index": round(value_index, 6),
    }


def price_sensitivity(
    value: dict[str, Any], prices: Iterable[int] = PRICE_GRID
) -> list[dict[str, Any]]:
    if value.get("status") != "VALUED":
        return []
    return [
        {
            "net_cost": price,
            "score_gain_per_1000": round(value["score_gain"] * 1000 / price, 8),
            "rank_gain_per_1000": round(value["rank_gain"] * 1000 / price, 8),
            "percentile_gain_per_1000": round(value["percentile_gain"] * 1000 / price, 8),
            "value_index_per_1000": round(value["value_index"] * 1000 / price, 8),
        }
        for price in prices
        if price > 0
    ]


def relative_value_classes(values: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Assign contextual quintiles by value-index efficiency within a declared set."""
    eligible = [
        row for row in values if row.get("observed_price", 0) > 0 and row.get("value_index")
    ]
    ordered = sorted(
        eligible,
        key=lambda row: (row["value_index"] * 1000 / row["observed_price"], row["candidate"]),
        reverse=True,
    )
    labels = ("STRONG VALUE", "VALUE", "FAIR", "PREMIUM", "OVERPAY")
    output = []
    for index, row in enumerate(ordered):
        bucket = min(len(labels) - 1, index * len(labels) // len(ordered))
        output.append(
            {
                **row,
                "value_index_per_1000": round(row["value_index"] * 1000 / row["observed_price"], 8),
                "relative_valuation": labels[bucket],
                "classification_scope": "contextual quintile within supplied opportunity set",
            }
        )
    return output
