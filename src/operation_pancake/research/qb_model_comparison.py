"""Interpretable held-out comparison of QB formula architectures A-D."""

from __future__ import annotations

import csv
import json
import math
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from statistics import fmean
from typing import Any

from operation_pancake.research.qb_formula_phase import QB_RATING_FIELDS, QBObservation

RIDGE_PENALTY = 1.0
COLLINEAR_THRESHOLD = 0.85
ARCHITECTURES = {
    "A": "Universal",
    "B": "Archetype Specific",
    "C": "Shared Core + Archetype Modifier",
    "D": "Shared Weights + Archetype Thresholds",
}


def _round_ovr(value: float) -> int:
    return math.floor(value + 0.5)


@dataclass(frozen=True, slots=True)
class LinearScoreModel:
    """Nonnegative ridge-weighted score on standardized QB ratings."""

    means: tuple[float, ...]
    scales: tuple[float, ...]
    weights: tuple[float, ...]
    intercept: float

    def score(self, observation: QBObservation) -> float:
        return self.intercept + sum(
            weight * ((rating - mean) / scale)
            for rating, mean, scale, weight in zip(
                observation.ratings,
                self.means,
                self.scales,
                self.weights,
                strict=True,
            )
        )

    def parameters(self) -> dict[str, Any]:
        return {
            "intercept": round(self.intercept, 8),
            "standardization_means": dict(zip(QB_RATING_FIELDS, self.means, strict=True)),
            "standardization_scales": dict(zip(QB_RATING_FIELDS, self.scales, strict=True)),
            "standardized_nonnegative_weights": dict(
                zip(QB_RATING_FIELDS, self.weights, strict=True)
            ),
        }


def _fit_linear(observations: list[QBObservation]) -> LinearScoreModel:
    if len(observations) < 2:
        raise ValueError("At least two fitting observations are required.")
    columns = list(zip(*(observation.ratings for observation in observations), strict=True))
    means = tuple(fmean(column) for column in columns)
    scales = tuple(
        math.sqrt(fmean((value - mean) ** 2 for value in column)) or 1.0
        for column, mean in zip(columns, means, strict=True)
    )
    x = [
        tuple(
            (value - mean) / scale
            for value, mean, scale in zip(observation.ratings, means, scales, strict=True)
        )
        for observation in observations
    ]
    y = [float(observation.overall) for observation in observations]
    intercept = fmean(y)
    weights = [0.0] * len(QB_RATING_FIELDS)
    predictions = [intercept] * len(observations)

    for _ in range(1000):
        largest_change = 0.0
        for index in range(len(weights)):
            old = weights[index]
            partial = [
                target - (prediction - old * row[index])
                for target, prediction, row in zip(y, predictions, x, strict=True)
            ]
            numerator = sum(row[index] * residual for row, residual in zip(x, partial, strict=True))
            denominator = sum(row[index] ** 2 for row in x) + RIDGE_PENALTY
            new = max(0.0, numerator / denominator)
            delta = new - old
            if delta:
                predictions = [
                    prediction + delta * row[index]
                    for prediction, row in zip(predictions, x, strict=True)
                ]
            weights[index] = new
            largest_change = max(largest_change, abs(delta))
        intercept_delta = fmean(
            target - prediction for target, prediction in zip(y, predictions, strict=True)
        )
        intercept += intercept_delta
        predictions = [prediction + intercept_delta for prediction in predictions]
        if max(largest_change, abs(intercept_delta)) < 1e-10:
            break
    return LinearScoreModel(means, scales, tuple(weights), intercept)


class ArchitectureModel:
    """Common prediction and parameter interface for architectures A-D."""

    def __init__(self, architecture: str, models: dict[str, LinearScoreModel], **extra: Any):
        self.architecture = architecture
        self.models = models
        self.extra = extra

    def score(self, observation: QBObservation) -> float | None:
        if self.architecture == "A":
            return self.models["shared"].score(observation)
        if self.architecture == "B":
            model = self.models.get(observation.archetype)
            return None if model is None else model.score(observation)
        base = self.models["shared"].score(observation)
        if self.architecture == "C":
            return base + self.extra["modifiers"].get(observation.archetype, 0.0)
        calibration = self.extra["calibrations"].get(observation.archetype)
        return base if calibration is None else calibration[0] + calibration[1] * base

    def predict(self, observation: QBObservation) -> int | None:
        score = self.score(observation)
        return None if score is None else _round_ovr(score)

    def parameters(self) -> dict[str, Any]:
        result = {name: model.parameters() for name, model in sorted(self.models.items())}
        result.update(self.extra)
        return result


def fit_architecture(architecture: str, fit: list[QBObservation]) -> ArchitectureModel:
    """Fit one architecture using fitting-partition observations only."""
    if architecture not in ARCHITECTURES:
        raise KeyError(f"Unknown architecture: {architecture}")
    if any(observation.analysis_partition != "fit" for observation in fit):
        raise ValueError("Model fitting accepts only the fit partition.")
    if architecture == "A":
        return ArchitectureModel("A", {"shared": _fit_linear(fit)})
    if architecture == "B":
        groups: dict[str, list[QBObservation]] = defaultdict(list)
        for observation in fit:
            groups[observation.archetype].append(observation)
        models = {
            archetype: _fit_linear(cards)
            for archetype, cards in sorted(groups.items())
            if len(cards) >= 2
        }
        return ArchitectureModel("B", models, data_limited_archetypes=["Pure Runner"])

    shared = _fit_linear(fit)
    if architecture == "C":
        residuals: dict[str, list[float]] = defaultdict(list)
        for observation in fit:
            residuals[observation.archetype].append(observation.overall - shared.score(observation))
        modifiers = {name: fmean(values) for name, values in sorted(residuals.items())}
        return ArchitectureModel("C", {"shared": shared}, modifiers=modifiers)

    calibrations: dict[str, tuple[float, float]] = {}
    groups: dict[str, list[QBObservation]] = defaultdict(list)
    for observation in fit:
        groups[observation.archetype].append(observation)
    for archetype, cards in sorted(groups.items()):
        if len(cards) < 3:
            continue
        scores = [shared.score(card) for card in cards]
        targets = [card.overall for card in cards]
        score_mean = fmean(scores)
        target_mean = fmean(targets)
        denominator = sum((score - score_mean) ** 2 for score in scores) + RIDGE_PENALTY
        slope = max(
            0.0,
            sum(
                (score - score_mean) * (target - target_mean)
                for score, target in zip(scores, targets, strict=True)
            )
            / denominator,
        )
        calibrations[archetype] = (target_mean - slope * score_mean, slope)
    return ArchitectureModel("D", {"shared": shared}, calibrations=calibrations)


def _metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    usable = [row for row in rows if row["predicted_ovr"] is not None]
    if not usable:
        return {
            "count": 0,
            "exact_accuracy": None,
            "within_one_accuracy": None,
            "mean_absolute_error": None,
            "maximum_error": None,
            "mean_signed_residual": None,
        }
    errors = [abs(row["residual"]) for row in usable]
    return {
        "count": len(usable),
        "exact_accuracy": round(sum(error == 0 for error in errors) / len(errors), 6),
        "within_one_accuracy": round(sum(error <= 1 for error in errors) / len(errors), 6),
        "mean_absolute_error": round(fmean(errors), 6),
        "maximum_error": max(errors),
        "mean_signed_residual": round(fmean(row["residual"] for row in usable), 6),
    }


def _predictions(
    model: ArchitectureModel, observations: list[QBObservation]
) -> list[dict[str, Any]]:
    rows = []
    for observation in observations:
        score = model.score(observation)
        predicted = None if score is None else _round_ovr(score)
        rows.append(
            {
                "architecture": model.architecture,
                "qb_id": observation.qb_id,
                "player": observation.player,
                "archetype": observation.archetype,
                "actual_ovr": observation.overall,
                "latent_score": None if score is None else round(score, 8),
                "predicted_ovr": predicted,
                "residual": None if predicted is None else predicted - observation.overall,
                "analysis_partition": observation.analysis_partition,
            }
        )
    return rows


def _breakdowns(rows: list[dict[str, Any]], key: str) -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[str(row[key])].append(row)
    return {name: _metrics(group) for name, group in sorted(groups.items())}


def _cross_ovr(
    architecture: str, fit: list[QBObservation]
) -> tuple[list[dict[str, Any]], list[ArchitectureModel]]:
    rows: list[dict[str, Any]] = []
    folds: list[ArchitectureModel] = []
    for level in sorted({observation.overall for observation in fit}):
        validation = [observation for observation in fit if observation.overall == level]
        blocked_players = {observation.player.casefold() for observation in validation}
        blocked_profiles = {observation.unique_profile_key for observation in validation}
        training = [
            observation
            for observation in fit
            if observation.overall != level
            and observation.player.casefold() not in blocked_players
            and observation.unique_profile_key not in blocked_profiles
        ]
        model = fit_architecture(architecture, training)
        folds.append(model)
        for row in _predictions(model, validation):
            row["validation_ovr"] = level
            row["training_count"] = len(training)
            rows.append(row)
    return rows, folds


def _pearson(left: list[int], right: list[int]) -> float | None:
    lm, rm = fmean(left), fmean(right)
    den = math.sqrt(sum((x - lm) ** 2 for x in left) * sum((y - rm) ** 2 for y in right))
    return (
        None
        if den == 0
        else sum((x - lm) * (y - rm) for x, y in zip(left, right, strict=True)) / den
    )


def _stability(
    architecture: str, folds: list[ArchitectureModel], fit: list[QBObservation]
) -> dict[str, Any]:
    weight_sets = []
    for model in folds:
        candidate = model.models.get("shared")
        if candidate is not None:
            weight_sets.append(candidate.weights)

    def summarize(sets: list[tuple[float, ...]]) -> dict[str, Any]:
        fields = {}
        for index, field in enumerate(QB_RATING_FIELDS):
            values = [weights[index] for weights in sets]
            value_mean = None if not values else fmean(values)
            fields[field] = {
                "fold_count": len(values),
                "minimum": None if not values else round(min(values), 8),
                "maximum": None if not values else round(max(values), 8),
                "mean": None if value_mean is None else round(value_mean, 8),
                "collapsed_to_zero_folds": sum(value < 1e-8 for value in values),
                "sign_instability": False,
                "large_fold_to_fold_change": (
                    False
                    if not values
                    else max(values) - min(values) > max(0.25, abs(value_mean or 0.0))
                ),
            }
        return fields

    fields = summarize(weight_sets)
    archetype_sets: dict[str, list[tuple[float, ...]]] = defaultdict(list)
    if architecture == "B":
        for model in folds:
            for archetype, fitted in model.models.items():
                archetype_sets[archetype].append(fitted.weights)
    collinear = []
    for i, left in enumerate(QB_RATING_FIELDS):
        for j, right in enumerate(QB_RATING_FIELDS[i + 1 :], i + 1):
            correlation = _pearson([o.ratings[i] for o in fit], [o.ratings[j] for o in fit])
            if correlation is not None and abs(correlation) >= COLLINEAR_THRESHOLD:
                collinear.append(
                    {"left": left, "right": right, "correlation": round(correlation, 6)}
                )
    return {
        "architecture": architecture,
        "shared_weight_stability": fields,
        "archetype_weight_stability": {
            archetype: summarize(sets) for archetype, sets in sorted(archetype_sets.items())
        },
        "highly_collinear_rating_pairs": collinear,
        "warnings": (
            ["Architecture B has no shared coefficient vector."] if architecture == "B" else []
        ),
    }


def _boundary(model: ArchitectureModel, research: dict[str, Any]) -> dict[str, Any]:
    observations = {item["qb_id"]: item for item in research["observations"]}

    def predicted(qb_id: str) -> int | None:
        item = observations[qb_id]
        observation = _observation_from_dict(item)
        return model.predict(observation)

    evidence = research["boundary_evidence"]
    adjacent = evidence["adjacent_ovr_nearest_within_archetype"]
    same = evidence["same_ovr_maximum_contrasts_within_archetype"]
    sequences = evidence["same_player_card_sequences"]

    def ordered(pair: dict[str, Any]) -> bool | None:
        low, high = predicted(pair["lower_qb_id"]), predicted(pair["upper_qb_id"])
        return None if low is None or high is None else high >= low

    def equal(pair: dict[str, Any]) -> bool | None:
        low, high = predicted(pair["lower_qb_id"]), predicted(pair["upper_qb_id"])
        return None if low is None or high is None else high == low

    explicit = evidence["explicit_boundary_records"][0]
    return {
        "adjacent_ovr_ordered": sum(ordered(pair) is True for pair in adjacent),
        "adjacent_ovr_count": len(adjacent),
        "same_ovr_equal": sum(equal(pair) is True for pair in same),
        "same_ovr_count": len(same),
        "candidate_sequences_ordered": sum(ordered(pair) is True for pair in sequences),
        "candidate_sequence_count": len(sequences),
        "candidate_sequences_confirmed_progression": False,
        "strongest_adjacent_constraints": [
            {
                "lower_qb_id": pair["lower_qb_id"],
                "upper_qb_id": pair["upper_qb_id"],
                "euclidean_distance": pair["euclidean_distance"],
            }
            for pair in sorted(adjacent, key=lambda item: item["euclidean_distance"])[:5]
        ],
        "strongest_same_ovr_contrasts": [
            {
                "left_qb_id": pair["lower_qb_id"],
                "right_qb_id": pair["upper_qb_id"],
                "euclidean_distance": pair["euclidean_distance"],
            }
            for pair in sorted(same, key=lambda item: item["euclidean_distance"], reverse=True)[:5]
        ],
        "explicit_boundary_qb_id": explicit["qb_id"],
        "explicit_79_prediction": predicted(explicit["qb_id"]),
    }


def _observation_from_dict(item: dict[str, Any]) -> QBObservation:
    return QBObservation(
        qb_id=item["qb_id"],
        player=item["player"],
        overall=item["overall"],
        archetype=item["archetype"],
        program=item["program"],
        ratings=tuple(item["ratings"][field] for field in QB_RATING_FIELDS),
        model_role=item["model_role"],
        population_scope=item["population_scope"],
        unique_profile_key=item["unique_profile_key"],
        duplicate_note=item["duplicate_note"],
        frozen_score_check=item["frozen_score_check"],
        frozen_score_formula=item["frozen_score_formula"],
        formula_delta=item["formula_delta"],
        source_id=item["source_id"],
        source_locator=item["source_locator"],
        source_record=item["source_record"],
        workbook_sheet=item["workbook_sheet"],
        workbook_row=item["workbook_row"],
        analysis_partition=item["analysis_partition"],
    )


def build_model_comparison(research: dict[str, Any]) -> dict[str, Any]:
    """Fit and compare A-D without selecting or declaring a final formula."""
    observations = [_observation_from_dict(item) for item in research["observations"]]
    fit = [item for item in observations if item.analysis_partition == "fit"]
    holdout = [item for item in observations if item.analysis_partition == "holdout"]
    results, all_predictions, stability, boundaries = [], [], [], []
    for architecture in ARCHITECTURES:
        model = fit_architecture(architecture, fit)
        predictions = _predictions(model, observations)
        all_predictions.extend(predictions)
        fit_rows = [row for row in predictions if row["analysis_partition"] == "fit"]
        holdout_rows = [row for row in predictions if row["analysis_partition"] == "holdout"]
        cross_rows, folds = _cross_ovr(architecture, fit)
        boundary = _boundary(model, research)
        boundaries.append({"architecture": architecture, **boundary})
        stability.append(_stability(architecture, folds, fit))
        holdout_metrics = _metrics(holdout_rows)
        warnings = []
        status = "PROVISIONALLY VIABLE"
        if architecture == "B":
            warnings.append(
                "Pure Runner has zero fit observations; independent formula unsupported."
            )
            status = "DATA LIMITED"
        if holdout_metrics["count"] != len(holdout):
            warnings.append("Some holdout observations could not be predicted.")
        archetype_metrics = _breakdowns(holdout_rows, "archetype")
        for archetype, metrics in archetype_metrics.items():
            if metrics["count"] <= 3 and metrics["exact_accuracy"] < 0.5:
                warnings.append(
                    f"{archetype} holdout exact accuracy is low but data-limited "
                    f"(n={metrics['count']})."
                )
        threshold = {}
        for name, mapper in {
            "round_half_up": _round_ovr,
            "floor": math.floor,
            "ceiling": math.ceil,
        }.items():
            mapped = [
                {
                    **row,
                    "predicted_ovr": None
                    if row["latent_score"] is None
                    else mapper(row["latent_score"]),
                    "residual": None
                    if row["latent_score"] is None
                    else mapper(row["latent_score"]) - row["actual_ovr"],
                }
                for row in holdout_rows
            ]
            threshold[name] = _metrics(mapped)
        results.append(
            {
                "architecture": architecture,
                "name": ARCHITECTURES[architecture],
                "parameterization": model.parameters(),
                "training_population": {"partition": "fit", "count": len(fit)},
                "validation_population": {"partition": "holdout", "count": len(holdout)},
                "fit_metrics": _metrics(fit_rows),
                "holdout_metrics": holdout_metrics,
                "cross_ovr_metrics": _metrics(cross_rows),
                "holdout_by_archetype": archetype_metrics,
                "holdout_by_ovr": _breakdowns(holdout_rows, "actual_ovr"),
                "threshold_mapping_comparison": threshold,
                "parameter_count": sum(
                    len(model.parameters()[key].get("standardized_nonnegative_weights", {})) + 1
                    for key in model.models
                )
                + sum(
                    len(value) if isinstance(value, dict) else 0 for value in model.extra.values()
                ),
                "boundary_tests": boundary,
                "warnings": warnings,
                "viability_status": status,
            }
        )
    return {
        "schema_version": 1,
        "formula_status": "unsolved",
        "fit_count": len(fit),
        "holdout_count": len(holdout),
        "architectures": results,
        "predictions": all_predictions,
        "weight_stability": stability,
        "boundary_evaluation": boundaries,
        "leakage_controls": {
            "holdout_used_for_training": False,
            "profile_duplicates_used_for_training": False,
            "cross_ovr_blocks_same_player_and_profile": True,
        },
    }


def write_model_artifacts(directory: str | Path, comparison: dict[str, Any]) -> None:
    """Write deterministic comparison, prediction, stability, and boundary artifacts."""
    root = Path(directory)
    root.mkdir(parents=True, exist_ok=True)
    sections = {
        "qb_model_comparison.json": {
            key: value
            for key, value in comparison.items()
            if key not in {"predictions", "weight_stability", "boundary_evaluation"}
        },
        "qb_weight_stability.json": comparison["weight_stability"],
        "qb_boundary_threshold_evaluation.json": comparison["boundary_evaluation"],
    }
    for name, payload in sections.items():
        (root / name).write_text(
            json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    fields = [
        "architecture",
        "qb_id",
        "player",
        "archetype",
        "actual_ovr",
        "latent_score",
        "predicted_ovr",
        "residual",
        "analysis_partition",
    ]
    with (root / "qb_per_card_predictions.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(
            {field: row[field] for field in fields} for row in comparison["predictions"]
        )
