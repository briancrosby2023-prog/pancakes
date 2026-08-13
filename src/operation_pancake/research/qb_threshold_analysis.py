"""Discrete score-band research for the QB Formula Phase."""

from __future__ import annotations

import json
import math
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from statistics import fmean
from typing import Any

from operation_pancake.research.qb_formula_phase import QB_RATING_FIELDS, QBObservation
from operation_pancake.research.qb_model_comparison import (
    ARCHITECTURES,
    ArchitectureModel,
    fit_architecture,
)

FOCUS_ARCHITECTURES = ("A", "C")
MIN_ARCHETYPE_OFFSET_SAMPLE = 5


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


def _pava(levels: list[int], centers: list[float], counts: list[int]) -> dict[int, float]:
    """Pool adjacent OVR centers until latent scores are monotonic."""
    blocks = [
        {"levels": [level], "weight": count, "value": center}
        for level, center, count in zip(levels, centers, counts, strict=True)
    ]
    index = 0
    while index < len(blocks) - 1:
        if blocks[index]["value"] <= blocks[index + 1]["value"]:
            index += 1
            continue
        left, right = blocks[index], blocks[index + 1]
        weight = left["weight"] + right["weight"]
        merged = {
            "levels": left["levels"] + right["levels"],
            "weight": weight,
            "value": (left["value"] * left["weight"] + right["value"] * right["weight"]) / weight,
        }
        blocks[index : index + 2] = [merged]
        index = max(0, index - 1)
    return {level: float(block["value"]) for block in blocks for level in block["levels"]}


def _interpolate_centers(
    observed: dict[int, float], minimum: int, maximum: int
) -> dict[int, float]:
    """Fill omitted OVR centers from neighboring fit-only centers."""
    levels = sorted(observed)
    if len(levels) < 2:
        raise ValueError("At least two observed OVR levels are required for score bands.")
    result = dict(observed)
    for level in range(minimum, maximum + 1):
        if level in result:
            continue
        lower = max((candidate for candidate in levels if candidate < level), default=None)
        upper = min((candidate for candidate in levels if candidate > level), default=None)
        if lower is None:
            first, second = levels[:2]
            slope = (observed[second] - observed[first]) / (second - first)
            result[level] = observed[first] + slope * (level - first)
        elif upper is None:
            first, second = levels[-2:]
            slope = (observed[second] - observed[first]) / (second - first)
            result[level] = observed[second] + slope * (level - second)
        else:
            fraction = (level - lower) / (upper - lower)
            result[level] = observed[lower] + fraction * (observed[upper] - observed[lower])
    return dict(sorted(result.items()))


@dataclass(frozen=True, slots=True)
class ScoreBands:
    """Monotonic unequal-width score-to-OVR bands learned from fit data."""

    centers: dict[int, float]
    thresholds: dict[int, float]
    archetype_offsets: dict[str, float]
    pooled_level_groups: tuple[tuple[int, ...], ...]

    def predict_score(self, score: float, archetype: str) -> int:
        adjusted = score + self.archetype_offsets.get(archetype, 0.0)
        for upper_ovr, threshold in sorted(self.thresholds.items()):
            if adjusted < threshold:
                return upper_ovr - 1
        return max(self.centers)

    def parameters(self) -> dict[str, Any]:
        return {
            "centers": {str(key): round(value, 8) for key, value in self.centers.items()},
            "thresholds": {
                f"{upper - 1}_to_{upper}": round(value, 8)
                for upper, value in self.thresholds.items()
            },
            "band_widths": {
                str(level): round(
                    self.thresholds.get(level + 1, math.inf)
                    - self.thresholds.get(level, -math.inf),
                    8,
                )
                if level not in {min(self.centers), max(self.centers)}
                else None
                for level in self.centers
            },
            "archetype_offsets": {
                key: round(value, 8) for key, value in self.archetype_offsets.items()
            },
            "pooled_level_groups": [list(group) for group in self.pooled_level_groups],
        }


def fit_score_bands(
    model: ArchitectureModel,
    fit: list[QBObservation],
    overall_range: tuple[int, int],
    archetype_offsets: bool = False,
) -> ScoreBands:
    """Learn monotonic unequal-width score bands from fitting observations only."""
    if not fit or any(item.analysis_partition != "fit" for item in fit):
        raise ValueError("Score bands require only non-empty fit-partition observations.")
    scores = [(item, model.score(item)) for item in fit]
    if any(score is None for _, score in scores):
        raise ValueError("Fitted architecture cannot score every fitting observation.")
    by_level: dict[int, list[float]] = defaultdict(list)
    for item, score in scores:
        assert score is not None
        by_level[item.overall].append(score)
    levels = sorted(by_level)
    raw_centers = [fmean(by_level[level]) for level in levels]
    monotonic = _pava(levels, raw_centers, [len(by_level[level]) for level in levels])
    centers = _interpolate_centers(monotonic, *overall_range)
    thresholds = {
        upper: (centers[upper - 1] + centers[upper]) / 2
        for upper in range(overall_range[0] + 1, overall_range[1] + 1)
    }
    offsets: dict[str, float] = {}
    if archetype_offsets:
        residuals: dict[str, list[float]] = defaultdict(list)
        for item, score in scores:
            assert score is not None
            residuals[item.archetype].append(centers[item.overall] - score)
        offsets = {
            archetype: fmean(values)
            for archetype, values in sorted(residuals.items())
            if len(values) >= MIN_ARCHETYPE_OFFSET_SAMPLE
        }
    pooled: dict[float, list[int]] = defaultdict(list)
    for level, value in monotonic.items():
        pooled[round(value, 12)].append(level)
    return ScoreBands(
        centers,
        thresholds,
        offsets,
        tuple(tuple(group) for group in pooled.values() if len(group) > 1),
    )


def _rows(
    architecture: str,
    variant: str,
    model: ArchitectureModel,
    bands: ScoreBands,
    observations: list[QBObservation],
) -> list[dict[str, Any]]:
    rows = []
    for item in observations:
        score = model.score(item)
        predicted = None if score is None else bands.predict_score(score, item.archetype)
        rows.append(
            {
                "architecture": architecture,
                "variant": variant,
                "qb_id": item.qb_id,
                "player": item.player,
                "archetype": item.archetype,
                "actual_ovr": item.overall,
                "latent_score": None if score is None else round(score, 8),
                "predicted_ovr": predicted,
                "residual": None if predicted is None else predicted - item.overall,
                "analysis_partition": item.analysis_partition,
            }
        )
    return rows


def _metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    usable = [row for row in rows if row["predicted_ovr"] is not None]
    errors = [abs(row["residual"]) for row in usable]
    return {
        "count": len(usable),
        "exact_accuracy": None
        if not usable
        else round(sum(error == 0 for error in errors) / len(errors), 6),
        "within_one_accuracy": None
        if not usable
        else round(sum(error <= 1 for error in errors) / len(errors), 6),
        "mean_absolute_error": None if not usable else round(fmean(errors), 6),
        "maximum_error": None if not usable else max(errors),
        "mean_signed_residual": None
        if not usable
        else round(fmean(row["residual"] for row in usable), 6),
    }


def _cross_ovr(
    architecture: str,
    fit: list[QBObservation],
    overall_range: tuple[int, int],
    adjusted: bool,
) -> tuple[list[dict[str, Any]], list[ScoreBands]]:
    rows = []
    fold_bands = []
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
        model = fit_architecture(architecture, training)
        bands = fit_score_bands(model, training, overall_range, adjusted)
        fold_bands.append(bands)
        fold_rows = _rows(
            architecture,
            "archetype_adjusted_bands" if adjusted else "global_bands",
            model,
            bands,
            validation,
        )
        for row in fold_rows:
            row["validation_ovr"] = level
            row["training_count"] = len(training)
        rows.extend(fold_rows)
    return rows, fold_bands


def _threshold_stability(folds: list[ScoreBands]) -> dict[str, Any]:
    transitions = sorted(folds[0].thresholds)
    return {
        f"{upper - 1}_to_{upper}": {
            "fold_count": len(folds),
            "minimum": round(min(fold.thresholds[upper] for fold in folds), 8),
            "maximum": round(max(fold.thresholds[upper] for fold in folds), 8),
            "mean": round(fmean(fold.thresholds[upper] for fold in folds), 8),
            "range": round(
                max(fold.thresholds[upper] for fold in folds)
                - min(fold.thresholds[upper] for fold in folds),
                8,
            ),
        }
        for upper in transitions
    }


def _boundary_diagnostics(rows: list[dict[str, Any]], research: dict[str, Any]) -> dict[str, Any]:
    predictions = {row["qb_id"]: row["predicted_ovr"] for row in rows}
    evidence = research["boundary_evidence"]

    def ordered(pair: dict[str, Any]) -> bool | None:
        lower = predictions[pair["lower_qb_id"]]
        upper = predictions[pair["upper_qb_id"]]
        return None if lower is None or upper is None else upper >= lower

    def equal(pair: dict[str, Any]) -> bool | None:
        left = predictions[pair["lower_qb_id"]]
        right = predictions[pair["upper_qb_id"]]
        return None if left is None or right is None else left == right

    adjacent = evidence["adjacent_ovr_nearest_within_archetype"]
    contrasts = evidence["same_ovr_maximum_contrasts_within_archetype"]
    sequences = evidence["same_player_card_sequences"]
    explicit = evidence["explicit_boundary_records"][0]
    sequence_details = [
        {
            "lower_qb_id": pair["lower_qb_id"],
            "upper_qb_id": pair["upper_qb_id"],
            "actual_ovr_change": pair["upper_overall"] - pair["lower_overall"],
            "euclidean_distance": pair["euclidean_distance"],
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
        "adjacent_ordered": sum(ordered(pair) is True for pair in adjacent),
        "adjacent_count": len(adjacent),
        "same_ovr_equal": sum(equal(pair) is True for pair in contrasts),
        "same_ovr_count": len(contrasts),
        "candidate_sequences_ordered": sum(ordered(pair) is True for pair in sequences),
        "candidate_sequence_count": len(sequences),
        "candidate_sequences_confirmed_progression": False,
        "explicit_boundary_qb_id": explicit["qb_id"],
        "explicit_79_prediction": predictions[explicit["qb_id"]],
        "sequence_information_priorities": sorted(
            sequence_details,
            key=lambda item: (-item["information_priority"], item["lower_qb_id"]),
        ),
    }


def _classify_errors(
    threshold_rows: list[dict[str, Any]], baseline_rows: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    baseline = {
        row["qb_id"]: row for row in baseline_rows if row["analysis_partition"] == "holdout"
    }
    classifications = []
    for row in threshold_rows:
        if row["analysis_partition"] != "holdout" or row["residual"] == 0:
            continue
        prior = baseline[row["qb_id"]]
        threshold_error = abs(row["residual"])
        baseline_error = abs(prior["residual"])
        if threshold_error < baseline_error:
            category = "likely_threshold_error_improved"
        elif threshold_error > baseline_error:
            category = "threshold_mapping_worsened"
        elif row["archetype"] in {"Dual Threat", "Backfield Creator"}:
            category = "possible_archetype_effect_data_limited"
        else:
            category = "insufficient_to_distinguish_threshold_from_weighting"
        classifications.append(
            {
                "qb_id": row["qb_id"],
                "archetype": row["archetype"],
                "actual_ovr": row["actual_ovr"],
                "baseline_prediction": prior["predicted_ovr"],
                "threshold_prediction": row["predicted_ovr"],
                "classification": category,
            }
        )
    return classifications


def build_threshold_analysis(
    research: dict[str, Any], baseline_comparison: dict[str, Any]
) -> dict[str, Any]:
    """Compare global and minimally adjusted score bands for A and C."""
    observations = [_observation(item) for item in research["observations"]]
    fit = [item for item in observations if item.analysis_partition == "fit"]
    holdout = [item for item in observations if item.analysis_partition == "holdout"]
    overall_range = (
        research["population"]["overall_minimum"],
        research["population"]["overall_maximum"],
    )
    baseline_rows = baseline_comparison["predictions"]
    results = []
    all_predictions = []
    for architecture in FOCUS_ARCHITECTURES:
        model = fit_architecture(architecture, fit)
        architecture_baseline = [
            row for row in baseline_rows if row["architecture"] == architecture
        ]
        baseline_holdout = [
            row for row in architecture_baseline if row["analysis_partition"] == "holdout"
        ]
        for adjusted in (False, True):
            variant = "archetype_adjusted_bands" if adjusted else "global_bands"
            bands = fit_score_bands(model, fit, overall_range, adjusted)
            rows = _rows(architecture, variant, model, bands, observations)
            all_predictions.extend(rows)
            holdout_rows = [row for row in rows if row["analysis_partition"] == "holdout"]
            cross_rows, fold_bands = _cross_ovr(architecture, fit, overall_range, adjusted)
            threshold_metrics = _metrics(holdout_rows)
            baseline_metrics = _metrics(baseline_holdout)
            results.append(
                {
                    "architecture": architecture,
                    "architecture_name": ARCHITECTURES[architecture],
                    "variant": variant,
                    "parameters": bands.parameters(),
                    "parameter_count": len(bands.thresholds) + len(bands.archetype_offsets),
                    "training_population": {"partition": "fit", "count": len(fit)},
                    "validation_population": {
                        "partition": "holdout",
                        "count": len(holdout),
                    },
                    "baseline_holdout_metrics": baseline_metrics,
                    "threshold_holdout_metrics": threshold_metrics,
                    "holdout_exact_change": round(
                        threshold_metrics["exact_accuracy"] - baseline_metrics["exact_accuracy"],
                        6,
                    ),
                    "cross_ovr_metrics": _metrics(cross_rows),
                    "threshold_stability": _threshold_stability(fold_bands),
                    "boundary_diagnostics": _boundary_diagnostics(rows, research),
                    "systematic_errors": _classify_errors(holdout_rows, architecture_baseline),
                    "interpretation": (
                        "Threshold evidence is material only if independent holdout and "
                        "cross-OVR behavior improve without boundary regressions."
                    ),
                }
            )
    return {
        "schema_version": 1,
        "phase": "QB Formula Phase — Discrete Threshold & Boundary Analysis",
        "formula_status": "unsolved",
        "baseline_commit": "6a265ec",
        "focus_architectures": list(FOCUS_ARCHITECTURES),
        "results": results,
        "predictions": all_predictions,
        "leakage_controls": {
            "thresholds_learned_from_fit_only": True,
            "holdout_used_for_threshold_training": False,
            "cross_ovr_blocks_same_player_and_profile": True,
            "profile_duplicates_used_for_training": False,
        },
    }


def write_threshold_artifacts(directory: str | Path, analysis: dict[str, Any]) -> None:
    """Write separate deterministic threshold and boundary research artifacts."""
    root = Path(directory)
    root.mkdir(parents=True, exist_ok=True)
    summary = {key: value for key, value in analysis.items() if key != "predictions"}
    boundaries = [
        {
            "architecture": result["architecture"],
            "variant": result["variant"],
            **result["boundary_diagnostics"],
        }
        for result in analysis["results"]
    ]
    errors = [
        {
            "architecture": result["architecture"],
            "variant": result["variant"],
            "errors": result["systematic_errors"],
        }
        for result in analysis["results"]
    ]
    payloads = {
        "qb_discrete_threshold_comparison.json": summary,
        "qb_threshold_predictions.json": analysis["predictions"],
        "qb_threshold_boundary_analysis.json": boundaries,
        "qb_threshold_systematic_errors.json": errors,
    }
    for name, payload in payloads.items():
        (root / name).write_text(
            json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
