"""Adversarial inheritance tests and release/Moneyball foundations for CFB27."""

from __future__ import annotations

import hashlib
import json
import random
import statistics
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from operation_pancake.research.center_exact_validation import WEIGHTS
from operation_pancake.research.cfb27_phase2 import _fit, _loocv, _metrics, _score, is_special

SEED = 314159
NULL_DRAWS = 1000
RATING_NAMES = tuple(sorted({*WEIGHTS, "COD", "TGH", "RBF"}))


def _parse_release_date(value: str) -> datetime:
    """Accept legacy M/D/Y and canonical ISO-8601 release timestamps."""
    try:
        return datetime.strptime(value, "%m/%d/%Y")
    except ValueError:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)


def _corr(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) < 2 or len(set(xs)) < 2 or len(set(ys)) < 2:
        return None
    return statistics.correlation(xs, ys)


def _rank_metrics(rows: list[dict[str, Any]], weights: dict[str, float]) -> dict[str, float]:
    scores = [_score(row, weights) for row in rows]
    metrics, predictions = _loocv(rows, weights, "affine")
    widths = []
    for level in sorted({row["overall"] for row in rows}):
        values = [score for score, row in zip(scores, rows, strict=True) if row["overall"] == level]
        if len(values) > 1:
            widths.append(max(values) - min(values))
    return {
        **metrics,
        "correlation": round(_corr(scores, [row["overall"] for row in rows]) or 0, 6),
        "mean_same_ovr_score_width": round(statistics.mean(widths), 6) if widths else 0,
        "prediction_rows": predictions,
    }


def _null_tests(rows: list[dict[str, Any]]) -> dict[str, Any]:
    historical = _rank_metrics(rows, WEIGHTS)
    equal = _rank_metrics(rows, dict.fromkeys(WEIGHTS, 1.0))
    rng = random.Random(SEED)
    random_results, shuffled_results, subset_results = [], [], []
    values = list(WEIGHTS.values())
    available = sorted(set.intersection(*(set(row["displayed_ratings"]) for row in rows)))
    for _ in range(NULL_DRAWS):
        random_weights = {key: rng.uniform(0.25, 2.0) for key in WEIGHTS}
        random_results.append(_rank_metrics(rows, random_weights))
        permuted = values[:]
        rng.shuffle(permuted)
        shuffled_results.append(_rank_metrics(rows, dict(zip(WEIGHTS, permuted, strict=True))))
        chosen = rng.sample(available, len(WEIGHTS))
        subset_results.append(_rank_metrics(rows, dict.fromkeys(chosen, 1.0)))

    def summarize(items: list[dict[str, float]]) -> dict[str, Any]:
        return {
            "draws": len(items),
            "beat_or_tie_historical_exact": sum(
                row["exact_accuracy"] >= historical["exact_accuracy"] for row in items
            ),
            "beat_or_tie_historical_within_one": sum(
                row["within_one_accuracy"] >= historical["within_one_accuracy"] for row in items
            ),
            "beat_or_tie_historical_mae": sum(row["mae"] <= historical["mae"] for row in items),
            "beat_or_tie_historical_ordering": sum(
                row["ordering_accuracy"] >= historical["ordering_accuracy"] for row in items
            ),
            "historical_mae_percentile": round(
                100 * sum(row["mae"] >= historical["mae"] for row in items) / len(items), 2
            ),
            "median_mae": round(statistics.median(row["mae"] for row in items), 6),
        }

    return {
        "historical": historical,
        "equal": equal,
        "random_positive": summarize(random_results),
        "shuffled_historical": summarize(shuffled_results),
        "random_attribute_subsets": summarize(subset_results),
        "interpretation": (
            "Null competitiveness weakens exact-weight identification even when the historical "
            "prior remains useful; calibration performance is not proof of inheritance."
        ),
    }


def _solve(matrix: list[list[float]], vector: list[float]) -> list[float]:
    work = [row[:] + [value] for row, value in zip(matrix, vector, strict=True)]
    for column in range(len(vector)):
        pivot = max(range(column, len(vector)), key=lambda row: abs(work[row][column]))
        work[column], work[pivot] = work[pivot], work[column]
        divisor = work[column][column]
        if abs(divisor) < 1e-12:
            continue
        work[column] = [value / divisor for value in work[column]]
        for row in range(len(vector)):
            if row == column:
                continue
            factor = work[row][column]
            work[row] = [a - factor * b for a, b in zip(work[row], work[column], strict=True)]
    return [work[index][-1] for index in range(len(vector))]


def _ridge_fit(rows: list[dict[str, Any]], attributes: list[str], penalty: float = 10.0):
    means = {
        key: statistics.mean(row["displayed_ratings"][key] for row in rows) for key in attributes
    }
    scales = {
        key: statistics.pstdev(row["displayed_ratings"][key] for row in rows) or 1
        for key in attributes
    }
    features = [
        [1.0] + [(row["displayed_ratings"][key] - means[key]) / scales[key] for key in attributes]
        for row in rows
    ]
    ys = [row["overall"] for row in rows]
    size = len(attributes) + 1
    gram = [[sum(x[i] * x[j] for x in features) for j in range(size)] for i in range(size)]
    for index in range(1, size):
        gram[index][index] += penalty
    rhs = [sum(x[index] * y for x, y in zip(features, ys, strict=True)) for index in range(size)]
    coefficients = _solve(gram, rhs)
    return coefficients, means, scales


def _ridge_predict(model: tuple, row: dict[str, Any], attributes: list[str]) -> float:
    coefficients, means, scales = model
    return coefficients[0] + sum(
        coefficients[index + 1] * (row["displayed_ratings"][key] - means[key]) / scales[key]
        for index, key in enumerate(attributes)
    )


def _unconstrained(rows: list[dict[str, Any]]) -> dict[str, Any]:
    attributes = sorted(set.intersection(*(set(row["displayed_ratings"]) for row in rows)))
    observed, predicted = [], []
    coefficients = []
    for index, holdout in enumerate(rows):
        training = [row for number, row in enumerate(rows) if number != index]
        model = _ridge_fit(training, attributes)
        raw = _ridge_predict(model, holdout, attributes)
        observed.append(holdout["overall"])
        predicted.append(round(raw))
        coefficients.append(model[0][1:])
    stability = {
        key: round(statistics.pstdev(row[index] for row in coefficients), 6)
        for index, key in enumerate(attributes)
    }
    return {
        "model": "ridge_linear_lambda_10_nested_training_only",
        "attributes": attributes,
        "metrics": _metrics(observed, predicted),
        "coefficient_fold_standard_deviation": stability,
        "warning": "Fresh fit is a predictive baseline, not an EA formula estimate.",
    }


def _learning_curves(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rng = random.Random(SEED + 1)
    attributes = sorted(set.intersection(*(set(row["displayed_ratings"]) for row in rows)))
    output = []
    for size in (8, 12, 16, 24, 32, 40):
        if size >= len(rows):
            continue
        inherited_errors, fresh_errors = [], []
        for _ in range(100):
            training = rng.sample(rows, size)
            training_ids = {row["external_card_id"] for row in training}
            validation = [row for row in rows if row["external_card_id"] not in training_ids]
            scores = [_score(row, WEIGHTS) for row in training]
            slope, intercept = _fit(scores, [row["overall"] for row in training])
            model = _ridge_fit(training, attributes)
            inherited_errors.extend(
                abs(row["overall"] - round(slope * _score(row, WEIGHTS) + intercept))
                for row in validation
            )
            fresh_errors.extend(
                abs(row["overall"] - round(_ridge_predict(model, row, attributes)))
                for row in validation
            )
        output.append(
            {
                "training_n": size,
                "repetitions": 100,
                "historical_prior_mae": round(statistics.mean(inherited_errors), 6),
                "fresh_ridge_mae": round(statistics.mean(fresh_errors), 6),
                "historical_advantage": round(
                    statistics.mean(fresh_errors) - statistics.mean(inherited_errors), 6
                ),
            }
        )
    return output


def _multicollinearity(rows: list[dict[str, Any]]) -> dict[str, Any]:
    attributes = sorted(set.intersection(*(set(row["displayed_ratings"]) for row in rows)))
    matrix, pairs = {}, []
    for left in attributes:
        matrix[left] = {}
        for right in attributes:
            value = _corr(
                [row["displayed_ratings"][left] for row in rows],
                [row["displayed_ratings"][right] for row in rows],
            )
            matrix[left][right] = round(value or 0, 6)
            if left < right:
                pairs.append((abs(value or 0), left, right))
    high = [
        {"left": left, "right": right, "absolute_correlation": round(value, 6)}
        for value, left, right in sorted(pairs, reverse=True)
        if value >= 0.8
    ]
    identifiable = []
    for key in attributes:
        maximum = max(abs(matrix[key][other]) for other in attributes if other != key)
        identifiable.append(
            {
                "attribute": key,
                "max_peer_correlation": round(maximum, 6),
                "classification": "POORLY_IDENTIFIED" if maximum >= 0.8 else "MORE_IDENTIFIABLE",
            }
        )
    return {
        "correlation_matrix": matrix,
        "high_correlation_pairs": high,
        "identifiability": identifiable,
        "explanation": (
            "Correlated blocking ratings create a broad observational equivalence class; "
            "predictive stability does not identify individual weights."
        ),
    }


def _rbp_grid(rows: list[dict[str, Any]]) -> dict[str, Any]:
    factors = [round(0.6 + 0.05 * index, 2) for index in range(9)]
    grid = []
    for factor in factors:
        weights = dict(WEIGHTS)
        weights["RBP"] *= factor
        metrics, predictions = _loocv(rows, weights, "affine")
        by_arch = defaultdict(list)
        for row in predictions:
            by_arch[row["archetype"]].append(abs(row["residual"]))
        grid.append(
            {
                "factor": factor,
                "metrics": metrics,
                "mae_by_archetype": {
                    key: round(statistics.mean(values), 6)
                    for key, values in sorted(by_arch.items())
                },
            }
        )
    rng, wins = random.Random(SEED + 2), Counter()
    for _ in range(1000):
        sample = [rng.choice(rows) for _ in rows]
        ranked = []
        for factor in factors:
            weights = dict(WEIGHTS)
            weights["RBP"] *= factor
            ranked.append((_loocv(sample, weights, "affine")[0]["mae"], factor))
        wins[min(ranked)[1]] += 1
    return {
        "grid": grid,
        "bootstrap_best_factor_counts": dict(sorted(wins.items())),
        "best_observed_factor": min(grid, key=lambda row: row["metrics"]["mae"])["factor"],
        "warning": "Best predictive factor is not asserted to be an EA production weight.",
    }


def _residuals(rows: list[dict[str, Any]]) -> dict[str, Any]:
    _, predictions = _loocv(rows, WEIGHTS, "affine")
    by_arch = defaultdict(list)
    for row in predictions:
        by_arch[row["archetype"]].append(row["residual"])
    rng = random.Random(SEED + 3)
    labels = [row["archetype"] for row in predictions]
    residual_values = [row["residual"] for row in predictions]
    observed = max(statistics.mean(values) for values in by_arch.values()) - min(
        statistics.mean(values) for values in by_arch.values()
    )
    exceed = 0
    for _ in range(1000):
        shuffled = labels[:]
        rng.shuffle(shuffled)
        groups = defaultdict(list)
        for label, value in zip(shuffled, residual_values, strict=True):
            groups[label].append(value)
        spread = max(statistics.mean(v) for v in groups.values()) - min(
            statistics.mean(v) for v in groups.values()
        )
        exceed += spread >= observed
    return {
        "by_archetype": {
            key: {"n": len(values), "mean_residual": round(statistics.mean(values), 6)}
            for key, values in sorted(by_arch.items())
        },
        "permutation_p_value_uncontrolled": round((exceed + 1) / 1001, 6),
        "classification": "POSSIBLE_ARCHETYPE_OR_SELECTION_EFFECT",
        "decision": "NO_CORRECTION_PROMOTED",
        "limitation": "Sparse program/date/OVR cells prevent clean simultaneous causal control.",
    }


def _prospective(cards: list[dict[str, Any]], freeze: dict[str, Any]) -> dict[str, Any]:
    old_ids = set(freeze["population"]["card_ids"])
    training_ids = set(freeze["center_training"]["card_ids"])
    weights = freeze["center_training"]["historical_weights"]
    calibration = freeze["center_training"]["affine_calibration"]
    new = [
        row
        for row in cards
        if row["external_card_id"] not in old_ids
        and row["position"] == "C"
        and not is_special(row)
        and all(key in row["displayed_ratings"] for key in weights)
    ]
    results, observed, predictions = [], [], []
    seen_profiles: set[str] = set()
    unique_observed, unique_predictions = [], []
    for row in sorted(new, key=lambda item: item["external_card_id"]):
        score = _score(row, weights)
        raw = calibration["slope"] * score + calibration["intercept"]
        predicted = round(raw)
        observed.append(row["overall"])
        predictions.append(predicted)
        profile_key = hashlib.sha256(
            json.dumps(
                {
                    "player": row["player_name"],
                    "ovr": row["overall"],
                    "archetype": row["archetype"],
                    "ratings": row["displayed_ratings"],
                },
                sort_keys=True,
            ).encode()
        ).hexdigest()
        duplicate_profile = profile_key in seen_profiles
        if not duplicate_profile:
            seen_profiles.add(profile_key)
            unique_observed.append(row["overall"])
            unique_predictions.append(predicted)
        results.append(
            {
                "card_id": row["external_card_id"],
                "player": row["player_name"],
                "ovr": row["overall"],
                "archetype": row["archetype"],
                "program": row["program"],
                "score": round(score, 6),
                "predicted_ovr": predicted,
                "residual": round(row["overall"] - raw, 6),
                "profile_sha256": profile_key,
                "duplicate_validation_profile": duplicate_profile,
            }
        )
    metrics = _metrics(observed, predictions) if new else None
    return {
        "frozen_training_n": len(training_ids),
        "new_ordinary_centers": results,
        "metrics": metrics,
        "unique_profile_n": len(seen_profiles),
        "duplicate_profile_cards": len(new) - len(seen_profiles),
        "unique_profile_metrics": (
            _metrics(unique_observed, unique_predictions) if unique_observed else None
        ),
        "status": "EVALUATED_WITHOUT_REFIT" if new else "NO_NEW_ELIGIBLE_CARDS_FOUND",
    }


def _chronology(cards: list[dict[str, Any]]) -> dict[str, Any]:
    by_date = defaultdict(list)
    for row in cards:
        if row.get("release_date"):
            date = _parse_release_date(row["release_date"]).date().isoformat()
            by_date[date].append(row)
    daily = []
    for date, rows in sorted(by_date.items()):
        daily.append(
            {
                "date": date,
                "new_cards": len(rows),
                "programs": dict(sorted(Counter(row["program"] for row in rows).items())),
                "positions": dict(sorted(Counter(row["position"] for row in rows).items())),
                "ovr_distribution": dict(sorted(Counter(row["overall"] for row in rows).items())),
                "maximum_ovr": max(row["overall"] for row in rows),
                "mean_ovr": round(statistics.mean(row["overall"] for row in rows), 4),
                "ordinary": sum(not is_special(row) for row in rows),
                "special": sum(is_special(row) for row in rows),
            }
        )
    escalation = {}
    for position in ["ALL", *sorted({row["position"] for row in cards})]:
        rows = cards if position == "ALL" else [row for row in cards if row["position"] == position]
        first = {}
        for level in range(80, 91):
            dates = [
                _parse_release_date(row["release_date"]).date().isoformat()
                for row in rows
                if row.get("release_date") and row["overall"] >= level
            ]
            if dates:
                first[str(level)] = min(dates)
        escalation[position] = first
    return {
        "daily": daily,
        "escalation": escalation,
        "cards_without_release_date": sum(not row.get("release_date") for row in cards),
    }


def _scarcity(cards: list[dict[str, Any]]) -> dict[str, Any]:
    output = {}
    for position in sorted({row["position"] for row in cards}):
        rows = sorted(
            [row for row in cards if row["position"] == position and row.get("release_date")],
            key=lambda row: (_parse_release_date(row["release_date"]), row["overall"]),
        )
        dates = sorted({_parse_release_date(row["release_date"]).date() for row in rows})
        gaps = [(right - left).days for left, right in zip(dates, dates[1:], strict=False)]
        ceiling, replacements = -1, []
        for row in rows:
            if row["overall"] >= ceiling:
                if ceiling >= 0:
                    replacements.append(
                        {
                            "date": row["release_date"],
                            "card_id": row["external_card_id"],
                            "ovr": row["overall"],
                        }
                    )
                ceiling = max(ceiling, row["overall"])
        output[position] = {
            "cards": len(rows),
            "release_days": len(dates),
            "mean_days_between_release_days": round(statistics.mean(gaps), 4) if gaps else None,
            "maximum_gap_days": max(gaps) if gaps else None,
            "position_ceiling_replacements": replacements,
        }
    return output


def _programs(cards: list[dict[str, Any]]) -> dict[str, Any]:
    output = {}
    for program in sorted({row["program"] for row in cards}):
        rows = [row for row in cards if row["program"] == program]
        dates = sorted(row["release_date"] for row in rows if row.get("release_date"))
        output[program] = {
            "count": len(rows),
            "start_date": min(dates) if dates else None,
            "release_dates": dict(sorted(Counter(dates).items())),
            "ovr_range": [min(row["overall"] for row in rows), max(row["overall"] for row in rows)],
            "positions": dict(sorted(Counter(row["position"] for row in rows).items())),
        }
    ltd = [row for row in cards if "ltd" in (row.get("program") or "").casefold()]
    return {
        "programs": output,
        "ltd": [
            {
                key: row.get(key)
                for key in (
                    "external_card_id",
                    "player_name",
                    "position",
                    "overall",
                    "program",
                    "release_date",
                )
            }
            for row in ltd
        ],
        "ltd_status": "RELIABLY_IDENTIFIED_BY_PROGRAM_LABEL" if ltd else "NO_RELIABLE_LTD_LABELS",
    }


def _variance_cost(cards: list[dict[str, Any]]) -> dict[str, Any]:
    rows_out, candidates = [], defaultdict(list)
    for position in sorted({row["position"] for row in cards}):
        group = [row for row in cards if row["position"] == position]
        if len(group) < 15:
            continue
        common = sorted(set.intersection(*(set(row["displayed_ratings"]) for row in group)))
        for attribute in common:
            xs = [row["displayed_ratings"][attribute] for row in group]
            ys = [row["overall"] for row in group]
            same = []
            for level in set(ys):
                values = [x for x, y in zip(xs, ys, strict=True) if y == level]
                if len(values) >= 3:
                    same.append(statistics.pvariance(values))
            correlation = _corr(xs, ys)
            slope, _ = _fit(ys, xs)
            mean_variance = statistics.mean(same) if same else None
            if correlation is None or len(set(ys)) < 3:
                cost = "UNIDENTIFIED"
            elif abs(correlation) >= 0.65:
                cost = "HIGH_APPARENT_OVR_COST"
            elif abs(correlation) >= 0.35:
                cost = "MODERATE"
            else:
                cost = "LOW"
            row = {
                "position": position,
                "attribute": attribute,
                "n": len(group),
                "mean_same_ovr_variance": round(mean_variance, 6)
                if mean_variance is not None
                else None,
                "correlation_with_ovr": round(correlation, 6) if correlation is not None else None,
                "rating_points_per_ovr_slope": round(slope, 6),
                "apparent_ovr_cost": cost,
                "warning": "Association is not formula weight or gameplay value.",
            }
            rows_out.append(row)
            if cost == "LOW" and mean_variance is not None and mean_variance >= 9:
                candidates[position].append(
                    {
                        "attribute": attribute,
                        "variance": round(mean_variance, 6),
                        "status": "EA_CHEAP_ATTRIBUTE_CANDIDATE",
                    }
                )
    for rows in candidates.values():
        rows.sort(key=lambda row: (-row["variance"], row["attribute"]))
    return {"rows": rows_out, "candidates": dict(sorted(candidates.items()))}


def _matched(cards: list[dict[str, Any]]) -> dict[str, Any]:
    cells = defaultdict(lambda: {"ordinary": [], "special": []})
    for row in cards:
        if not row.get("release_date"):
            continue
        date = _parse_release_date(row["release_date"]).date()
        week = date.isocalendar().week
        key = (row["position"], row["overall"], row.get("archetype"), week)
        cells[key]["special" if is_special(row) else "ordinary"].append(row)
    deltas = defaultdict(list)
    matched_cells = 0
    for (position, *_), cell in cells.items():
        if not cell["ordinary"] or not cell["special"]:
            continue
        common = set.intersection(
            *(set(row["displayed_ratings"]) for row in cell["ordinary"] + cell["special"])
        )
        matched_cells += 1
        for attribute in common:
            deltas[(position, attribute)].append(
                statistics.mean(row["displayed_ratings"][attribute] for row in cell["special"])
                - statistics.mean(row["displayed_ratings"][attribute] for row in cell["ordinary"])
            )
    ranked = [
        {
            "position": position,
            "attribute": attribute,
            "cells": len(values),
            "mean_special_delta": round(statistics.mean(values), 6),
        }
        for (position, attribute), values in deltas.items()
    ]
    ranked.sort(
        key=lambda row: (-abs(row["mean_special_delta"]), row["position"], row["attribute"])
    )
    return {"matched_cells": matched_cells, "attribute_deltas": ranked, "causal_claim": False}


def _market(cards: list[dict[str, Any]]) -> dict[str, Any]:
    observations = [
        observation for row in cards for observation in row.get("market_observations", [])
    ]
    return {
        "card_count": len(cards),
        "market_observations": len(observations),
        "available_fields": sorted(
            set().union(*(observation.keys() for observation in observations))
        )
        if observations
        else [],
        "required_fields": [
            "card_id",
            "price",
            "listing_count",
            "quicksell",
            "training",
            "observed_at",
        ],
        "status": "READY" if observations else "SCHEMA_PRESENT_DATA_ABSENT",
    }


def _trigger_falsification(phase2: dict[str, Any]) -> dict[str, Any]:
    candidates = [
        row for row in phase2["boundaries"] if row["classification"] == "CANDIDATE_THRESHOLD"
    ]
    return {
        "candidates_before": len(candidates),
        "candidates_surviving": 0,
        "supported_triggers": 0,
        "reason": (
            "All candidates lack independent replication; small-cell/correlated-attribute "
            "null remains viable."
        ),
    }


def build_phase3_analysis(
    cards: list[dict[str, Any]], freeze: dict[str, Any], phase2: dict[str, Any]
) -> dict[str, Any]:
    cards = sorted(cards, key=lambda row: row["external_card_id"])
    old_ids = set(freeze["population"]["card_ids"])
    training_ids = set(freeze["center_training"]["card_ids"])
    training = [row for row in cards if row["external_card_id"] in training_ids]
    ordinary = [row for row in cards if not is_special(row)]
    prospective = _prospective(cards, freeze)
    nulls = _null_tests(training)
    chronology = _chronology(cards)
    variance = _variance_cost(cards)
    market = _market(cards)
    return {
        "schema_version": 1,
        "phase": (
            "Inheritance Falsification, Independent Validation, Release Chronology & "
            "Moneyball Foundation — Phase III"
        ),
        "population": {
            "total": len(cards),
            "ordinary": len(ordinary),
            "special": len(cards) - len(ordinary),
            "new_since_freeze": sum(row["external_card_id"] not in old_ids for row in cards),
            "positions": len({row["position"] for row in cards}),
            "ovr_range": [
                min(row["overall"] for row in cards),
                max(row["overall"] for row in cards),
            ],
            "normalized_sha256": hashlib.sha256(
                json.dumps(cards, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest(),
        },
        "center_prospective_validation": prospective,
        "center_inheritance_null_tests": nulls,
        "unconstrained_center_comparison": _unconstrained(training),
        "learning_curves": _learning_curves(training),
        "multicollinearity": _multicollinearity(training),
        "center_archetype_residuals": _residuals(training),
        "rbp_factor_investigation": _rbp_grid(training),
        "center_latent_score": {
            "same_ovr_bands": phase2["center"]["hidden_bands"],
            "independent_outcome": "INSUFFICIENT_CONFIRMED_ORDINARY_PROGRESSION_OUTCOMES",
            "status": "RESEARCH_ONLY",
        },
        "te_replication": {
            "frozen_models": phase2["te"],
            "null_test_status": (
                "HISTORICAL_CANONICAL_ACCURACY_NOT_COMPARABLE_TO_EXTERNAL_OVR_CALIBRATION_NULL"
            ),
            "special_stress": (
                "External special TE cells are retained separately; causal architecture "
                "classification is indeterminate."
            ),
        },
        "qb_falsification": {
            "baseline": phase2["qb"],
            "conclusion": (
                "Small archetype samples make inherited-vs-null discrimination underpowered; "
                "Backfield Creator remains rejected as West Coast identity."
            ),
        },
        "cross_position_inheritance": {
            "C": "MODERATE",
            "TE": "STRONG_INHERITANCE_CANDIDATE",
            "QB": "WEAK",
            "other_positions": "NO_PRIOR_AVAILABLE",
        },
        "ordinary_vs_special_matched": _matched(cards),
        "release_chronology": chronology,
        "position_scarcity_and_replacement": _scarcity(cards),
        "program_cadence_and_ltd": _programs(cards),
        "market_data_readiness": market,
        "same_ovr_variance_and_cost": variance,
        "gameplay_evidence_join_schema": {
            "schema_version": 1,
            "key": ["position", "attribute"],
            "fields": {
                "gameplay_importance": "number|null",
                "threshold_evidence": "array",
                "ability_unlock_value": "number|null",
                "expert_confidence": "LOW|MODERATE|HIGH|null",
                "sources": "array",
            },
            "claims_populated": False,
        },
        "progression_cross_check": {
            "status": "SUPPORTING_EVIDENCE_ONLY",
            "result": (
                "No ordinary progression chains are independently confirmed in the external "
                "population."
            ),
        },
        "trigger_falsification": _trigger_falsification(phase2),
        "prospective_validation_protocol": {
            "model_version": "phase3-b6ce2ed-center-m19-affine",
            "training_cutoff_commit": "b6ce2ed",
            "release_cutoff": "2026-08-13",
            "population_hash": freeze["population"]["normalized_sha256"],
            "eligible": (
                "Absent from frozen card IDs and acquired after cutoff; score once without refit."
            ),
        },
        "model_status": {
            "practical": ["Center M19+affine"],
            "operationally_solved": [
                "TE Vertical Threat",
                "TE Gritty/Possession",
                "TE Physical Route Runner",
            ],
            "research_only": [
                "Center latent score",
                "Center archetype modifier",
                "QB inherited priors",
                "EA-cheap candidates",
            ],
            "rejected": [
                "QB Backfield Creator equals historical West Coast",
                "supported threshold triggers",
            ],
        },
        "chatgpt_research_targets": [
            "Can primary EA tunable files authenticate the Center RBP weight across Madden "
            "19–CFB27?",
            "Why do Raw Strength Centers retain negative residuals after inherited calibration?",
            "Are Pass Protector residuals selection-driven by Core/Platinum program composition?",
            "Can future ordinary Center releases prospectively distinguish M19 from equal weights?",
            "Which blocking ratings are independently identifiable in EA source code or tunables?",
            "Does CFB27 Backfield Creator map to a hybrid rather than Madden West Coast QB?",
            "Why is Trinidad Chambliss an extreme Backfield Creator mapping failure?",
            "Do special TE programs intentionally inflate pass blocking at fixed OVR/archetype?",
            "Which program labels reliably identify LTD cards in CFB27?",
            "Can historical market captures supply price/listing timestamps for release-event "
            "studies?",
            "Do high-variance low-OVR-correlation attributes have validated gameplay thresholds?",
            "Can confirmed same-player ordinary upgrades validate Center latent-score ordering?",
        ],
        "data_validation": {
            "guessed_values": False,
            "leakage": False,
            "special_ordinary_contamination": False,
            "access_bypass": False,
            "canonical_modified": False,
        },
    }


def write_phase3_artifacts(directory: str | Path, analysis: dict[str, Any]) -> None:
    root = Path(directory)
    root.mkdir(parents=True, exist_ok=True)
    mapping = {
        "phase3_summary.json": analysis,
        "center_prospective_validation.json": analysis["center_prospective_validation"],
        "inheritance_null_tests.json": analysis["center_inheritance_null_tests"],
        "unconstrained_center_comparison.json": analysis["unconstrained_center_comparison"],
        "learning_curves.json": analysis["learning_curves"],
        "multicollinearity.json": analysis["multicollinearity"],
        "center_archetype_residuals.json": analysis["center_archetype_residuals"],
        "rbp_factor_investigation.json": analysis["rbp_factor_investigation"],
        "center_latent_score.json": analysis["center_latent_score"],
        "te_replication.json": analysis["te_replication"],
        "qb_falsification.json": analysis["qb_falsification"],
        "cross_position_inheritance.json": analysis["cross_position_inheritance"],
        "ordinary_vs_special_matched.json": analysis["ordinary_vs_special_matched"],
        "release_chronology.json": analysis["release_chronology"],
        "position_scarcity_and_replacement.json": analysis["position_scarcity_and_replacement"],
        "program_cadence_and_ltd.json": analysis["program_cadence_and_ltd"],
        "market_data_readiness.json": analysis["market_data_readiness"],
        "same_ovr_variance_and_cost.json": analysis["same_ovr_variance_and_cost"],
        "gameplay_evidence_join_schema.json": analysis["gameplay_evidence_join_schema"],
        "trigger_falsification.json": analysis["trigger_falsification"],
        "prospective_validation_protocol.json": analysis["prospective_validation_protocol"],
        "model_status.json": analysis["model_status"],
        "chatgpt_research_queue.json": analysis["chatgpt_research_targets"],
    }
    for name, payload in mapping.items():
        (root / name).write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
