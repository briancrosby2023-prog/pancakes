"""Small-budget EA-plausible nonlinear QB formula research."""

from __future__ import annotations

import json
import math
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from statistics import fmean
from typing import Any, Callable

from operation_pancake.research.qb_formula_phase import QB_RATING_FIELDS, QBObservation

RIDGE_PENALTY = 1.0
BASELINE_HOLDOUT_EXACT = 0.777778
BASELINE_CROSS_OVR_EXACT = 0.666667

FeatureBuilder = Callable[[QBObservation], tuple[float, ...]]


@dataclass(frozen=True, slots=True)
class CandidateDefinition:
    """One fixed, interpretable nonlinear hypothesis."""

    candidate_id: str
    name: str
    motivation: tuple[str, ...]
    feature_names: tuple[str, ...]
    builder: FeatureBuilder
    structural_parameters: int
    mechanism_count: int


def _ratings(item: QBObservation) -> dict[str, int]:
    return dict(zip(QB_RATING_FIELDS, item.ratings, strict=True))


def _base(item: QBObservation) -> tuple[float, ...]:
    return tuple(float(value) for value in item.ratings)


def _replace(item: QBObservation, changes: dict[str, float]) -> tuple[float, ...]:
    values = _ratings(item)
    return tuple(float(changes.get(field, values[field])) for field in QB_RATING_FIELDS)


def _cap_passing(item: QBObservation) -> tuple[float, ...]:
    values = _ratings(item)
    return _replace(item, {field: min(values[field], 90) for field in ("SAC", "MAC", "DAC")})


def _diminishing_passing(item: QBObservation) -> tuple[float, ...]:
    values = _ratings(item)
    return _replace(
        item,
        {
            field: min(values[field], 90) + 0.5 * max(0, values[field] - 90)
            for field in ("SAC", "MAC", "DAC")
        },
    )


def _append(item: QBObservation, *values: float) -> tuple[float, ...]:
    return _base(item) + tuple(values)


def _passing_bottleneck(item: QBObservation) -> tuple[float, ...]:
    values = _ratings(item)
    return _append(item, min(values["SAC"], values["MAC"], values["DAC"]))


def _power_deep_bottleneck(item: QBObservation) -> tuple[float, ...]:
    values = _ratings(item)
    return _append(item, min(values["THP"], values["DAC"]))


def _mobility_bottleneck(item: QBObservation) -> tuple[float, ...]:
    values = _ratings(item)
    return _append(item, min(values["SPD"], values["ACC"], values["AGI"]))


def _low_awareness_penalty(item: QBObservation) -> tuple[float, ...]:
    values = _ratings(item)
    return _append(item, min(0, values["AWR"] - 80))


def _two_bottlenecks(item: QBObservation) -> tuple[float, ...]:
    values = _ratings(item)
    return _append(
        item,
        min(values["SAC"], values["MAC"], values["DAC"]),
        min(values["THP"], values["DAC"]),
    )


CANDIDATES = (
    CandidateDefinition(
        "baseline_a",
        "Architecture A round-half-up",
        ("Mandatory simplicity baseline.",),
        QB_RATING_FIELDS,
        _base,
        0,
        0,
    ),
    CandidateDefinition(
        "passing_cap_90",
        "SAC/MAC/DAC hard cap at 90",
        ("Same-OVR passing-profile contrasts.", "QB-0002 threshold regression."),
        QB_RATING_FIELDS,
        _cap_passing,
        1,
        1,
    ),
    CandidateDefinition(
        "passing_diminishing_90",
        "SAC/MAC/DAC half contribution above 90",
        ("High passing ratings may have diminishing EA valuation.",),
        QB_RATING_FIELDS,
        _diminishing_passing,
        2,
        1,
    ),
    CandidateDefinition(
        "passing_accuracy_bottleneck",
        "Minimum of SAC/MAC/DAC",
        ("QB-0016 overprediction.", "Large same-OVR passing contrasts."),
        QB_RATING_FIELDS + ("MIN_SAC_MAC_DAC",),
        _passing_bottleneck,
        0,
        1,
    ),
    CandidateDefinition(
        "power_deep_bottleneck",
        "Minimum of THP/DAC",
        ("QB-0070 and QB-0071 underprediction.", "Deep accuracy requires arm power."),
        QB_RATING_FIELDS + ("MIN_THP_DAC",),
        _power_deep_bottleneck,
        0,
        1,
    ),
    CandidateDefinition(
        "mobility_bottleneck",
        "Minimum of SPD/ACC/AGI",
        ("Dual Threat holdout errors.", "EA mobility may be bottlenecked."),
        QB_RATING_FIELDS + ("MIN_SPD_ACC_AGI",),
        _mobility_bottleneck,
        0,
        1,
    ),
    CandidateDefinition(
        "low_awareness_floor_80",
        "Additional penalty below AWR 80",
        ("QB-0033 and QB-0034 boundary underprediction.",),
        QB_RATING_FIELDS + ("AWR_BELOW_80",),
        _low_awareness_penalty,
        1,
        1,
    ),
    CandidateDefinition(
        "passing_plus_power_bottlenecks",
        "SAC/MAC/DAC and THP/DAC bottlenecks",
        ("Only predeclared two-mechanism candidate within the complexity budget.",),
        QB_RATING_FIELDS + ("MIN_SAC_MAC_DAC", "MIN_THP_DAC"),
        _two_bottlenecks,
        0,
        2,
    ),
)


@dataclass(frozen=True, slots=True)
class NonlinearScoreModel:
    definition: CandidateDefinition
    means: tuple[float, ...]
    scales: tuple[float, ...]
    coefficients: tuple[float, ...]
    intercept: float

    def score(self, item: QBObservation) -> float:
        features = self.definition.builder(item)
        return self.intercept + sum(
            coefficient * ((value - mean) / scale)
            for value, mean, scale, coefficient in zip(
                features, self.means, self.scales, self.coefficients, strict=True
            )
        )

    def predict(self, item: QBObservation) -> int:
        return math.floor(self.score(item) + 0.5)

    def parameters(self) -> dict[str, Any]:
        return {
            "intercept": round(self.intercept, 8),
            "coefficients": {
                name: round(value, 8)
                for name, value in zip(
                    self.definition.feature_names, self.coefficients, strict=True
                )
            },
            "fixed_structural_parameters": self.definition.structural_parameters,
        }


def fit_candidate(definition: CandidateDefinition, fit: list[QBObservation]) -> NonlinearScoreModel:
    if len(fit) < 2 or any(item.analysis_partition != "fit" for item in fit):
        raise ValueError("Candidate fitting requires at least two fit observations only.")
    matrix = [definition.builder(item) for item in fit]
    width = len(definition.feature_names)
    if any(len(row) != width for row in matrix):
        raise ValueError("Candidate feature builder returned an invalid feature count.")
    columns = list(zip(*matrix, strict=True))
    means = tuple(fmean(column) for column in columns)
    scales = tuple(
        math.sqrt(fmean((value - mean) ** 2 for value in column)) or 1.0
        for column, mean in zip(columns, means, strict=True)
    )
    standardized = [
        tuple((value - mean) / scale for value, mean, scale in zip(row, means, scales, strict=True))
        for row in matrix
    ]
    targets = [float(item.overall) for item in fit]
    intercept = fmean(targets)
    coefficients = [0.0] * width
    predictions = [intercept] * len(fit)
    for _ in range(1000):
        largest = 0.0
        for index in range(width):
            old = coefficients[index]
            partial = [
                target - (prediction - old * row[index])
                for target, prediction, row in zip(targets, predictions, standardized, strict=True)
            ]
            numerator = sum(
                row[index] * residual for row, residual in zip(standardized, partial, strict=True)
            )
            denominator = sum(row[index] ** 2 for row in standardized) + RIDGE_PENALTY
            new = max(0.0, numerator / denominator)
            delta = new - old
            predictions = [
                prediction + delta * row[index]
                for prediction, row in zip(predictions, standardized, strict=True)
            ]
            coefficients[index] = new
            largest = max(largest, abs(delta))
        intercept_delta = fmean(
            target - prediction for target, prediction in zip(targets, predictions, strict=True)
        )
        intercept += intercept_delta
        predictions = [prediction + intercept_delta for prediction in predictions]
        if max(largest, abs(intercept_delta)) < 1e-10:
            break
    return NonlinearScoreModel(definition, means, scales, tuple(coefficients), intercept)


def _observation(item: dict[str, Any]) -> QBObservation:
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


def _prediction_rows(
    model: NonlinearScoreModel, observations: list[QBObservation]
) -> list[dict[str, Any]]:
    return [
        {
            "candidate_id": model.definition.candidate_id,
            "qb_id": item.qb_id,
            "player": item.player,
            "archetype": item.archetype,
            "actual_ovr": item.overall,
            "latent_score": round(model.score(item), 8),
            "predicted_ovr": model.predict(item),
            "residual": model.predict(item) - item.overall,
            "analysis_partition": item.analysis_partition,
        }
        for item in observations
    ]


def _metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    errors = [abs(row["residual"]) for row in rows]
    return {
        "count": len(rows),
        "exact_accuracy": round(sum(error == 0 for error in errors) / len(errors), 6),
        "within_one_accuracy": round(sum(error <= 1 for error in errors) / len(errors), 6),
        "mean_absolute_error": round(fmean(errors), 6),
        "maximum_error": max(errors),
        "mean_signed_residual": round(fmean(row["residual"] for row in rows), 6),
    }


def _cross_ovr(
    definition: CandidateDefinition, fit: list[QBObservation]
) -> tuple[list[dict[str, Any]], list[NonlinearScoreModel]]:
    rows, models = [], []
    for level in sorted({item.overall for item in fit}):
        validation = [item for item in fit if item.overall == level]
        players = {item.player.casefold() for item in validation}
        profiles = {item.unique_profile_key for item in validation}
        training = [
            item
            for item in fit
            if item.overall != level
            and item.player.casefold() not in players
            and item.unique_profile_key not in profiles
        ]
        model = fit_candidate(definition, training)
        models.append(model)
        fold_rows = _prediction_rows(model, validation)
        for row in fold_rows:
            row["validation_ovr"] = level
            row["training_count"] = len(training)
        rows.extend(fold_rows)
    return rows, models


def _stability(models: list[NonlinearScoreModel]) -> dict[str, Any]:
    names = models[0].definition.feature_names
    return {
        name: {
            "fold_count": len(models),
            "minimum": round(min(model.coefficients[index] for model in models), 8),
            "maximum": round(max(model.coefficients[index] for model in models), 8),
            "mean": round(fmean(model.coefficients[index] for model in models), 8),
            "collapsed_to_zero_folds": sum(model.coefficients[index] < 1e-8 for model in models),
            "large_fold_to_fold_change": (
                max(model.coefficients[index] for model in models)
                - min(model.coefficients[index] for model in models)
                > 0.25
            ),
        }
        for index, name in enumerate(names)
    }


def _constraints(
    model: NonlinearScoreModel, observations: list[QBObservation], research: dict[str, Any]
) -> dict[str, Any]:
    predicted = {item.qb_id: model.predict(item) for item in observations}
    evidence = research["boundary_evidence"]
    adjacent = evidence["adjacent_ovr_nearest_within_archetype"]
    contrasts = evidence["same_ovr_maximum_contrasts_within_archetype"]
    sequences = evidence["same_player_card_sequences"]

    def ordered(pair: dict[str, Any]) -> bool:
        return predicted[pair["upper_qb_id"]] >= predicted[pair["lower_qb_id"]]

    def equal(pair: dict[str, Any]) -> bool:
        return predicted[pair["upper_qb_id"]] == predicted[pair["lower_qb_id"]]

    explicit = evidence["explicit_boundary_records"][0]
    adjacent_details = [
        {
            "lower_qb_id": pair["lower_qb_id"],
            "upper_qb_id": pair["upper_qb_id"],
            "predicted_ordered": ordered(pair),
            "lower_prediction": predicted[pair["lower_qb_id"]],
            "upper_prediction": predicted[pair["upper_qb_id"]],
        }
        for pair in adjacent
    ]
    contrast_details = [
        {
            "left_qb_id": pair["lower_qb_id"],
            "right_qb_id": pair["upper_qb_id"],
            "predicted_equal": equal(pair),
            "left_prediction": predicted[pair["lower_qb_id"]],
            "right_prediction": predicted[pair["upper_qb_id"]],
        }
        for pair in contrasts
    ]
    sequence_details = [
        {
            "lower_qb_id": pair["lower_qb_id"],
            "upper_qb_id": pair["upper_qb_id"],
            "predicted_ordered": ordered(pair),
            "confirmed_progression": False,
            "information_priority": round(
                abs(pair["upper_overall"] - pair["lower_overall"])
                / max(pair["euclidean_distance"], 1e-9),
                8,
            ),
        }
        for pair in sequences
    ]
    return {
        "adjacent_ordered": sum(ordered(pair) for pair in adjacent),
        "adjacent_count": len(adjacent),
        "same_ovr_equal": sum(equal(pair) for pair in contrasts),
        "same_ovr_count": len(contrasts),
        "candidate_sequences_ordered": sum(ordered(pair) for pair in sequences),
        "candidate_sequence_count": len(sequences),
        "candidate_sequences_confirmed_progression": False,
        "explicit_79_prediction": predicted[explicit["qb_id"]],
        "explicit_boundary_qb_id": explicit["qb_id"],
        "adjacent_pair_effects": adjacent_details,
        "same_ovr_pair_effects": contrast_details,
        "sequence_effects_by_information_value": sorted(
            sequence_details,
            key=lambda item: (-item["information_priority"], item["lower_qb_id"]),
        ),
    }


def _by_archetype(rows: list[dict[str, Any]]) -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[row["archetype"]].append(row)
    return {name: _metrics(group) for name, group in sorted(groups.items())}


def _qb0074_audit(model: NonlinearScoreModel, observations: list[QBObservation]) -> dict[str, Any]:
    card = next(item for item in observations if item.qb_id == "QB-0074")
    features = model.definition.builder(card)
    contributions = {
        name: round(coefficient * ((value - mean) / scale), 8)
        for name, value, mean, scale, coefficient in zip(
            model.definition.feature_names,
            features,
            model.means,
            model.scales,
            model.coefficients,
            strict=True,
        )
    }
    return {
        "qb_id": card.qb_id,
        "ratings_complete": len(card.ratings) == 15,
        "source_id": card.source_id,
        "source_locator": card.source_locator,
        "source_record": card.source_record,
        "frozen_formula_audit_matches": abs(card.formula_delta) < 1e-10,
        "predicted_ovr": model.predict(card),
        "latent_score": round(model.score(card), 8),
        "largest_positive_contributions": sorted(
            contributions.items(), key=lambda item: (-item[1], item[0])
        )[:5],
    }


def build_nonlinearity_analysis(research: dict[str, Any]) -> dict[str, Any]:
    """Evaluate the fixed nonlinear hypothesis family without validation tuning."""
    observations = [_observation(item) for item in research["observations"]]
    fit = [item for item in observations if item.analysis_partition == "fit"]
    results, predictions = [], []
    for definition in CANDIDATES:
        model = fit_candidate(definition, fit)
        rows = _prediction_rows(model, observations)
        predictions.extend(rows)
        fit_rows = [row for row in rows if row["analysis_partition"] == "fit"]
        holdout_rows = [row for row in rows if row["analysis_partition"] == "holdout"]
        cross_rows, folds = _cross_ovr(definition, fit)
        holdout_metrics = _metrics(holdout_rows)
        cross_metrics = _metrics(cross_rows)
        supported = (
            definition.candidate_id != "baseline_a"
            and holdout_metrics["exact_accuracy"] > BASELINE_HOLDOUT_EXACT
            and cross_metrics["exact_accuracy"] > BASELINE_CROSS_OVR_EXACT
            and definition.mechanism_count <= 2
        )
        results.append(
            {
                "candidate_id": definition.candidate_id,
                "name": definition.name,
                "motivation": list(definition.motivation),
                "feature_names": list(definition.feature_names),
                "learned_parameter_count": len(definition.feature_names) + 1,
                "structural_parameter_count": definition.structural_parameters,
                "total_complexity": len(definition.feature_names)
                + 1
                + definition.structural_parameters,
                "mechanism_count": definition.mechanism_count,
                "parameters": model.parameters(),
                "fit_metrics": _metrics(fit_rows),
                "holdout_metrics": holdout_metrics,
                "cross_ovr_metrics": cross_metrics,
                "holdout_by_archetype": _by_archetype(holdout_rows),
                "holdout_errors": [row for row in holdout_rows if row["residual"] != 0],
                "constraints": _constraints(model, observations, research),
                "coefficient_stability": _stability(folds),
                "qb_0074_audit": _qb0074_audit(model, observations),
                "support_status": (
                    "SUPPORTED"
                    if supported
                    else ("BASELINE" if definition.candidate_id == "baseline_a" else "REJECTED")
                ),
                "rejection_reason": None
                if supported or definition.candidate_id == "baseline_a"
                else (
                    "No joint improvement over Architecture A on independent holdout "
                    "and leakage-controlled cross-OVR exact accuracy."
                ),
            }
        )
    return {
        "schema_version": 1,
        "phase": "QB Formula Phase — EA-Plausible Interactions, Caps & Nonlinearity",
        "formula_status": "unsolved",
        "baseline_commit": "f4bf7d3",
        "complexity_budget": {
            "maximum_mechanisms": 2,
            "candidate_count_including_baseline": len(CANDIDATES),
            "candidate_set_predeclared_before_validation": True,
        },
        "selection_bias_warning": (
            "Mechanisms were motivated by known errors; independent holdout is therefore "
            "not a pristine mechanism-selection set. Cross-OVR evidence is required."
        ),
        "results": results,
        "predictions": predictions,
        "surviving_mechanisms": [
            result["candidate_id"] for result in results if result["support_status"] == "SUPPORTED"
        ],
        "leakage_controls": {
            "holdout_used_for_fitting": False,
            "boundary_used_for_fitting": False,
            "research_only_used_for_fitting": False,
            "profile_duplicate_used_for_fitting": False,
            "cross_ovr_blocks_same_player_and_profile": True,
        },
    }


def write_nonlinearity_artifacts(directory: str | Path, analysis: dict[str, Any]) -> None:
    root = Path(directory)
    root.mkdir(parents=True, exist_ok=True)
    summary = {key: value for key, value in analysis.items() if key != "predictions"}
    rejected = [result for result in analysis["results"] if result["support_status"] == "REJECTED"]
    payloads = {
        "qb_nonlinearity_comparison.json": summary,
        "qb_nonlinearity_predictions.json": analysis["predictions"],
        "qb_nonlinearity_rejected_mechanisms.json": rejected,
        "qb_nonlinearity_qb0074_audit.json": [
            {"candidate_id": result["candidate_id"], **result["qb_0074_audit"]}
            for result in analysis["results"]
        ],
    }
    for name, payload in payloads.items():
        (root / name).write_text(
            json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
