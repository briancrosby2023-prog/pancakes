"""Evidence mining across CFB27 position families for OP-X-012E.15.

This is scientific support code, not a workflow controller. It extracts two
high-value signals directly from the canonical Alpha population:

* same-OVR within-archetype rating spreads (large spreads weaken a rating as a
  dominant OVR driver), and
* adjacent-OVR directional shifts (consistent shifts strengthen a rating as a
  candidate driver).

The output deliberately does not claim causal weights or exact prediction.
"""

from __future__ import annotations

from collections import defaultdict
from statistics import median
from typing import Iterable, Mapping, Sequence


FAMILIES: dict[str, tuple[str, ...]] = {
    "BLOCKING": ("C", "TE", "LG", "RG", "LT", "RT"),
    "COVERAGE": ("CB", "FS", "SS"),
    "FRONT_SEVEN": ("DT", "MLB", "SAM", "WILL", "LE", "RE"),
}


def _complete_numeric_ratings(card: Mapping) -> dict[str, float]:
    ratings = card.get("displayed_ratings")
    if not isinstance(ratings, Mapping):
        return {}
    return {
        str(key): float(value)
        for key, value in ratings.items()
        if isinstance(value, (int, float)) and not isinstance(value, bool)
    }


def analyze_position(cards: Iterable[Mapping], position: str, *, min_cell: int = 4) -> dict:
    """Extract fixed-OVR and adjacent-OVR constraints for one native position."""
    rows = [
        card
        for card in cards
        if card.get("position") == position
        and card.get("overall") is not None
        and card.get("archetype")
        and _complete_numeric_ratings(card)
    ]
    cells: dict[tuple[str, int], list[Mapping]] = defaultdict(list)
    for card in rows:
        cells[(str(card["archetype"]), int(card["overall"]))].append(card)

    spread_by_rating: dict[str, list[float]] = defaultdict(list)
    spread_examples: dict[str, list[dict]] = defaultdict(list)
    for (archetype, ovr), cell in cells.items():
        if len(cell) < min_cell:
            continue
        common = set(_complete_numeric_ratings(cell[0]))
        for card in cell[1:]:
            common &= set(_complete_numeric_ratings(card))
        for rating in common:
            values = [_complete_numeric_ratings(card)[rating] for card in cell]
            spread = max(values) - min(values)
            spread_by_rating[rating].append(spread)
            if spread > 0:
                spread_examples[rating].append(
                    {"archetype": archetype, "ovr": ovr, "n": len(cell), "spread": spread}
                )

    adjacent_by_rating: dict[str, list[float]] = defaultdict(list)
    archetypes = sorted({str(card["archetype"]) for card in rows})
    for archetype in archetypes:
        by_ovr = {
            ovr: cell for (cell_arch, ovr), cell in cells.items()
            if cell_arch == archetype and len(cell) >= min_cell
        }
        for low_ovr in sorted(by_ovr):
            high_ovr = low_ovr + 1
            if high_ovr not in by_ovr:
                continue
            low, high = by_ovr[low_ovr], by_ovr[high_ovr]
            common = set(_complete_numeric_ratings(low[0])) & set(_complete_numeric_ratings(high[0]))
            for card in low[1:] + high[1:]:
                common &= set(_complete_numeric_ratings(card))
            for rating in common:
                low_med = median(_complete_numeric_ratings(card)[rating] for card in low)
                high_med = median(_complete_numeric_ratings(card)[rating] for card in high)
                adjacent_by_rating[rating].append(high_med - low_med)

    rating_rows = []
    for rating in sorted(set(spread_by_rating) | set(adjacent_by_rating)):
        spreads = spread_by_rating.get(rating, [])
        deltas = adjacent_by_rating.get(rating, [])
        positive = sum(delta > 0 for delta in deltas)
        negative = sum(delta < 0 for delta in deltas)
        rating_rows.append(
            {
                "rating": rating,
                "same_ovr_cells": len(spreads),
                "median_same_ovr_spread": median(spreads) if spreads else None,
                "max_same_ovr_spread": max(spreads) if spreads else None,
                "largest_spread_examples": sorted(
                    spread_examples.get(rating, []), key=lambda row: (-row["spread"], row["archetype"], row["ovr"])
                )[:3],
                "adjacent_boundaries": len(deltas),
                "median_adjacent_delta": median(deltas) if deltas else None,
                "positive_boundary_share": positive / len(deltas) if deltas else None,
                "negative_boundary_share": negative / len(deltas) if deltas else None,
            }
        )

    likely_non_drivers = sorted(
        (
            row for row in rating_rows
            if row["same_ovr_cells"] >= 3
            and (row["median_same_ovr_spread"] or 0) >= 10
            and (row["positive_boundary_share"] is None or row["positive_boundary_share"] < 0.65)
        ),
        key=lambda row: (-(row["median_same_ovr_spread"] or 0), row["rating"]),
    )
    candidate_drivers = sorted(
        (
            row for row in rating_rows
            if row["adjacent_boundaries"] >= 3
            and (row["positive_boundary_share"] or 0) >= 0.75
            and (row["median_adjacent_delta"] or 0) > 0
        ),
        key=lambda row: (-(row["positive_boundary_share"] or 0), -(row["median_adjacent_delta"] or 0), row["rating"]),
    )
    return {
        "position": position,
        "cards": len(rows),
        "archetypes": sorted({str(card["archetype"]) for card in rows}),
        "ratings": rating_rows,
        "candidate_drivers": candidate_drivers,
        "likely_non_drivers": likely_non_drivers,
        "interpretation": "heuristic constraints only; predictive validation remains separate",
    }


def build_multi_family_matrix(cards: Sequence[Mapping]) -> dict:
    """Analyze all three E.15 first-pass position families in one deterministic artifact."""
    families = {}
    for family, positions in FAMILIES.items():
        families[family] = {
            "positions": [analyze_position(cards, position) for position in positions],
        }
    return {
        "phase": "OP-X-012E.15",
        "method": "SAME_OVR_SPREAD_PLUS_ADJACENT_BOUNDARY",
        "families": families,
        "prediction_accuracy_measured": False,
    }
