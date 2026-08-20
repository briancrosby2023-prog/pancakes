"""Attribute explanations derived only from frozen production ranking models."""

from __future__ import annotations

import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any

from .engine import ProductionEngine, load_population
from .registry import build_model_registry
from .valuation import percentile_of


def _quantile(values: list[float], percentile: float) -> float:
    ordered = sorted(values)
    location = (len(ordered) - 1) * percentile / 100
    lower = int(location)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = location - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def effective_terms(
    card: dict[str, Any], scored: dict[str, Any], model: dict[str, Any]
) -> dict[str, float]:
    """Return score-space coefficients after coverage-aware denominators."""
    ratings = card.get("native_ratings") or {}
    profile = scored["routing"]["profile"]
    if profile != "Blend":
        weights = model["profiles"][profile]
        denominator = sum(
            weight for attribute, weight in weights.items() if ratings.get(attribute) is not None
        )
        return (
            {}
            if not denominator
            else {
                attribute: weight / denominator
                for attribute, weight in weights.items()
                if ratings.get(attribute) is not None
            }
        )
    terms: dict[str, float] = defaultdict(float)
    for profile_name, blend_weight in (("Vertical Threat", 0.71), ("Possession", 0.29)):
        weights = model["profiles"][profile_name]
        denominator = sum(
            weight for attribute, weight in weights.items() if ratings.get(attribute) is not None
        )
        if not denominator:
            continue
        for attribute, weight in weights.items():
            if ratings.get(attribute) is not None:
                terms[attribute] += blend_weight * weight / denominator
    return dict(terms)


class AttributeIntelligence:
    """Fast explanation API over the canonical scored CFB27 population."""

    def __init__(self, root: Path):
        self.root = root
        self.registry = build_model_registry(root)
        self.models = {(row["id"], row["version"]): row for row in self.registry["models"]}
        self.engine = ProductionEngine(self.registry)
        self.population = load_population(root)
        self.cards = {row["card_id"]: row for row in self.population}
        self.scored_all = [self.engine.score(card) for card in self.population]
        self.ranked = self.engine.rank(self.scored_all)
        self.scored = {row["card_id"]: row for row in self.ranked}
        self.groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
        for row in self.ranked:
            self.groups[(row["position_family"], row["archetype"])].append(row)

    def contribution(self, card_id: str) -> dict[str, Any]:
        if card_id not in self.cards:
            return {"status": "UNRESOLVED IDENTITY"}
        raw_score = self.engine.score(self.cards[card_id])
        if raw_score["routing"]["status"] != "ROUTED":
            return {"status": raw_score["routing"]["status"], "contributions": []}
        if raw_score["score"] is None:
            return {
                "status": raw_score["score_status"],
                "coverage": raw_score["attribute_coverage"],
                "missing_evidence": True,
                "contributions": [],
            }
        model = self.models[(raw_score["pancake_model_id"], raw_score["pancake_model_version"])]
        terms = effective_terms(self.cards[card_id], raw_score, model)
        ratings = self.cards[card_id]["native_ratings"]
        peers = self.groups[(raw_score["position_family"], raw_score["archetype"])]
        contributions = []
        for attribute, coefficient in terms.items():
            values = [self.cards[row["card_id"]]["native_ratings"].get(attribute) for row in peers]
            values = [float(value) for value in values if value is not None]
            rating = float(ratings[attribute])
            percentile = percentile_of(rating, values)
            label = (
                "ELITE MODEL STRENGTH"
                if percentile >= 98
                else "STRONG"
                if percentile >= 90
                else "MAJOR DEFICIENCY"
                if percentile < 10
                else "WEAK"
                if percentile < 25
                else "AVERAGE"
            )
            at_or_above = sum(value >= rating for value in values)
            contribution = rating * coefficient
            contributions.append(
                {
                    "attribute": attribute,
                    "raw_rating": rating,
                    "effective_coefficient": coefficient,
                    "weighted_contribution": round(contribution, 9),
                    "score_share_percent": round(100 * contribution / raw_score["score"], 6),
                    "attribute_percentile": percentile,
                    "strength_class": label,
                    "peer_count": len(values),
                    "count_at_or_above": at_or_above,
                    "elite_tail_scarcity": round(1 - at_or_above / len(values), 6),
                    "local_density_within_one": sum(abs(value - rating) <= 1 for value in values),
                    "marginal_pancake_value": {
                        str(delta): round(coefficient * delta, 9) for delta in (1, 2, 3, 5)
                    },
                    "availability": "AVAILABLE",
                    "confidence": raw_score["score_confidence"],
                }
            )
        contributions.sort(key=lambda row: (-row["weighted_contribution"], row["attribute"]))
        reconciled = sum(row["weighted_contribution"] for row in contributions)
        return {
            "status": "EXPLAINED",
            "card_id": card_id,
            "player_name": raw_score["player_name"],
            "position_family": raw_score["position_family"],
            "archetype": raw_score["archetype"],
            "model_profile": raw_score["routing"]["profile"],
            "score": raw_score["score"],
            "coverage": raw_score["attribute_coverage"],
            "confidence": raw_score["score_confidence"],
            "contribution_sum": round(reconciled, 6),
            "reconciliation_error": round(reconciled - raw_score["score"], 9),
            "contributions": contributions,
            "scientific_scope": (
                "contribution to validated Pancake ranking model; not gameplay value"
            ),
        }

    def compare(self, current_id: str, candidate_id: str) -> dict[str, Any]:
        left, right = self.contribution(current_id), self.contribution(candidate_id)
        if left.get("status") != "EXPLAINED" or right.get("status") != "EXPLAINED":
            return {"status": "UNSUPPORTED OR INCOMPLETE", "current": left, "candidate": right}
        if left["position_family"] != right["position_family"]:
            return {"status": "INCOMPARABLE", "reason": "different position families"}
        left_map = {row["attribute"]: row for row in left["contributions"]}
        right_map = {row["attribute"]: row for row in right["contributions"]}
        attributes = []
        raw_left = self.cards[current_id]["native_ratings"]
        raw_right = self.cards[candidate_id]["native_ratings"]
        for attribute in sorted(set(left_map) | set(right_map)):
            before = left_map.get(attribute, {}).get("weighted_contribution", 0)
            after = right_map.get(attribute, {}).get("weighted_contribution", 0)
            change = after - before
            attributes.append(
                {
                    "attribute": attribute,
                    "current_rating": raw_left.get(attribute),
                    "candidate_rating": raw_right.get(attribute),
                    "rating_delta": None
                    if raw_left.get(attribute) is None or raw_right.get(attribute) is None
                    else raw_right[attribute] - raw_left[attribute],
                    "score_contribution_change": round(change, 9),
                    "current_effective_coefficient": left_map.get(attribute, {}).get(
                        "effective_coefficient", 0
                    ),
                    "candidate_effective_coefficient": right_map.get(attribute, {}).get(
                        "effective_coefficient", 0
                    ),
                    "current_attribute_percentile": left_map.get(attribute, {}).get(
                        "attribute_percentile"
                    ),
                    "candidate_attribute_percentile": right_map.get(attribute, {}).get(
                        "attribute_percentile"
                    ),
                    "candidate_count_at_or_above": right_map.get(attribute, {}).get(
                        "count_at_or_above"
                    ),
                }
            )
        score_delta = right["score"] - left["score"]
        for row in attributes:
            row["share_of_total_improvement_percent"] = (
                None
                if score_delta == 0
                else round(100 * row["score_contribution_change"] / score_delta, 6)
            )
        gains = sorted(
            (row for row in attributes if row["score_contribution_change"] > 0),
            key=lambda row: -row["score_contribution_change"],
        )
        primary_attributes = {row["attribute"] for row in gains[:3]}
        for row in attributes:
            row["role"] = (
                "PRIMARY UPGRADE DRIVER"
                if row["attribute"] in primary_attributes
                else "SECONDARY GAIN"
                if row["score_contribution_change"] > 0
                else "LOSS/OFFSET"
                if row["score_contribution_change"] < 0
                else "NEUTRAL"
            )
        raw_changed = set(raw_left) | set(raw_right)
        modeled = set(left_map) | set(right_map)
        inflation = [
            {
                "attribute": attribute,
                "rating_delta": raw_right.get(attribute, 0) - raw_left.get(attribute, 0),
            }
            for attribute in sorted(raw_changed - modeled)
            if raw_right.get(attribute) is not None
            and raw_left.get(attribute) is not None
            and raw_right[attribute] > raw_left[attribute]
        ]
        return {
            "status": "DECOMPOSED",
            "current": left["player_name"],
            "candidate": right["player_name"],
            "score_delta": round(score_delta, 6),
            "contribution_delta_sum": round(
                sum(row["score_contribution_change"] for row in attributes), 6
            ),
            "reconciliation_error": round(
                sum(row["score_contribution_change"] for row in attributes) - score_delta, 9
            ),
            "top_three_gain_share_percent": None
            if score_delta <= 0
            else round(
                100 * sum(row["score_contribution_change"] for row in gains[:3]) / score_delta, 6
            ),
            "improvement_shape": "CONCENTRATED"
            if score_delta > 0
            and sum(row["score_contribution_change"] for row in gains[:3]) / score_delta >= 0.8
            else "BROAD",
            "attributes": attributes,
            "low_model_value_inflation": inflation,
            "model_profile_changed": left["model_profile"] != right["model_profile"],
            "coverage_changed": left["coverage"] != right["coverage"],
            "decomposition_caveat": (
                "profile or coverage changes reallocate normalized contribution; "
                "a positive contribution change need not imply a positive raw-rating delta"
            ),
        }

    def alternatives(
        self, card_id: str, tolerance: float = 0.5, limit: int = 10
    ) -> list[dict[str, Any]]:
        target = self.scored.get(card_id)
        if target is None:
            return []
        rows = [
            row
            for row in self.ranked
            if row["position_family"] == target["position_family"]
            and row["card_id"] != card_id
            and abs(row["score"] - target["score"]) <= tolerance
        ]
        rows.sort(key=lambda row: (abs(row["score"] - target["score"]), row["position_rank"]))
        return [
            {
                "card_id": row["card_id"],
                "player_name": row["player_name"],
                "overall": row["native_overall"],
                "archetype": row["archetype"],
                "score_difference": round(row["score"] - target["score"], 6),
                "rank_difference": row["position_rank"] - target["position_rank"],
                "score_confidence": row["score_confidence"],
                "attribute_coverage": row["attribute_coverage"],
                "different_archetype": row["archetype"] != target["archetype"],
                "profile_challenges": [
                    label
                    for condition, label in (
                        (row["archetype"] != target["archetype"], "DIFFERENT ARCHETYPE"),
                        (
                            row["score_confidence"] != target["score_confidence"],
                            "DIFFERENT SCORE CONFIDENCE",
                        ),
                        (
                            abs(row["attribute_coverage"] - target["attribute_coverage"]) > 0.1,
                            "MATERIAL COVERAGE DIFFERENCE",
                        ),
                    )
                    if condition
                ],
            }
            for row in rows[:limit]
        ]

    def attribute_upgrades(
        self, card_id: str, attribute: str | None = None, min_score_gain: float = 0, limit: int = 10
    ) -> list[dict[str, Any]]:
        target = self.scored.get(card_id)
        if target is None:
            return []
        current_ratings = self.cards[card_id]["native_ratings"]
        candidates = []
        for row in self.ranked:
            if (
                row["position_family"] != target["position_family"]
                or row["score"] - target["score"] < min_score_gain
            ):
                continue
            delta = (
                None
                if attribute is None
                else self.cards[row["card_id"]]["native_ratings"].get(attribute, -1)
                - current_ratings.get(attribute, -1)
            )
            if attribute is not None and delta <= 0:
                continue
            candidates.append(
                {
                    "card_id": row["card_id"],
                    "player_name": row["player_name"],
                    "score_gain": round(row["score"] - target["score"], 6),
                    "attribute": attribute,
                    "attribute_gain": delta,
                }
            )
        candidates.sort(
            key=lambda row: (-(row["attribute_gain"] or 0), -row["score_gain"], row["card_id"])
        )
        return candidates[:limit]


def population_attribute_stats(intelligence: AttributeIntelligence) -> dict[str, Any]:
    values: dict[tuple[str, str, str], list[tuple[float, float]]] = defaultdict(list)
    for row in intelligence.ranked:
        explanation = intelligence.contribution(row["card_id"])
        for item in explanation["contributions"]:
            values[(row["position_family"], row["archetype"], item["attribute"])].append(
                (item["raw_rating"], item["effective_coefficient"])
            )
    output = {}
    for (family, archetype, attribute), pairs in sorted(values.items()):
        ratings = [pair[0] for pair in pairs]
        weight = statistics.mean(pair[1] for pair in pairs)
        stddev = statistics.pstdev(ratings)
        output[f"{family}|{archetype}|{attribute}"] = {
            "n": len(ratings),
            "mean": round(statistics.mean(ratings), 6),
            "stddev": round(stddev, 6),
            "p90": round(_quantile(ratings, 90), 6),
            "p95": round(_quantile(ratings, 95), 6),
            "p98": round(_quantile(ratings, 98), 6),
            "effective_coefficient": round(weight, 9),
            "differentiation_index": round(weight * stddev, 9),
        }
    return output
