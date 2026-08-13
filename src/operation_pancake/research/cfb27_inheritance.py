"""Descriptive CFB27 population and inherited Center architecture analysis."""

from __future__ import annotations

import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from operation_pancake.research.center_exact_validation import WEIGHT_TOTAL, WEIGHTS

ORDINARY_PROGRAM_PREFIXES = ("core", "platinum")


def _corr(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) < 3 or statistics.pstdev(xs) == 0 or statistics.pstdev(ys) == 0:
        return None
    return statistics.correlation(xs, ys)


def _fit(xs: list[float], ys: list[float]) -> tuple[float, float]:
    mean_x, mean_y = statistics.mean(xs), statistics.mean(ys)
    denominator = sum((x - mean_x) ** 2 for x in xs)
    slope = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys, strict=True)) / denominator
    return slope, mean_y - slope * mean_x


def _metrics(observed: list[int], predicted: list[int]) -> dict[str, float]:
    errors = [abs(a - b) for a, b in zip(observed, predicted, strict=True)]
    return {
        "exact_accuracy": round(sum(error == 0 for error in errors) / len(errors), 6),
        "within_one_accuracy": round(sum(error <= 1 for error in errors) / len(errors), 6),
        "mae": round(statistics.mean(errors), 6),
    }


def _center_inheritance(cards: list[dict[str, Any]]) -> dict[str, Any]:
    centers = [
        card
        for card in cards
        if card["position"] == "C" and all(k in card["displayed_ratings"] for k in WEIGHTS)
    ]
    rows = []
    for card in centers:
        score = sum(WEIGHTS[k] * card["displayed_ratings"][k] for k in WEIGHTS) / WEIGHT_TOTAL
        program = (card.get("program") or "").casefold()
        special = not program.startswith(ORDINARY_PROGRAM_PREFIXES)
        rows.append(
            {
                "card_id": card["external_card_id"],
                "player": card["player_name"],
                "ovr": card["overall"],
                "archetype": card.get("archetype"),
                "program": card.get("program"),
                "special_card": special,
                "madden19_weighted_score": round(score, 8),
            }
        )
    ordinary = [row for row in rows if not row["special_card"]]
    evaluation = ordinary if len(ordinary) >= 5 else rows
    observed, predicted, adjusted = [], [], []
    for heldout in evaluation:
        training = [row for row in evaluation if row is not heldout]
        slope, intercept = _fit(
            [row["madden19_weighted_score"] for row in training], [row["ovr"] for row in training]
        )
        base = slope * heldout["madden19_weighted_score"] + intercept
        residuals = defaultdict(list)
        for row in training:
            residuals[row["archetype"]].append(
                row["ovr"] - (slope * row["madden19_weighted_score"] + intercept)
            )
        offset = (
            statistics.mean(residuals[heldout["archetype"]])
            if len(residuals[heldout["archetype"]]) >= 3
            else 0.0
        )
        observed.append(heldout["ovr"])
        predicted.append(round(base))
        adjusted.append(round(base + offset))
    correlation = _corr(
        [row["madden19_weighted_score"] for row in rows], [row["ovr"] for row in rows]
    )
    return {
        "population": len(rows),
        "ordinary_population": len(ordinary),
        "special_population": len(rows) - len(ordinary),
        "cards": rows,
        "madden19_score_ovr_correlation": round(correlation, 6)
        if correlation is not None
        else None,
        "leave_one_out_recalibration": _metrics(observed, predicted),
        "leave_one_out_minimal_archetype_adjustment": _metrics(observed, adjusted),
        "madden19_attribute_order": [
            k for k, _ in sorted(WEIGHTS.items(), key=lambda item: (-item[1], item[0]))
        ],
        "classification": "STABLE_CORE_WITH_RECALIBRATION"
        if correlation is not None and correlation >= 0.7
        else "INSUFFICIENT_EVIDENCE",
        "special_card_warning": (
            "Legends and promotional cards are excluded from the primary ordinary-card "
            "validation when sample size permits."
        ),
    }


def build_inheritance_analysis(
    cards: list[dict[str, Any]], historical_leads: dict[str, Any]
) -> dict[str, Any]:
    """Build deterministic descriptive and constrained inheritance evidence."""
    cards = sorted(cards, key=lambda c: (c["position"], c["overall"], c["external_card_id"]))
    position_rows = {}
    for position in sorted({card["position"] for card in cards}):
        group = [card for card in cards if card["position"] == position]
        attributes = sorted(set.intersection(*(set(card["displayed_ratings"]) for card in group)))
        relationships = {}
        for attribute in attributes:
            values = [card["displayed_ratings"][attribute] for card in group]
            correlation = _corr(values, [card["overall"] for card in group])
            relationships[attribute] = {
                "correlation_with_ovr": round(correlation, 6) if correlation is not None else None,
                "mean": round(statistics.mean(values), 6),
            }
        means_by_ovr = {}
        for ovr in sorted({card["overall"] for card in group}):
            level = [card for card in group if card["overall"] == ovr]
            means_by_ovr[str(ovr)] = {
                a: round(statistics.mean(c["displayed_ratings"][a] for c in level), 4)
                for a in attributes
            }
        position_rows[position] = {
            "count": len(group),
            "ovr_range": [min(c["overall"] for c in group), max(c["overall"] for c in group)],
            "ovr_distribution": dict(sorted(Counter(c["overall"] for c in group).items())),
            "archetype_distribution": dict(
                sorted(Counter(c.get("archetype") or "UNKNOWN" for c in group).items())
            ),
            "attribute_relationships": relationships,
            "attribute_means_by_ovr": means_by_ovr,
        }
    thresholds = []
    for position, _summary in position_rows.items():
        group = [card for card in cards if card["position"] == position]
        levels = sorted({card["overall"] for card in group})
        common = set.intersection(*(set(card["displayed_ratings"]) for card in group))
        for lower in levels:
            upper = lower + 1
            below, above = ([c for c in group if c["overall"] == value] for value in (lower, upper))
            if not below or not above:
                continue
            for attribute in sorted(common):
                difference = statistics.mean(
                    c["displayed_ratings"][attribute] for c in above
                ) - statistics.mean(c["displayed_ratings"][attribute] for c in below)
                classification = (
                    "CANDIDATE_THRESHOLD"
                    if len(below) >= 2 and len(above) >= 2 and difference >= 2
                    else "INSUFFICIENT"
                )
                thresholds.append(
                    {
                        "position": position,
                        "boundary": f"{lower}->{upper}",
                        "attribute": attribute,
                        "lower_n": len(below),
                        "upper_n": len(above),
                        "mean_difference": round(difference, 4),
                        "classification": classification,
                    }
                )
    center = _center_inheritance(cards)
    practical = []
    if center["leave_one_out_recalibration"]["within_one_accuracy"] >= 0.95:
        practical.append("C")
    return {
        "schema_version": 1,
        "phase": "CFB27 Population & EA Architectural Inheritance Phase I",
        "cards_acquired": len(cards),
        "positions": position_rows,
        "center_inheritance": center,
        "threshold_candidates": thresholds,
        "historical_leads": historical_leads,
        "ea_evolution_hypothesis": {
            "chain": [
                "MADDEN_16_ARCHETYPE_WEIGHTS",
                "MADDEN_19_ARCHITECTURE",
                "MADDEN_20_ADJUSTMENTS",
                "MADDEN_21_ARCHETYPE_TUNABLES",
                "LATER_MADDEN",
                "CFB27",
            ],
            "classification": center["classification"],
            "scope": "CENTER_ONLY; other positions lack inherited numeric priors",
        },
        "practical_95_positions": practical,
        "operationally_solved_98_positions": [],
        "pc_evaluator": {
            "C": {
                "status": "PRACTICAL_RESEARCH_MODEL" if practical else "RESEARCH_ONLY",
                "confidence": "MODERATE" if practical else "LOW",
                "attribute_importance": WEIGHTS,
                "archetype_handling": "minimal residual offset evaluated leakage-free",
                "validation_metrics": center["leave_one_out_recalibration"],
                "known_limitations": [
                    "bounded public sample",
                    "historical Madden row-level population unavailable",
                    "special cards separated",
                    "not operationally solved",
                ],
            }
        },
        "canonical_modified": False,
        "guessed_values": False,
    }


def write_inheritance_artifacts(directory: str | Path, analysis: dict[str, Any]) -> None:
    root = Path(directory)
    root.mkdir(parents=True, exist_ok=True)
    payloads = {
        "analysis_summary.json": analysis,
        "population_descriptives.json": analysis["positions"],
        "center_inheritance.json": analysis["center_inheritance"],
        "threshold_candidates.json": analysis["threshold_candidates"],
        "ea_historical_leads.json": analysis["historical_leads"],
        "pc_evaluator_models.json": analysis["pc_evaluator"],
    }
    for name, payload in payloads.items():
        (root / name).write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
