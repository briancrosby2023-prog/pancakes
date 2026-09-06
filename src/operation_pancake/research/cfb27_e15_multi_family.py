"""Evidence mining across CFB27 position families for OP-X-012E.15.

Extract same-OVR spread, adjacent-OVR movement, and archetype-level consistency.
The output is hypothesis discrimination evidence, not an exact OVR claim.
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
    adjacent_by_rating_archetype: dict[str, dict[str, list[float]]] = defaultdict(
        lambda: defaultdict(list)
    )
    archetypes = sorted({str(card["archetype"]) for card in rows})
    for archetype in archetypes:
        by_ovr = {
            ovr: cell
            for (cell_arch, ovr), cell in cells.items()
            if cell_arch == archetype and len(cell) >= min_cell
        }
        for low_ovr in sorted(by_ovr):
            high_ovr = low_ovr + 1
            if high_ovr not in by_ovr:
                continue
            low, high = by_ovr[low_ovr], by_ovr[high_ovr]
            common = set(_complete_numeric_ratings(low[0])) & set(
                _complete_numeric_ratings(high[0])
            )
            for card in low[1:] + high[1:]:
                common &= set(_complete_numeric_ratings(card))
            for rating in common:
                low_med = median(_complete_numeric_ratings(card)[rating] for card in low)
                high_med = median(_complete_numeric_ratings(card)[rating] for card in high)
                delta = high_med - low_med
                adjacent_by_rating[rating].append(delta)
                adjacent_by_rating_archetype[rating][archetype].append(delta)

    rating_rows = []
    for rating in sorted(set(spread_by_rating) | set(adjacent_by_rating)):
        spreads = spread_by_rating.get(rating, [])
        deltas = adjacent_by_rating.get(rating, [])
        positive = sum(delta > 0 for delta in deltas)
        negative = sum(delta < 0 for delta in deltas)
        archetype_signals = []
        for archetype, arch_deltas in sorted(adjacent_by_rating_archetype[rating].items()):
            arch_positive = sum(delta > 0 for delta in arch_deltas)
            archetype_signals.append(
                {
                    "archetype": archetype,
                    "boundaries": len(arch_deltas),
                    "median_delta": median(arch_deltas),
                    "positive_share": arch_positive / len(arch_deltas),
                }
            )
        positive_arches = [
            row
            for row in archetype_signals
            if row["boundaries"] >= 2 and row["positive_share"] >= 0.75 and row["median_delta"] > 0
        ]
        negative_arches = [
            row
            for row in archetype_signals
            if row["boundaries"] >= 2 and row["positive_share"] <= 0.25 and row["median_delta"] < 0
        ]
        if positive_arches and negative_arches:
            architecture_signal = "ARCHETYPE_DEPENDENT"
        elif len(positive_arches) >= 2:
            architecture_signal = "SHARED_POSITIVE_CANDIDATE"
        else:
            architecture_signal = "UNRESOLVED"
        rating_rows.append(
            {
                "rating": rating,
                "same_ovr_cells": len(spreads),
                "median_same_ovr_spread": median(spreads) if spreads else None,
                "max_same_ovr_spread": max(spreads) if spreads else None,
                "largest_spread_examples": sorted(
                    spread_examples.get(rating, []),
                    key=lambda row: (-row["spread"], row["archetype"], row["ovr"]),
                )[:3],
                "adjacent_boundaries": len(deltas),
                "median_adjacent_delta": median(deltas) if deltas else None,
                "positive_boundary_share": positive / len(deltas) if deltas else None,
                "negative_boundary_share": negative / len(deltas) if deltas else None,
                "archetype_signals": archetype_signals,
                "architecture_signal": architecture_signal,
            }
        )

    likely_non_drivers = sorted(
        (
            row
            for row in rating_rows
            if row["same_ovr_cells"] >= 3
            and (row["median_same_ovr_spread"] or 0) >= 10
            and (row["positive_boundary_share"] is None or row["positive_boundary_share"] < 0.65)
        ),
        key=lambda row: (-(row["median_same_ovr_spread"] or 0), row["rating"]),
    )
    candidate_drivers = sorted(
        (
            row
            for row in rating_rows
            if row["adjacent_boundaries"] >= 3
            and (row["positive_boundary_share"] or 0) >= 0.75
            and (row["median_adjacent_delta"] or 0) > 0
        ),
        key=lambda row: (
            -(row["positive_boundary_share"] or 0),
            -(row["median_adjacent_delta"] or 0),
            row["rating"],
        ),
    )
    archetype_dependent = [
        row for row in rating_rows if row["architecture_signal"] == "ARCHETYPE_DEPENDENT"
    ]
    shared_candidates = [
        row for row in rating_rows if row["architecture_signal"] == "SHARED_POSITIVE_CANDIDATE"
    ]
    return {
        "position": position,
        "cards": len(rows),
        "archetypes": archetypes,
        "ratings": rating_rows,
        "candidate_drivers": candidate_drivers,
        "likely_non_drivers": likely_non_drivers,
        "shared_component_candidates": shared_candidates,
        "archetype_dependent_candidates": archetype_dependent,
        "interpretation": "heuristic constraints only; predictive validation remains separate",
    }


def build_multi_family_matrix(cards: Sequence[Mapping]) -> dict:
    families = {}
    for family, positions in FAMILIES.items():
        families[family] = {
            "positions": [analyze_position(cards, position) for position in positions],
        }
    return {
        "phase": "OP-X-012E.15",
        "method": "SAME_OVR_SPREAD_PLUS_ADJACENT_BOUNDARY_PLUS_ARCHETYPE_CONSISTENCY",
        "families": families,
        "prediction_accuracy_measured": False,
    }
