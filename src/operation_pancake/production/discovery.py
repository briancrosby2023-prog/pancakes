"""Price-independent player discovery over frozen production ranking scores."""

from __future__ import annotations

import bisect
import json
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any

from .engine import load_population
from .registry import build_model_registry


def _percentile(value: float, values: list[float]) -> float:
    ordered = sorted(values)
    return round(100 * bisect.bisect_right(ordered, value) / len(ordered), 6)


def _quantile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    index = (len(ordered) - 1) * fraction
    low = int(index)
    high = min(low + 1, len(ordered) - 1)
    return ordered[low] + (ordered[high] - ordered[low]) * (index - low)


def build_discovery(root: Path) -> dict[str, Any]:
    """Build deterministic, position-normalized football-value discovery artifacts."""
    scored = json.loads((root / "data/production/cfb27_scored_population.json").read_text())
    ranked = [row for row in scored if row.get("score") is not None]
    raw = {row["card_id"]: row for row in load_population(root)}
    registry = build_model_registry(root)
    models = {(row["id"], row["version"]): row for row in registry["models"]}
    by_position: dict[str, list[dict]] = defaultdict(list)
    by_archetype: dict[tuple[str, str], list[dict]] = defaultdict(list)
    by_cell: dict[tuple[str, str, int], list[dict]] = defaultdict(list)
    for row in ranked:
        by_position[row["position_family"]].append(row)
        by_archetype[(row["position_family"], row["archetype"])].append(row)
        by_cell[(row["position_family"], row["archetype"], row["native_overall"])].append(row)
    attribute_values: dict[tuple[str, str, str], list[float]] = defaultdict(list)
    for row in ranked:
        for attribute, rating in raw[row["card_id"]].get("native_ratings", {}).items():
            if rating is not None:
                attribute_values[(row["position_family"], row["archetype"], attribute)].append(
                    float(rating)
                )

    metrics = []
    victim_rows = []
    network = []
    savings = []
    for position, rows in sorted(by_position.items()):
        position_scores = [row["score"] for row in rows]
        position_ovrs = [row["native_overall"] for row in rows]
        score_sorted = sorted(rows, key=lambda row: (row["score"], row["card_id"]))
        score_values = [row["score"] for row in score_sorted]
        for row in rows:
            arch_rows = by_archetype[(position, row["archetype"])]
            arch_scores = [peer["score"] for peer in arch_rows]
            cell = by_cell[(position, row["archetype"], row["native_overall"])]
            cell_scores = [peer["score"] for peer in cell]
            position_pct = _percentile(row["score"], position_scores)
            archetype_pct = _percentile(row["score"], arch_scores)
            ovr_pct = _percentile(row["native_overall"], position_ovrs)
            efficiency = position_pct - ovr_pct
            residual = row["score"] - statistics.median(cell_scores)
            rank_gap = 100 * (ovr_pct - (100 - position_pct)) / 100
            higher = [
                peer
                for peer in rows
                if peer["native_overall"] > row["native_overall"] and peer["score"] < row["score"]
            ]
            same_arch_higher = [peer for peer in higher if peer["archetype"] == row["archetype"]]
            lo = bisect.bisect_left(score_values, row["score"] - 1.0)
            hi = bisect.bisect_right(score_values, row["score"] + 1.0)
            near = [peer for peer in score_sorted[lo:hi] if peer["card_id"] != row["card_id"]]
            coverage = float(row["attribute_coverage"])
            confidence = (
                1.0
                if row["score_confidence"] == "HIGH"
                else 0.75
                if row["score_confidence"] == "MEDIUM"
                else 0.5
            )
            dominance = _percentile(row["score"], cell_scores)
            victim_pct = 100 * len(higher) / max(1, len(rows) - 1)
            model = models[(row["pancake_model_id"], row["pancake_model_version"])]
            profile = row["routing"]["profile"]
            if profile == "Blend":
                weights = {
                    attribute: max(
                        model["profiles"]["Vertical Threat"].get(attribute, 0),
                        model["profiles"]["Possession"].get(attribute, 0),
                    )
                    for attribute in set(model["profiles"]["Vertical Threat"])
                    | set(model["profiles"]["Possession"])
                }
            else:
                weights = model["profiles"][profile]
            ratings = raw[row["card_id"]].get("native_ratings", {})
            scarcity_terms = [
                (
                    weight,
                    _percentile(
                        float(ratings[attribute]),
                        attribute_values[(position, row["archetype"], attribute)],
                    ),
                )
                for attribute, weight in weights.items()
                if ratings.get(attribute) is not None
            ]
            scarcity = round(
                sum(weight * percentile for weight, percentile in scarcity_terms)
                / sum(weight for weight, _ in scarcity_terms),
                6,
            )
            density_score = max(0.0, 100 - min(100.0, len(near)))
            components = {
                "ovr_efficiency": max(0.0, min(100.0, 50 + efficiency)),
                "position_percentile": position_pct,
                "archetype_percentile": archetype_pct,
                "same_ovr_dominance": dominance,
                "higher_ovr_victim_rate": victim_pct,
                "weighted_attribute_scarcity": scarcity,
                "near_equivalent_selectivity": density_score,
                "confidence": 100 * confidence,
            }
            weights = {
                "ovr_efficiency": 0.25,
                "position_percentile": 0.20,
                "archetype_percentile": 0.15,
                "same_ovr_dominance": 0.15,
                "higher_ovr_victim_rate": 0.10,
                "weighted_attribute_scarcity": 0.05,
                "near_equivalent_selectivity": 0.05,
                "confidence": 0.05,
            }
            index = round(sum(components[key] * weights[key] for key in weights), 6)
            near_ids = {
                str(tolerance): [
                    peer["card_id"]
                    for peer in near
                    if abs(peer["score"] - row["score"]) <= tolerance
                ]
                for tolerance in (0.25, 0.5, 1.0)
            }
            lower_near = [peer for peer in near if peer["native_overall"] < row["native_overall"]]
            metrics.append(
                {
                    "card_id": row["card_id"],
                    "player_name": row["player_name"],
                    "position_family": position,
                    "archetype": row["archetype"],
                    "overall": row["native_overall"],
                    "score": row["score"],
                    "position_rank": row["position_rank"],
                    "archetype_rank": row["archetype_rank"],
                    "position_percentile": position_pct,
                    "archetype_percentile": archetype_pct,
                    "ovr_efficiency": round(efficiency, 6),
                    "same_ovr_residual": round(residual, 6),
                    "rank_gap_formulation": round(rank_gap, 6),
                    "distance_to_p90": round(_quantile(position_scores, 0.9) - row["score"], 6),
                    "distance_to_p95": round(_quantile(position_scores, 0.95) - row["score"], 6),
                    "distance_to_p98": round(_quantile(position_scores, 0.98) - row["score"], 6),
                    "same_ovr_dominance": dominance,
                    "attribute_scarcity": scarcity,
                    "local_score_density": len(near),
                    "near_equivalent_density": {k: len(v) for k, v in near_ids.items()},
                    "score_confidence": row["score_confidence"],
                    "attribute_coverage": coverage,
                    "components": components,
                    "football_value_index": index,
                    "market_status": "PRICE CHECK REQUIRED",
                }
            )
            victim_rows.append(
                {
                    "card_id": row["card_id"],
                    "higher_ovr_cards_beaten": len(higher),
                    "maximum_ovr_advantage_overcome": max(
                        (peer["native_overall"] - row["native_overall"] for peer in higher),
                        default=0,
                    ),
                    "highest_ranked_victim": min(higher, key=lambda peer: peer["position_rank"])[
                        "card_id"
                    ]
                    if higher
                    else None,
                    "same_archetype_victims": [peer["card_id"] for peer in same_arch_higher],
                    "same_position_victims": [peer["card_id"] for peer in higher],
                }
            )
            network.append(
                {
                    "card_id": row["card_id"],
                    "relationships": near_ids,
                    "closest": min(
                        near, key=lambda peer: (abs(peer["score"] - row["score"]), peer["card_id"])
                    )["card_id"]
                    if near
                    else None,
                    "lowest_ovr": min(
                        near, key=lambda peer: (peer["native_overall"], peer["card_id"])
                    )["card_id"]
                    if near
                    else None,
                    "highest_confidence": max(
                        near,
                        key=lambda peer: (
                            peer["attribute_coverage"],
                            -abs(peer["score"] - row["score"]),
                            peer["card_id"],
                        ),
                    )["card_id"]
                    if near
                    else None,
                    "same_archetype": next(
                        (peer["card_id"] for peer in near if peer["archetype"] == row["archetype"]),
                        None,
                    ),
                    "different_archetype": next(
                        (peer["card_id"] for peer in near if peer["archetype"] != row["archetype"]),
                        None,
                    ),
                    "profile_disclosure_required": any(
                        peer["archetype"] != row["archetype"] for peer in near
                    ),
                }
            )
            savings.append(
                {
                    "card_id": row["card_id"],
                    "lower_ovr_near_equivalents": [
                        {
                            "card_id": peer["card_id"],
                            "ovr_saved": row["native_overall"] - peer["native_overall"],
                            "score_sacrifice": round(row["score"] - peer["score"], 6),
                        }
                        for peer in sorted(
                            lower_near,
                            key=lambda peer: (
                                peer["native_overall"],
                                -peer["score"],
                                peer["card_id"],
                            ),
                        )
                    ],
                }
            )

    values = [row["football_value_index"] for row in metrics]
    thresholds = {
        tier: _quantile(values, q)
        for tier, q in (("INTERESTING", 0.60), ("STRONG", 0.80), ("ELITE", 0.95), ("EXTREME", 0.99))
    }
    for row in metrics:
        row["discovery_tier"] = next(
            (
                tier
                for tier in ("EXTREME", "ELITE", "STRONG", "INTERESTING")
                if row["football_value_index"] >= thresholds[tier]
            ),
            "ORDINARY",
        )
    cells = []
    for (position, archetype, overall), rows in sorted(by_cell.items()):
        ordered = sorted(rows, key=lambda row: (-row["score"], row["card_id"]))
        if len(ordered) < 2:
            continue
        cells.append(
            {
                "position_family": position,
                "archetype": archetype,
                "overall": overall,
                "count": len(ordered),
                "best": ordered[0]["card_id"],
                "median": ordered[len(ordered) // 2]["card_id"],
                "worst": ordered[-1]["card_id"],
                "score_spread": round(ordered[0]["score"] - ordered[-1]["score"], 6),
                "driver_disclosure": (
                    "See attribute contribution API; frozen-model contributions only"
                ),
            }
        )
    position_boards = {
        position: sorted(
            (row for row in metrics if row["position_family"] == position),
            key=lambda row: (-row["football_value_index"], row["card_id"]),
        )[:25]
        for position in sorted(by_position)
    }
    archetype_boards = {
        f"{position}|{archetype}": sorted(
            (
                row
                for row in metrics
                if row["position_family"] == position and row["archetype"] == archetype
            ),
            key=lambda row: (-row["football_value_index"], row["card_id"]),
        )[:15]
        for position, archetype in sorted(by_archetype)
    }
    return {
        "metrics": metrics,
        "victims": victim_rows,
        "network": network,
        "savings": savings,
        "cells": cells,
        "thresholds": thresholds,
        "position_boards": position_boards,
        "archetype_boards": archetype_boards,
        "raw_cards": raw,
    }


class DiscoveryIntelligence:
    """Read the frozen discovery artifacts for concise production queries."""

    def __init__(self, root: Path):
        self.root = root
        directory = root / "data/research/op_x_034"
        self.metrics = json.loads((directory / "football_value_index.json").read_text())["cards"]
        self.by_id = {row["card_id"]: row for row in self.metrics}
        self.network = {
            row["card_id"]: row
            for row in json.loads((directory / "near_equivalent_network.json").read_text())["cards"]
        }
        self.savings = {
            row["card_id"]: row
            for row in json.loads((directory / "ovr_savings.json").read_text())["cards"]
        }

    def discover(
        self, position: str | None = None, ovr_max: int | None = None, limit: int = 20
    ) -> list[dict]:
        rows = [
            row
            for row in self.metrics
            if (position is None or row["position_family"] == position)
            and (ovr_max is None or row["overall"] <= ovr_max)
        ]
        return sorted(rows, key=lambda row: (-row["football_value_index"], row["card_id"]))[:limit]

    def alternatives(self, card_id: str) -> dict:
        return {
            "target": self.by_id.get(card_id),
            "network": self.network.get(card_id),
            "market_status": "PRICE CHECK REQUIRED",
        }

    def ovr_savings(self, card_id: str) -> dict:
        return {
            "target": self.by_id.get(card_id),
            "ovr_savings": self.savings.get(card_id),
            "market_status": "PRICE CHECK REQUIRED",
        }
