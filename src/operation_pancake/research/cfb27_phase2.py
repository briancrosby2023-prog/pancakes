"""Phase-II inherited-model battery for the cached CFB27 population."""

from __future__ import annotations

import json
import random
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from operation_pancake.research.center_exact_validation import WEIGHTS

ORDINARY_PREFIXES = ("core", "platinum")


def is_special(card: dict[str, Any]) -> bool:
    return not (card.get("program") or "").casefold().startswith(ORDINARY_PREFIXES)


def _fit(xs: list[float], ys: list[float], fixed_slope: float | None = None) -> tuple[float, float]:
    if fixed_slope is not None:
        return fixed_slope, statistics.mean(
            y - fixed_slope * x for x, y in zip(xs, ys, strict=True)
        )
    mean_x, mean_y = statistics.mean(xs), statistics.mean(ys)
    denominator = sum((x - mean_x) ** 2 for x in xs)
    if denominator == 0:
        return 0.0, mean_y
    slope = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys, strict=True)) / denominator
    return slope, mean_y - slope * mean_x


def _metrics(observed: list[int], predictions: list[int]) -> dict[str, float]:
    errors = [abs(a - b) for a, b in zip(observed, predictions, strict=True)]
    pairs = [
        (i, j)
        for i in range(len(observed))
        for j in range(i + 1, len(observed))
        if observed[i] != observed[j]
    ]
    ordered = sum(
        (predictions[i] - predictions[j]) * (observed[i] - observed[j]) > 0 for i, j in pairs
    )
    return {
        "n": len(observed),
        "exact_accuracy": round(sum(e == 0 for e in errors) / len(errors), 6),
        "within_one_accuracy": round(sum(e <= 1 for e in errors) / len(errors), 6),
        "mae": round(statistics.mean(errors), 6),
        "ordering_accuracy": round(ordered / len(pairs), 6) if pairs else 0.0,
    }


def _score(card: dict[str, Any], weights: dict[str, float]) -> float:
    available = {key: value for key, value in weights.items() if key in card["displayed_ratings"]}
    if not available:
        raise ValueError("No inherited attributes available for card.")
    total = sum(available.values())
    return sum(weight * card["displayed_ratings"][key] for key, weight in available.items()) / total


def _threshold_predict(training: list[tuple[float, int]], score: float) -> int:
    medians = sorted(
        (statistics.median(s for s, y in training if y == level), level)
        for level in {y for _, y in training}
    )
    thresholds = [(medians[i][0] + medians[i + 1][0]) / 2 for i in range(len(medians) - 1)]
    index = sum(score >= threshold for threshold in thresholds)
    return medians[index][1]


def _loocv(
    rows: list[dict[str, Any]], weights: dict[str, float], form: str
) -> tuple[dict[str, float], list[dict[str, Any]]]:
    scored = [(_score(card, weights), card) for card in rows]
    observed, predicted, results = [], [], []
    for index, (score, card) in enumerate(scored):
        training = [(s, c["overall"]) for n, (s, c) in enumerate(scored) if n != index]
        if form == "linear":
            slope, intercept = _fit([s for s, _ in training], [y for _, y in training], 1.0)
            raw = slope * score + intercept
            estimate = round(raw)
        elif form == "affine":
            slope, intercept = _fit([s for s, _ in training], [y for _, y in training])
            raw = slope * score + intercept
            estimate = round(raw)
        elif form == "discrete_threshold":
            estimate = _threshold_predict(training, score)
            raw = float(estimate)
        else:
            raise ValueError(f"Unknown calibration form: {form}")
        observed.append(card["overall"])
        predicted.append(estimate)
        results.append(
            {
                "card_id": card["external_card_id"],
                "player": card["player_name"],
                "ovr": card["overall"],
                "archetype": card.get("archetype"),
                "special": is_special(card),
                "score": round(score, 8),
                "prediction": estimate,
                "residual": round(card["overall"] - raw, 8),
            }
        )
    return _metrics(observed, predicted), results


def _archetype_comparison(rows: list[dict[str, Any]], weights: dict[str, float]) -> dict[str, Any]:
    scored = [(_score(card, weights), card) for card in rows]
    observed, base_predictions, modifier_predictions, separate_predictions = [], [], [], []
    separate_eligible = 0
    for index, (score, card) in enumerate(scored):
        training = [(s, c) for n, (s, c) in enumerate(scored) if n != index]
        slope, intercept = _fit([s for s, _ in training], [c["overall"] for _, c in training])
        base = slope * score + intercept
        residuals = [
            c["overall"] - (slope * s + intercept)
            for s, c in training
            if c.get("archetype") == card.get("archetype")
        ]
        modifier = statistics.mean(residuals) if len(residuals) >= 3 else 0.0
        same = [
            (s, c["overall"]) for s, c in training if c.get("archetype") == card.get("archetype")
        ]
        if len(same) >= 4 and len({value for _, value in same}) >= 2:
            arch_slope, arch_intercept = _fit([s for s, _ in same], [value for _, value in same])
            separate = arch_slope * score + arch_intercept
            separate_eligible += 1
        else:
            separate = base
        observed.append(card["overall"])
        base_predictions.append(round(base))
        modifier_predictions.append(round(base + modifier))
        separate_predictions.append(round(separate))
    return {
        "no_correction": _metrics(observed, base_predictions),
        "small_modifier": _metrics(observed, modifier_predictions),
        "separate_formula": _metrics(observed, separate_predictions),
        "separate_formula_eligible_holdouts": separate_eligible,
    }


def _center_analysis(cards: list[dict[str, Any]]) -> dict[str, Any]:
    centers = [
        card
        for card in cards
        if card["position"] == "C" and all(key in card["displayed_ratings"] for key in WEIGHTS)
    ]
    ordinary = [card for card in centers if not is_special(card)]
    calibrations = {}
    prediction_rows = {}
    for form in ("linear", "affine", "discrete_threshold"):
        calibrations[form], prediction_rows[form] = _loocv(ordinary, WEIGHTS, form)
    scores = [_score(card, WEIGHTS) for card in ordinary]
    correlation = (
        statistics.correlation(scores, [card["overall"] for card in ordinary])
        if len(set(scores)) > 1
        else None
    )
    best_form = min(
        calibrations,
        key=lambda form: (
            calibrations[form]["mae"],
            -calibrations[form]["ordering_accuracy"],
            form,
        ),
    )
    residuals = prediction_rows[best_form]
    by_ovr, by_archetype = defaultdict(list), defaultdict(list)
    for row in residuals:
        by_ovr[str(row["ovr"])].append(row["residual"])
        by_archetype[row["archetype"]].append(row["residual"])
    bias = {
        "by_ovr": {
            key: round(statistics.mean(values), 6) for key, values in sorted(by_ovr.items())
        },
        "by_archetype": {
            key: {"n": len(values), "mean_residual": round(statistics.mean(values), 6)}
            for key, values in sorted(by_archetype.items())
        },
    }
    perturbations = []
    baseline = calibrations["affine"]
    for attribute in WEIGHTS:
        for factor in (0.75, 0.9, 1.1, 1.25):
            candidate = dict(WEIGHTS)
            candidate[attribute] *= factor
            metrics, _ = _loocv(ordinary, candidate, "affine")
            perturbations.append(
                {
                    "attribute": attribute,
                    "factor": factor,
                    "metrics": metrics,
                    "mae_change": round(metrics["mae"] - baseline["mae"], 6),
                }
            )
    best_perturbation = min(
        perturbations, key=lambda item: (item["metrics"]["mae"], -item["metrics"]["exact_accuracy"])
    )
    rng = random.Random(2719)
    neighborhood = []
    for _ in range(200):
        candidate = {key: value * rng.uniform(0.9, 1.1) for key, value in WEIGHTS.items()}
        metrics, _ = _loocv(ordinary, candidate, "affine")
        neighborhood.append(metrics)
    equivalent = sum(item["mae"] <= baseline["mae"] + 0.05 for item in neighborhood)
    stability = {}
    for attribute, weight in WEIGHTS.items():
        impacts = [
            abs(item["mae_change"])
            for item in perturbations
            if item["attribute"] == attribute and item["factor"] in (0.9, 1.1)
        ]
        if weight >= 10 and max(impacts) >= 0.02:
            label = "STABLE_HIGH_IMPORTANCE"
        elif weight <= 4 and max(impacts) < 0.02:
            label = "STABLE_LOW_IMPORTANCE"
        else:
            label = "POORLY_IDENTIFIED"
        stability[attribute] = {
            "historical_weight": weight,
            "classification": label,
            "local_mae_impact": round(max(impacts), 6),
        }
    bands = []
    for ovr in sorted({card["overall"] for card in ordinary}):
        values = [_score(card, WEIGHTS) for card in ordinary if card["overall"] == ovr]
        bands.append(
            {
                "ovr": ovr,
                "n": len(values),
                "minimum": round(min(values), 6),
                "maximum": round(max(values), 6),
                "width": round(max(values) - min(values), 6),
                "supported_structure": len(values) >= 4 and max(values) - min(values) >= 0.5,
            }
        )
    return {
        "population": len(centers),
        "ordinary_n": len(ordinary),
        "special_n": len(centers) - len(ordinary),
        "ovr_range": [min(c["overall"] for c in centers), max(c["overall"] for c in centers)],
        "correlation": round(correlation, 6) if correlation is not None else None,
        "calibrations": calibrations,
        "piecewise": {
            "status": "NOT_JUSTIFIED",
            "reason": (
                "Ordinary per-segment cells remain too small to justify extra knots over "
                "affine or discrete calibration."
            ),
        },
        "best_calibration": best_form,
        "predictions": prediction_rows[best_form],
        "bias": bias,
        "archetype_model_comparison": _archetype_comparison(ordinary, WEIGHTS),
        "weight_perturbation": {
            "baseline": baseline,
            "best_single_change": best_perturbation,
            "small_change_sufficient": best_perturbation["factor"] in (0.9, 1.1),
            "large_change_required": best_perturbation["factor"] in (0.75, 1.25),
            "sign_change_required": False,
        },
        "weight_stability": {
            "nearby_vectors_tested": len(neighborhood),
            "equivalent_vectors": equivalent,
            "attributes": stability,
        },
        "hidden_bands": bands,
    }


def _special_comparison(cards: list[dict[str, Any]]) -> dict[str, Any]:
    output = {}
    for position in sorted({card["position"] for card in cards}):
        group = [card for card in cards if card["position"] == position]
        ordinary, special = (
            [card for card in group if is_special(card) == flag] for flag in (False, True)
        )
        if len(ordinary) < 5 or len(special) < 5:
            continue
        common = set.intersection(*(set(card["displayed_ratings"]) for card in group))
        differences = {}
        for attribute in common:
            ordinary_offset = statistics.mean(
                card["displayed_ratings"][attribute] - card["overall"] for card in ordinary
            )
            special_offset = statistics.mean(
                card["displayed_ratings"][attribute] - card["overall"] for card in special
            )
            differences[attribute] = round(special_offset - ordinary_offset, 4)
        ranked = sorted(differences.items(), key=lambda item: abs(item[1]), reverse=True)
        output[position] = {
            "ordinary_n": len(ordinary),
            "special_n": len(special),
            "largest_ovr_adjusted_rating_differences": dict(ranked[:8]),
            "warning": (
                "Descriptive differences may reflect archetype/player selection, "
                "not special-card tuning."
            ),
        }
    return output


def _boundaries(cards: list[dict[str, Any]]) -> list[dict[str, Any]]:
    results = []
    for position in sorted({card["position"] for card in cards}):
        group = [card for card in cards if card["position"] == position]
        common = set.intersection(*(set(card["displayed_ratings"]) for card in group))
        for archetype in sorted({card.get("archetype") for card in group}):
            subset = [card for card in group if card.get("archetype") == archetype]
            for lower in sorted({card["overall"] for card in subset}):
                below = [card for card in subset if card["overall"] == lower]
                above = [card for card in subset if card["overall"] == lower + 1]
                if not below or not above:
                    continue
                for attribute in sorted(common):
                    effect = statistics.mean(
                        c["displayed_ratings"][attribute] for c in above
                    ) - statistics.mean(c["displayed_ratings"][attribute] for c in below)
                    enough = len(below) >= 5 and len(above) >= 5
                    results.append(
                        {
                            "position": position,
                            "archetype": archetype,
                            "boundary": f"{lower}->{lower + 1}",
                            "attribute": attribute,
                            "lower_n": len(below),
                            "upper_n": len(above),
                            "effect": round(effect, 6),
                            "classification": "CANDIDATE_THRESHOLD"
                            if enough and effect >= 2
                            else "INSUFFICIENT",
                            "alternative_explanation": (
                                "card-program mix, correlated ratings, and selection effects "
                                "remain plausible"
                            ),
                        }
                    )
    return results


def _qb_inheritance(
    cards: list[dict[str, Any]], weights: dict[str, dict[str, float]]
) -> dict[str, Any]:
    mapping = {
        "Pocket Passer": "Field General",
        "Dual Threat": "Scrambler",
        "Backfield Creator": "West Coast",
    }
    qbs = [card for card in cards if card["position"] == "QB" and card.get("archetype") in mapping]
    results = {}
    for archetype in sorted({card["archetype"] for card in qbs}):
        group = [card for card in qbs if card["archetype"] == archetype]
        ordinary = [card for card in group if not is_special(card)]
        evaluation = ordinary if len(ordinary) >= 6 else group
        if len(evaluation) < 4 or len({card["overall"] for card in evaluation}) < 2:
            results[archetype] = {"n": len(evaluation), "status": "INSUFFICIENT_OVR_BREADTH"}
            continue
        metrics, rows = _loocv(evaluation, weights[mapping[archetype]], "affine")
        results[archetype] = {
            "n": len(evaluation),
            "historical_prior": mapping[archetype],
            "metrics": metrics,
            "failure_cards": [row for row in rows if abs(row["residual"]) > 1],
            "status": "INHERITED_BASELINE_ONLY",
        }
    return {
        "archetypes": results,
        "unmapped_archetypes": sorted(
            {card.get("archetype") for card in cards if card["position"] == "QB"} - set(mapping)
        ),
        "warning": (
            "Historical archetype mapping is a declared research approximation, "
            "not an identity claim."
        ),
    }


def _moneyball(cards: list[dict[str, Any]]) -> dict[str, Any]:
    output = {}
    for position in sorted({card["position"] for card in cards}):
        group = [card for card in cards if card["position"] == position]
        if len(group) < 15:
            continue
        common = set.intersection(*(set(card["displayed_ratings"]) for card in group))
        candidates = []
        for attribute in common:
            xs = [card["displayed_ratings"][attribute] for card in group]
            ys = [card["overall"] for card in group]
            correlation = (
                statistics.correlation(xs, ys) if len(set(xs)) > 1 and len(set(ys)) > 1 else 0.0
            )
            same_ovr_ranges = []
            for ovr in set(ys):
                values = [
                    card["displayed_ratings"][attribute] for card in group if card["overall"] == ovr
                ]
                if len(values) >= 3:
                    same_ovr_ranges.append(max(values) - min(values))
            variance = statistics.mean(same_ovr_ranges) if same_ovr_ranges else 0.0
            if abs(correlation) <= 0.35 and variance >= 5:
                candidates.append(
                    {
                        "attribute": attribute,
                        "ovr_correlation": round(correlation, 6),
                        "mean_same_ovr_range": round(variance, 4),
                        "status": "DISPLAYED_OVR_INEXPENSIVE_CANDIDATE",
                    }
                )
        output[position] = sorted(
            candidates, key=lambda row: (-row["mean_same_ovr_range"], row["attribute"])
        )
    return output


def _position_descriptives(cards: list[dict[str, Any]]) -> dict[str, Any]:
    output = {}
    for position in sorted({card["position"] for card in cards}):
        group = [card for card in cards if card["position"] == position]
        common = sorted(set.intersection(*(set(card["displayed_ratings"]) for card in group)))
        attributes = {}
        for attribute in common:
            values = [card["displayed_ratings"][attribute] for card in group]
            ovrs = [card["overall"] for card in group]
            correlation = (
                statistics.correlation(values, ovrs)
                if len(set(values)) > 1 and len(set(ovrs)) > 1
                else None
            )
            same_ovr_ranges = []
            for ovr in sorted(set(ovrs)):
                level = [
                    card["displayed_ratings"][attribute] for card in group if card["overall"] == ovr
                ]
                if len(level) >= 2:
                    same_ovr_ranges.append(max(level) - min(level))
            attributes[attribute] = {
                "minimum": min(values),
                "maximum": max(values),
                "mean": round(statistics.mean(values), 6),
                "correlation_with_ovr": (
                    round(correlation, 6) if correlation is not None else None
                ),
                "mean_same_ovr_range": (
                    round(statistics.mean(same_ovr_ranges), 6) if same_ovr_ranges else None
                ),
            }
        means_by_archetype = {}
        for archetype in sorted({card.get("archetype") or "UNKNOWN" for card in group}):
            subset = [card for card in group if (card.get("archetype") or "UNKNOWN") == archetype]
            means_by_archetype[archetype] = {
                attribute: round(
                    statistics.mean(card["displayed_ratings"][attribute] for card in subset), 4
                )
                for attribute in common
            }
        means_by_ovr = {}
        for ovr in sorted({card["overall"] for card in group}):
            subset = [card for card in group if card["overall"] == ovr]
            means_by_ovr[str(ovr)] = {
                attribute: round(
                    statistics.mean(card["displayed_ratings"][attribute] for card in subset), 4
                )
                for attribute in common
            }
        adjacent_changes = {}
        levels = sorted(int(level) for level in means_by_ovr)
        for lower in levels:
            if str(lower + 1) in means_by_ovr:
                adjacent_changes[f"{lower}->{lower + 1}"] = {
                    attribute: round(
                        means_by_ovr[str(lower + 1)][attribute]
                        - means_by_ovr[str(lower)][attribute],
                        4,
                    )
                    for attribute in common
                }
        output[position] = {
            "count": len(group),
            "ovr_distribution": dict(sorted(Counter(card["overall"] for card in group).items())),
            "archetype_distribution": dict(
                sorted(Counter(card.get("archetype") or "UNKNOWN" for card in group).items())
            ),
            "attributes": attributes,
            "attribute_means_by_ovr": means_by_ovr,
            "attribute_means_by_archetype": means_by_archetype,
            "adjacent_ovr_mean_changes": adjacent_changes,
            "correlation_warning": "Descriptive relationship; not a formula weight.",
        }
    return output


def build_phase2_analysis(
    cards: list[dict[str, Any]],
    te_status: list[dict[str, Any]],
    qb_weights: dict[str, dict[str, float]],
    saturday: dict[str, Any],
) -> dict[str, Any]:
    cards = sorted(
        cards, key=lambda card: (card["position"], card["overall"], card["external_card_id"])
    )
    ordinary = [card for card in cards if not is_special(card)]
    center = _center_analysis(cards)
    boundaries = _boundaries(cards)
    practical_forms = [
        form
        for form, metrics in center["calibrations"].items()
        if metrics["within_one_accuracy"] >= 0.95
    ]
    practical_center = (
        min(
            practical_forms,
            key=lambda form: (
                center["calibrations"][form]["mae"],
                -center["calibrations"][form]["ordering_accuracy"],
                form,
            ),
        )
        if practical_forms
        else None
    )
    releases = [
        {
            "external_card_id": card["external_card_id"],
            "player": card["player_name"],
            "position": card["position"],
            "ovr": card["overall"],
            "program": card.get("program"),
            "release_date": card.get("release_date"),
            "special": is_special(card),
        }
        for card in cards
    ]
    return {
        "schema_version": 1,
        "phase": "CFB27 Population Expansion & Inherited Model Phase II",
        "population": {
            "total": len(cards),
            "ordinary": len(ordinary),
            "special": len(cards) - len(ordinary),
            "positions": dict(sorted(Counter(card["position"] for card in cards).items())),
            "ovr_range": [
                min(card["overall"] for card in cards),
                max(card["overall"] for card in cards),
            ],
            "archetypes": len({card.get("archetype") for card in cards}),
        },
        "center": center,
        "saturday": {
            "compatibility": "COMPATIBLE_SPECIAL_TUNING",
            "positive_direction_transitions": sum(
                row["positive_direction_compatible"] for row in saturday["transitions"]
            ),
            "transitions": len(saturday["transitions"]),
            "shared_absolute_boundary": saturday["shared_baseline_test"]["result"],
            "interpretation": (
                "Inherited weights explain direction of every transition but not one shared "
                "absolute special-card calibration."
            ),
        },
        "te": {
            "reproduction": te_status,
            "inheritance_result": "STABLE_HISTORICAL_ARCHITECTURE_WITH_SMALL_MODIFICATION",
            "frozen_artifacts_modified": False,
        },
        "qb": _qb_inheritance(cards, qb_weights),
        "ordinary_vs_special": _special_comparison(cards),
        "position_descriptives": _position_descriptives(cards),
        "boundaries": boundaries,
        "boundary_summary": {
            "diagnostics": len(boundaries),
            "candidates": sum(row["classification"] == "CANDIDATE_THRESHOLD" for row in boundaries),
            "supported": 0,
        },
        "practical_95": {
            "Center": practical_center,
            "TE": [row["Archetype"] for row in te_status],
        },
        "operationally_solved_98": {
            "TE": [
                row["Archetype"] for row in te_status if row.get("Operationally Solved?") == "YES"
            ]
        },
        "moneyball_preparation": _moneyball(cards),
        "release_chronology": sorted(
            releases,
            key=lambda row: (row["release_date"] or "", row["position"], row["external_card_id"]),
        ),
        "pc_evaluator": {
            "C": {
                "status": "PRACTICAL" if practical_center else "RESEARCH_ONLY",
                "calibration": practical_center or center["best_calibration"],
                "metrics": center["calibrations"][practical_center or center["best_calibration"]],
                "confidence": "MODERATE",
                "ordinary_special_warning": True,
                "archetype_handling": "residual bias reported; no separate formula promoted",
            },
            "TE": {"status": "EXISTING_FROZEN_MODELS", "models": te_status},
            "QB": {
                "status": "INHERITED_BASELINE_ONLY",
                "archetypes": _qb_inheritance(cards, qb_weights)["archetypes"],
            },
        },
        "external_source_plan": [
            {
                "priority": 1,
                "source": "Primary Madden PC extracted tunable tables",
                "need": "Authenticate archetype weights and evolution across Madden 19-21",
            },
            {
                "priority": 2,
                "source": "EA CFB27 base-roster export",
                "need": "Separate base-roster architecture from CUT card tuning",
            },
            {
                "priority": 3,
                "source": "Historical MUT/CUT card database export",
                "need": "Release chronology and cross-year special-card controls",
            },
        ],
        "chatgpt_research_targets": [
            "Locate and authenticate Table_44 Ability Progression Tunable Archetypes workbook.",
            "Recover primary Madden 16 position/archetype weight table.",
            "Explain Center archetype residuals that persist after inherited-score calibration.",
            "Validate whether promotional cards receive targeted rating inflation "
            "independent of OVR.",
            "Recover lower-OVR ordinary CFB27 cards for stronger adjacent-boundary tests.",
        ],
        "canonical_modified": False,
        "guessed_values": False,
        "access_bypass": False,
    }


def write_phase2_artifacts(directory: str | Path, analysis: dict[str, Any]) -> None:
    root = Path(directory)
    root.mkdir(parents=True, exist_ok=True)
    payloads = {
        "phase2_summary.json": analysis,
        "center_calibration_battery.json": analysis["center"],
        "saturday_special_test.json": analysis["saturday"],
        "te_inheritance_reproduction.json": analysis["te"],
        "qb_inherited_baseline.json": analysis["qb"],
        "ordinary_vs_special.json": analysis["ordinary_vs_special"],
        "position_descriptives.json": analysis["position_descriptives"],
        "boundary_analysis.json": analysis["boundaries"],
        "moneyball_preparation.json": analysis["moneyball_preparation"],
        "release_chronology.json": analysis["release_chronology"],
        "pc_evaluator_models.json": analysis["pc_evaluator"],
        "external_source_plan.json": analysis["external_source_plan"],
        "chatgpt_research_queue.json": analysis["chatgpt_research_targets"],
    }
    for name, payload in payloads.items():
        (root / name).write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
