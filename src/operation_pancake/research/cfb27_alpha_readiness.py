"""Formula-readiness diagnostics for the CFB27 Alpha population."""

from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path

from operation_pancake.research.cfb27_alpha_population import build_alpha_population

RESEARCH_RATINGS = {
    "SPD",
    "ACC",
    "AGI",
    "COD",
    "STR",
    "AWR",
    "PRC",
    "BSH",
    "TAK",
    "PUR",
    "POW",
    "MCV",
    "ZCV",
    "PRS",
    "PMV",
    "FMV",
    "PBK",
    "PBP",
    "PBF",
    "RBK",
    "RBP",
    "RBF",
    "IBL",
    "LBK",
}
FOCUS_POSITIONS = {
    "C",
    "TE",
    "CB",
    "FS",
    "SS",
    "DT",
    "SAM",
    "MIKE",
    "WILL",
    "LEDG",
    "REDG",
}


def _formula_eligible(card: dict) -> tuple[bool, str]:
    if card.get("extraction_status") != "COMPLETE":
        return False, "INCOMPLETE_VECTOR"
    ratings = card.get("displayed_ratings") or {}
    if len(ratings) < 15:
        return False, "INSUFFICIENT_RATINGS"
    if card.get("overall") is None or not card.get("position") or not card.get("archetype"):
        return False, "MISSING_IDENTITY_FIELD"
    if any(not isinstance(value, int) or value < 0 or value > 99 for value in ratings.values()):
        return False, "INVALID_RATING_VALUE"
    metadata = card.get("metadata") or {}
    if metadata.get("dynamic_state") or metadata.get("projected_state"):
        return False, "DYNAMIC_OR_PROJECTED"
    return True, "STATIC_NATIVE_CANDIDATE"


def _same_ovr_cells(cards: list[dict]) -> list[dict]:
    grouped: dict[tuple[str, str, int], list[dict]] = defaultdict(list)
    for card in cards:
        grouped[(card["position"], card["archetype"], card["overall"])].append(card)
    rows = []
    for (position, archetype, ovr), members in grouped.items():
        if len(members) < 2:
            continue
        fields = sorted(
            field
            for field in RESEARCH_RATINGS
            if sum(field in (card.get("displayed_ratings") or {}) for card in members) >= 2
        )
        spreads = {}
        for field in fields:
            values = [
                card["displayed_ratings"][field]
                for card in members
                if field in card["displayed_ratings"]
            ]
            if len(values) >= 2:
                spreads[field] = max(values) - min(values)
        rows.append(
            {
                "position": position,
                "archetype": archetype,
                "ovr": ovr,
                "cards": len(members),
                "pairwise_comparisons": len(members) * (len(members) - 1) // 2,
                "max_rating_spread": max(spreads.values()) if spreads else 0,
                "largest_spreads": dict(
                    sorted(spreads.items(), key=lambda item: (-item[1], item[0]))[:8]
                ),
            }
        )
    return sorted(
        rows,
        key=lambda row: (-row["pairwise_comparisons"], row["position"], row["ovr"]),
    )


def _focus_extreme_contrasts(cards: list[dict]) -> dict[str, list[dict]]:
    """Expose reproducible same-position/archetype/OVR experiments with card IDs."""
    grouped: dict[tuple[str, str, int], list[dict]] = defaultdict(list)
    for card in cards:
        if card["position"] in FOCUS_POSITIONS:
            grouped[(card["position"], card["archetype"], card["overall"])].append(card)
    by_position: dict[str, list[dict]] = defaultdict(list)
    for (position, archetype, ovr), members in grouped.items():
        if len(members) < 2:
            continue
        for rating in RESEARCH_RATINGS:
            observed = [
                (card["displayed_ratings"][rating], card)
                for card in members
                if rating in card["displayed_ratings"]
            ]
            if len(observed) < 2:
                continue
            low_value, low = min(
                observed,
                key=lambda item: (item[0], item[1]["external_card_id"]),
            )
            high_value, high = max(
                observed,
                key=lambda item: (item[0], item[1]["external_card_id"]),
            )
            if high_value == low_value:
                continue
            by_position[position].append(
                {
                    "position": position,
                    "archetype": archetype,
                    "ovr": ovr,
                    "rating": rating,
                    "spread": high_value - low_value,
                    "low_card_id": low["external_card_id"],
                    "low_player": low["player_name"],
                    "low_value": low_value,
                    "high_card_id": high["external_card_id"],
                    "high_player": high["player_name"],
                    "high_value": high_value,
                    "cell_cards": len(members),
                }
            )
    return {
        position: sorted(
            rows,
            key=lambda row: (-row["spread"], row["rating"], row["ovr"]),
        )[:50]
        for position, rows in sorted(by_position.items())
    }


def build_alpha_readiness(root: Path) -> dict:
    population = build_alpha_population(root)
    cards = list(population["cards"].values())
    reasons = Counter()
    eligible = []
    for card in cards:
        ok, reason = _formula_eligible(card)
        reasons[reason] += 1
        if ok:
            eligible.append(card)

    by_position = {}
    grouped = defaultdict(list)
    for card in eligible:
        grouped[card["position"]].append(card)
    cells = _same_ovr_cells(eligible)
    cells_by_position = Counter(row["position"] for row in cells)
    pairs_by_position = Counter()
    for row in cells:
        pairs_by_position[row["position"]] += row["pairwise_comparisons"]

    for position, rows in sorted(grouped.items()):
        ovrs = [row["overall"] for row in rows]
        archetypes = Counter(row["archetype"] for row in rows)
        pair_count = pairs_by_position[position]
        if len(rows) >= 50 and cells_by_position[position] >= 3:
            readiness = "READY_NOW"
        elif len(rows) >= 15 and cells_by_position[position] >= 1:
            readiness = "USABLE_WITH_RESTRICTIONS"
        else:
            readiness = "SPARSE"
        by_position[position] = {
            "formula_eligible_cards": len(rows),
            "ovr_range": [min(ovrs), max(ovrs)],
            "archetypes": dict(sorted(archetypes.items())),
            "same_ovr_archetype_cells": cells_by_position[position],
            "pairwise_natural_experiments": pair_count,
            "readiness": readiness,
        }

    focus = {
        position: by_position.get(position, {"readiness": "NOT_READY"})
        for position in sorted(FOCUS_POSITIONS)
    }
    return {
        "alpha_population": population["summary"],
        "formula_eligibility": {
            "eligible": len(eligible),
            "excluded": len(cards) - len(eligible),
            "classification_counts": dict(sorted(reasons.items())),
        },
        "position_readiness": by_position,
        "focus_position_readiness": focus,
        "natural_experiment_inventory": {
            "same_ovr_archetype_cells": len(cells),
            "pairwise_comparisons": sum(row["pairwise_comparisons"] for row in cells),
            "richest_cells": cells[:50],
        },
        "focus_extreme_contrasts": _focus_extreme_contrasts(eligible),
    }
