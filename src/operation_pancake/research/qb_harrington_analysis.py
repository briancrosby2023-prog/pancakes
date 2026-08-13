"""Controlled score analysis of the confirmed Joey Harrington progression chain."""

from __future__ import annotations

import json
import math
from pathlib import Path
from statistics import fmean
from typing import Any

from operation_pancake.importers.workbook_importer import WorkbookImporter
from operation_pancake.research.qb_formula_phase import QB_RATING_FIELDS

CHAIN_IDS = ("QB-0074", "QB-0038", "QB-0013", "QB-0003")
ARCHITECTURES = ("A", "C")


def round_half_up(value: float) -> int:
    """Round a nonnegative latent OVR using the established model convention."""
    return math.floor(value + 0.5)


def _architecture_parameters(comparison: dict[str, Any], architecture: str) -> dict[str, Any]:
    result = next(
        item for item in comparison["architectures"] if item["architecture"] == architecture
    )
    return result["parameterization"]


def _score(card: dict[str, Any], parameters: dict[str, Any], architecture: str) -> float:
    shared = parameters["shared"]
    score = shared["intercept"] + sum(
        shared["standardized_nonnegative_weights"][field]
        * (card["ratings"][field] - shared["standardization_means"][field])
        / shared["standardization_scales"][field]
        for field in QB_RATING_FIELDS
    )
    if architecture == "C":
        score += parameters["modifiers"].get(card["archetype"], 0.0)
    return score


def _raw_coefficients(parameters: dict[str, Any]) -> dict[str, float]:
    shared = parameters["shared"]
    return {
        field: shared["standardized_nonnegative_weights"][field]
        / shared["standardization_scales"][field]
        for field in QB_RATING_FIELDS
    }


def _card_summary(card: dict[str, Any]) -> dict[str, Any]:
    return {
        key: card[key]
        for key in (
            "qb_id",
            "player",
            "overall",
            "program",
            "archetype",
            "ratings",
            "source_id",
            "source_locator",
            "source_record",
            "workbook_sheet",
            "workbook_row",
            "model_role",
            "population_scope",
        )
    }


def _transition(lower: dict[str, Any], upper: dict[str, Any]) -> dict[str, Any]:
    deltas = {
        field: upper["ratings"][field] - lower["ratings"][field] for field in QB_RATING_FIELDS
    }
    changed = {field: value for field, value in deltas.items() if value != 0}
    magnitudes = set(changed.values())
    return {
        "lower_qb_id": lower["qb_id"],
        "upper_qb_id": upper["qb_id"],
        "lower_ovr": lower["overall"],
        "upper_ovr": upper["overall"],
        "observed_ovr_movement": upper["overall"] - lower["overall"],
        "rating_deltas": deltas,
        "changed_attributes": changed,
        "unchanged_attributes": [field for field, value in deltas.items() if value == 0],
        "total_raw_rating_point_increase": sum(deltas.values()),
        "changed_attribute_count": len(changed),
        "mean_change_among_changed": round(fmean(changed.values()), 8),
        "structurally_uniform": len(magnitudes) == 1,
        "exceptional_attributes": {
            field: value for field, value in changed.items() if value != min(changed.values())
        },
    }


def _state_scores(
    chain: list[dict[str, Any]], parameters: dict[str, Any], architecture: str
) -> list[dict[str, Any]]:
    rows = []
    for card in chain:
        latent = _score(card, parameters, architecture)
        predicted = round_half_up(latent)
        rows.append(
            {
                "qb_id": card["qb_id"],
                "observed_ovr": card["overall"],
                "latent_score": round(latent, 8),
                "predicted_ovr": predicted,
                "residual": predicted - card["overall"],
            }
        )
    return rows


def _offset_test(states: list[dict[str, Any]]) -> dict[str, Any]:
    intervals = []
    for state in states:
        lower = state["observed_ovr"] - 0.5 - state["latent_score"]
        upper = state["observed_ovr"] + 0.5 - state["latent_score"]
        intervals.append(
            {
                "qb_id": state["qb_id"],
                "lower_inclusive": round(lower, 8),
                "upper_exclusive": round(upper, 8),
            }
        )
    intersection_lower = max(item["lower_inclusive"] for item in intervals)
    intersection_upper = min(item["upper_exclusive"] for item in intervals)
    feasible = intersection_lower < intersection_upper
    return {
        "rounding": "round_half_up",
        "state_offset_intervals": intervals,
        "intersection_lower_inclusive": round(intersection_lower, 8),
        "intersection_upper_exclusive": round(intersection_upper, 8),
        "intersection_width": round(max(0.0, intersection_upper - intersection_lower), 8),
        "feasible": feasible,
        "descriptive_midpoint_offset": (
            round((intersection_lower + intersection_upper) / 2, 8) if feasible else None
        ),
        "production_parameter_created": False,
    }


def _model_transitions(
    transitions: list[dict[str, Any]],
    states: list[dict[str, Any]],
    coefficients: dict[str, float],
) -> list[dict[str, Any]]:
    score_by_id = {state["qb_id"]: state["latent_score"] for state in states}
    rows = []
    for transition in transitions:
        movement = score_by_id[transition["upper_qb_id"]] - score_by_id[transition["lower_qb_id"]]
        contributions = [
            {
                "attribute": field,
                "raw_delta": delta,
                "raw_score_coefficient": round(coefficients[field], 10),
                "score_contribution": round(delta * coefficients[field], 8),
            }
            for field, delta in transition["changed_attributes"].items()
        ]
        for item in contributions:
            item["percent_of_score_movement"] = (
                round(100 * item["score_contribution"] / movement, 6) if movement else None
            )
        contributions.sort(key=lambda item: (-item["score_contribution"], item["attribute"]))
        observed = transition["observed_ovr_movement"]
        minimum = observed - 1
        maximum = observed + 1
        rows.append(
            {
                "lower_qb_id": transition["lower_qb_id"],
                "upper_qb_id": transition["upper_qb_id"],
                "latent_score_movement": round(movement, 8),
                "observed_ovr_movement": observed,
                "ordinary_rounding_movement_interval": {
                    "lower_exclusive": minimum,
                    "upper_exclusive": maximum,
                    "note": (
                        "Necessary range across two independently unknown positions inside "
                        "their observed rounding bands; it is not a sufficient constraint."
                    ),
                },
                "movement_compatible": minimum < movement < maximum,
                "contributions": contributions,
                "contribution_sum": round(
                    sum(item["score_contribution"] for item in contributions), 8
                ),
            }
        )
    return rows


def _cross_card_test(
    observations: list[dict[str, Any]],
    parameters: dict[str, Any],
    offset: float | None,
) -> dict[str, Any]:
    comparable = [
        card
        for card in observations
        if card["qb_id"] not in CHAIN_IDS
        and card["archetype"] == "Pocket Passer"
        and 79 <= card["overall"] <= 86
    ]
    rows = []
    for card in sorted(comparable, key=lambda item: item["qb_id"]):
        latent = _score(card, parameters, "A")
        before = round_half_up(latent)
        after = None if offset is None else round_half_up(latent + offset)
        rows.append(
            {
                "qb_id": card["qb_id"],
                "overall": card["overall"],
                "program": card["program"],
                "latent_score": round(latent, 8),
                "baseline_prediction": before,
                "offset_prediction": after,
                "baseline_absolute_error": abs(before - card["overall"]),
                "offset_absolute_error": (None if after is None else abs(after - card["overall"])),
            }
        )
    improved = sum(
        row["offset_absolute_error"] is not None
        and row["offset_absolute_error"] < row["baseline_absolute_error"]
        for row in rows
    )
    damaged = sum(
        row["offset_absolute_error"] is not None
        and row["offset_absolute_error"] > row["baseline_absolute_error"]
        for row in rows
    )
    return {
        "selection_rule": "Non-Harrington Pocket Passers with observed OVR 79 through 86.",
        "hypothetical_offset": offset,
        "offset_was_not_optimized_on_comparables": True,
        "count": len(rows),
        "improved_count": improved,
        "damaged_count": damaged,
        "unchanged_count": len(rows) - improved - damaged if offset is not None else 0,
        "not_evaluated_count": len(rows) if offset is None else 0,
        "interpretation": (
            "Not applied because no single Harrington offset is feasible."
            if offset is None
            else "Descriptive application of the Harrington feasible-interval midpoint."
        ),
        "cards": rows,
    }


def _madden_comparison(
    workbook_path: str | Path, transitions: list[dict[str, Any]]
) -> dict[str, Any]:
    rows = [
        record.values
        for record in WorkbookImporter(workbook_path).records("Madden19_QB_Weights")
        if record.values["Attribute"] in QB_RATING_FIELDS
    ]
    columns = ("Field General", "Scrambler", "Strong Arm", "West Coast")
    weights = {column: {row["Attribute"]: float(row[column]) for row in rows} for column in columns}
    return {
        "available": True,
        "source_sheet": "Madden19_QB_Weights",
        "historical_reference_only": True,
        "cfb_archetype_mapping_assumed": False,
        "movements": {
            column: [
                {
                    "lower_qb_id": transition["lower_qb_id"],
                    "upper_qb_id": transition["upper_qb_id"],
                    "weighted_rating_movement": round(
                        sum(
                            weights[column][field] * delta
                            for field, delta in transition["rating_deltas"].items()
                        ),
                        8,
                    ),
                    "observed_ovr_movement": transition["observed_ovr_movement"],
                }
                for transition in transitions
            ]
            for column in columns
        },
    }


def _proportional_comparison(rows: list[dict[str, Any]]) -> dict[str, Any]:
    measures = {
        "total_raw_rating_points": [row["total_raw_rating_points"] for row in rows],
        "weighted_rating_points_architecture_a": [
            row["architecture_a_weighted_movement"] for row in rows
        ],
        "changed_attribute_count": [row["changed_attribute_count"] for row in rows],
        "mean_changed_attribute_delta": [row["mean_changed_attribute_delta"] for row in rows],
    }
    targets = [row["observed_ovr_movement"] for row in rows]
    results = {}
    for name, values in measures.items():
        scale = sum(x * y for x, y in zip(values, targets, strict=True)) / sum(
            x * x for x in values
        )
        predictions = [scale * value for value in values]
        results[name] = {
            "proportional_scale": round(scale, 10),
            "scaled_predictions": [round(value, 8) for value in predictions],
            "root_mean_squared_error": round(
                math.sqrt(
                    fmean(
                        (prediction - target) ** 2
                        for prediction, target in zip(predictions, targets, strict=True)
                    )
                ),
                8,
            ),
        }
    ordered = sorted(results, key=lambda name: (results[name]["root_mean_squared_error"], name))
    return {
        "proportional_no_intercept_comparisons": results,
        "best_descriptive_representations": [
            name
            for name in ordered
            if results[name]["root_mean_squared_error"]
            == results[ordered[0]]["root_mean_squared_error"]
        ],
        "interpretation": (
            "Total points and mean changed-attribute delta are equivalent here because "
            "all transitions change exactly 12 attributes. Count alone cannot explain the "
            "different +2/+3/+2 movements; this is descriptive, not a fitted formula."
        ),
    }


def build_harrington_analysis(
    research: dict[str, Any],
    model_comparison: dict[str, Any],
    provenance_audit: dict[str, Any],
    workbook_path: str | Path,
) -> dict[str, Any]:
    """Analyze the confirmed chain with frozen A/C parameters and no model search."""
    cards = {card["qb_id"]: card for card in research["observations"]}
    chain = [cards[qb_id] for qb_id in CHAIN_IDS]
    if {(card["player"], card["program"], card["archetype"]) for card in chain} != {
        ("Joey Harrington", "SI Legends - Millennium", "Pocket Passer")
    }:
        raise ValueError("Canonical Harrington states do not form the confirmed chain.")
    confirmed_pairs = {
        (item["lower_qb_id"], item["upper_qb_id"])
        for item in provenance_audit["confirmed_constraints"]
    }
    expected_pairs = set(zip(CHAIN_IDS[:-1], CHAIN_IDS[1:], strict=True))
    if confirmed_pairs != expected_pairs:
        raise ValueError("Provenance audit does not confirm the complete Harrington chain.")

    transitions = [
        _transition(lower, upper) for lower, upper in zip(chain[:-1], chain[1:], strict=True)
    ]
    architectures = {}
    for architecture in ARCHITECTURES:
        parameters = _architecture_parameters(model_comparison, architecture)
        states = _state_scores(chain, parameters, architecture)
        offset = _offset_test(states)
        architectures[architecture] = {
            "parameters_source": "existing qb_model_comparison artifact",
            "refitted_to_harrington": False,
            "state_scores": states,
            "transitions": _model_transitions(transitions, states, _raw_coefficients(parameters)),
            "local_offset": offset,
            "parameter_count": (16 if architecture == "A" else 16 + len(parameters["modifiers"])),
        }

    a_offset = architectures["A"]["local_offset"]["descriptive_midpoint_offset"]
    magnitude = [
        {
            "lower_qb_id": transition["lower_qb_id"],
            "upper_qb_id": transition["upper_qb_id"],
            "observed_ovr_movement": transition["observed_ovr_movement"],
            "total_raw_rating_points": transition["total_raw_rating_point_increase"],
            "changed_attribute_count": transition["changed_attribute_count"],
            "mean_changed_attribute_delta": transition["mean_change_among_changed"],
            "architecture_a_weighted_movement": architectures["A"]["transitions"][index][
                "latent_score_movement"
            ],
        }
        for index, transition in enumerate(transitions)
    ]
    return {
        "schema_version": 1,
        "phase": "QB Formula Phase — Controlled Harrington Progression Constraint Analysis",
        "formula_status": "unsolved",
        "global_formula_search_performed": False,
        "new_interactions_added": False,
        "chain": [
            {
                **_card_summary(card),
                "progression_confirmed": True,
                "progression_evidence": [
                    "QB_Progression",
                    "Progression_Logs",
                    "Research_Findings!QB-F-009",
                ],
            }
            for card in chain
        ],
        "transitions": transitions,
        "architectures": architectures,
        "magnitude_comparison": {
            "transitions": magnitude,
            **_proportional_comparison(magnitude),
        },
        "constant_effect": {
            "mathematically_permitted_for_a": architectures["A"]["local_offset"]["feasible"],
            "mathematically_permitted_for_c": architectures["C"]["local_offset"]["feasible"],
            "interpretation": (
                "A state-invariant additive effect preserves all transition movements. "
                "Feasibility does not identify whether a program, archetype, tier, or other "
                "effect exists."
            ),
            "production_effect_claimed": False,
        },
        "cross_card_consequences": _cross_card_test(
            research["observations"],
            _architecture_parameters(model_comparison, "A"),
            a_offset,
        ),
        "madden_reference": _madden_comparison(workbook_path, transitions),
        "information_value": {
            "strong_constraints": [
                "Aggregate score response across the 12 jointly changing attributes.",
                "Local linearity and relative movement across three confirmed transitions.",
                "Whether one additive calibration shift can classify all four states.",
            ],
            "weak_or_unidentified": [
                "Relative weights among attributes that move together.",
                "Weights for invariant AWR, TAC, and TGH.",
                "Archetype, program, or tier effects from one player/program chain.",
                "Exact hidden score thresholds within observed OVR bands.",
            ],
        },
        "next_experiment": {
            "recommendation": (
                "Acquire a source-confirmed same-program Pocket Passer upgrade where only "
                "2–4 ratings change and the displayed OVR moves exactly one point."
            ),
            "maximally_informative_if": [
                "Changed attributes differ from Harrington's near-uniform bundle.",
                "At least one of AWR, TAC, or TGH changes.",
                "Before/after images explicitly prove one upgrade chain.",
                "Both states lie near an independently populated OVR boundary.",
            ],
            "distinguishes": (
                "Aggregate-weight correctness from a constant calibration effect and begins "
                "separating individual attribute contributions."
            ),
        },
    }


def write_harrington_artifacts(directory: str | Path, analysis: dict[str, Any]) -> None:
    """Write deterministic, non-overlapping controlled-progression artifacts."""
    root = Path(directory)
    root.mkdir(parents=True, exist_ok=True)
    payloads = {
        "qb_harrington_chain.json": analysis["chain"],
        "qb_harrington_transition_deltas.json": analysis["transitions"],
        "qb_harrington_architecture_scores.json": analysis["architectures"],
        "qb_harrington_contributions.json": {
            architecture: value["transitions"]
            for architecture, value in analysis["architectures"].items()
        },
        "qb_harrington_local_offset.json": {
            architecture: value["local_offset"]
            for architecture, value in analysis["architectures"].items()
        },
        "qb_harrington_inequalities.json": {
            architecture: [
                {
                    key: transition[key]
                    for key in (
                        "lower_qb_id",
                        "upper_qb_id",
                        "latent_score_movement",
                        "observed_ovr_movement",
                        "ordinary_rounding_movement_interval",
                        "movement_compatible",
                    )
                }
                for transition in value["transitions"]
            ]
            for architecture, value in analysis["architectures"].items()
        },
        "qb_harrington_cross_card_consequences.json": analysis["cross_card_consequences"],
        "qb_harrington_madden_reference.json": analysis["madden_reference"],
        "qb_harrington_information_value.json": analysis["information_value"],
        "qb_harrington_next_experiment.json": analysis["next_experiment"],
        "qb_harrington_analysis_summary.json": {
            key: value
            for key, value in analysis.items()
            if key
            not in {
                "chain",
                "transitions",
                "architectures",
                "cross_card_consequences",
                "madden_reference",
                "information_value",
                "next_experiment",
            }
        },
    }
    for name, payload in payloads.items():
        (root / name).write_text(
            json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
