"""Jeff Saturday controlled Center reconstruction from recovered historical evidence."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

RECOVERED_BASE = {
    "PBK": 82,
    "PBF": 78,
    "PBP": 83,
    "RBK": 78,
    "RBF": 74,
    "RBP": 75,
    "IBL": 76,
    "LBK": 78,
    "STR": 82,
    "AWR": 70,
    "SPD": 65,
    "ACC": 57,
    "AGI": 64,
    "COD": 65,
}
CENTER_ATTRIBUTES = (
    "SPD",
    "ACC",
    "AGI",
    "COD",
    "AWR",
    "STR",
    "TGH",
    "RBK",
    "RBF",
    "RBP",
    "PBK",
    "PBF",
    "PBP",
    "LBK",
    "IBL",
)
SPARSE_IDS = ("SAT-01B", "SAT-08B", "SAT-02", "SAT-05", "SAT-04", "SAT-06", "SAT-06B")


def _state(vector: dict[str, int | None], derived: set[str], base: bool = False) -> dict[str, Any]:
    return {
        field: {
            "value": vector.get(field),
            "status": (
                "UNKNOWN"
                if vector.get(field) is None
                else "DIRECTLY_OBSERVED"
                if base or field not in derived
                else "DERIVED_FROM_CONFIRMED_DELTA"
            ),
        }
        for field in CENTER_ATTRIBUTES
    }


def _apply(
    vector: dict[str, int | None], deltas: dict[str, int]
) -> tuple[dict[str, int | None], set[str], list[str]]:
    result = dict(vector)
    derived, unknown_delta_fields = set(), []
    for field, delta in deltas.items():
        if field not in result or result[field] is None:
            unknown_delta_fields.append(field)
            continue
        result[field] += delta
        derived.add(field)
    return result, derived, unknown_delta_fields


def _series(transitions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id = {item["transition_id"]: item for item in transitions}
    results = []
    base_vector = {field: RECOVERED_BASE.get(field) for field in CENTER_ATTRIBUTES}
    for number in range(1, 12):
        reset_id = f"SAT-{number:02d}"
        first, second = by_id[reset_id], by_id[f"{reset_id}B"]
        at_81, derived_81, unknown_a = _apply(base_vector, first["attribute_deltas"])
        at_82, derived_b, unknown_b = _apply(at_81, second["attribute_deltas"])
        results.append(
            {
                "reset_id": reset_id,
                "player": "Jeff Saturday",
                "position": "C",
                "archetype": "Pass Protector",
                "trajectory_architecture": "FRESH_COMMON_80_BASELINE_THEN_SEQUENTIAL_A_B",
                "architecture_evidence": (
                    "Recovered historical evidence identifies common Jeff Saturday 80 OVR "
                    "experiments; log A is 80→81 and matching B is 81→82."
                ),
                "states": [
                    {"overall": 80, "ratings": _state(base_vector, set(), base=True)},
                    {"overall": 81, "ratings": _state(at_81, derived_81)},
                    {"overall": 82, "ratings": _state(at_82, derived_81 | derived_b)},
                ],
                "transition_ids": [first["transition_id"], second["transition_id"]],
                "unknown_delta_fields": sorted(set(unknown_a + unknown_b)),
            }
        )
    return results


def _transition_matrix(transitions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            **item,
            "player": "Jeff Saturday",
            "position": "C",
            "archetype": "Pass Protector",
            "linkage_status": "CONFIRMED",
            "full_relevant_center_vector_known": False,
            "missing_center_attributes": ["TGH"],
            "information_value": (
                "HIGH_SPARSE_BOUNDARY"
                if item["transition_id"] in SPARSE_IDS
                else "CONTROLLED_BOUNDARY"
            ),
        }
        for item in transitions
        if item["transition_id"].startswith("SAT-")
    ]


def _sparse_analysis(matrix: list[dict[str, Any]]) -> list[dict[str, Any]]:
    conclusions = {
        "SAT-01B": (
            "PBF is locally OVR-sensitive under this trajectory; coefficient magnitude is "
            "unidentified."
        ),
        "SAT-08B": (
            "PBP is locally OVR-sensitive under this trajectory; coefficient magnitude is "
            "unidentified."
        ),
        "SAT-02": "A +2 PBP change crosses 80→81 from the common base.",
        "SAT-05": "Replicates the +2 PBP 80→81 result from the common base.",
        "SAT-04": (
            "A +6 PBF change crosses 80→81; comparison with +1 PBF uses different hidden starts."
        ),
        "SAT-06": (
            "A +5 PBP change crosses 80→81; larger delta does not imply a larger displayed jump."
        ),
        "SAT-06B": "PBK is locally OVR-sensitive at this trajectory's 81 state.",
    }
    return [
        {
            **next(item for item in matrix if item["transition_id"] == transition_id),
            "legitimate_conclusion": conclusions[transition_id],
            "explanations_remaining": [
                "positive positional weight",
                "proximity to an OVR threshold",
                "trajectory-specific starting hidden score",
                "discrete or nonlinear score conversion",
            ],
            "one_rating_point_equals_one_ovr": False,
        }
        for transition_id in SPARSE_IDS
    ]


def build_saturday_center_analysis(
    progression_audit: dict[str, Any], previous_audit: dict[str, Any]
) -> dict[str, Any]:
    """Integrate recovered evidence while preserving the repository-only audit result."""
    transitions = progression_audit["confirmed_transitions"]
    matrix = _transition_matrix(transitions)
    canonical_centers = [
        card for card in progression_audit["canonical_cards"] if card["position"] == "C"
    ]
    return {
        "schema_version": 1,
        "phase": "Jeff Saturday Controlled Center Reconstruction",
        "evidence_record": {
            "provenance_type": "USER_SUPPLIED_RECOVERED_HISTORICAL_OPERATION_PANCAKE_EVIDENCE",
            "ingested_date": "2026-08-13",
            "player": {"value": "Jeff Saturday", "status": "HISTORICALLY_RECOVERED"},
            "position": {"value": "C", "status": "HISTORICALLY_RECOVERED"},
            "archetype": {"value": "Pass Protector", "status": "HISTORICALLY_RECOVERED"},
            "starting_overall": {"value": 80, "status": "HISTORICALLY_RECOVERED"},
            "base_ratings": {
                field: {
                    "value": RECOVERED_BASE.get(field),
                    "status": "HISTORICALLY_RECOVERED" if field in RECOVERED_BASE else "UNKNOWN",
                }
                for field in CENTER_ATTRIBUTES
            },
            "reset_deltas_status": "REPOSITORY_CONFIRMED",
            "previous_repository_only_result_preserved": {
                "classification": "UNRESOLVED",
                "artifact": "data/research/reset_context_audit/reset_linkage_classifications.json",
                "reason": "Repository-accessible evidence alone did not identify reset context.",
            },
        },
        "reset_linkages": [
            {
                "reset_id": item["reset_id"],
                "classification": "CONFIRMED",
                "player": "Jeff Saturday",
                "position": "C",
                "archetype": "Pass Protector",
                "reason": (
                    "Newly supplied recovered historical Operation Pancake evidence links "
                    "the Saturday Reset experiments to Jeff Saturday Center research."
                ),
                "repository_delta_records": item["transition_ids"],
                "prior_repository_only_classification": item["classification"],
            }
            for item in previous_audit["reset_linkages"]
        ],
        "trajectory_architecture": {
            "classification": "FRESH_COMMON_80_BASELINE_THEN_SEQUENTIAL_A_B",
            "series_are_independent": True,
            "within_series_b_follows_a": True,
            "confidence": "HIGH",
            "reason": (
                "Each numbered A record starts 80→81; its B record continues 81→82. "
                "Recovered evidence supplies one common Jeff Saturday 80 OVR base."
            ),
        },
        "reconstructed_series": _series(transitions),
        "center_transition_matrix": matrix,
        "sparse_boundary_analysis": _sparse_analysis(matrix),
        "weight_constraints": {
            "direct_local_sensitivity": ["PBK", "PBF", "PBP"],
            "bundle_only_constraints": [
                "RBK",
                "RBF",
                "RBP",
                "IBL",
                "LBK",
                "STR",
                "AWR",
                "SPD",
                "ACC",
                "AGI",
                "COD",
            ],
            "unidentifiable": [
                "TGH",
                "RCK meaning",
                "exact weights",
                "hidden starting scores",
                "score-to-OVR thresholds",
            ],
            "inequality_interpretation": (
                "Each positive bundle was sufficient to cross its observed +1 OVR boundary "
                "from that trajectory state. Unknown hidden-band locations prevent numeric "
                "coefficient lower bounds or cross-trajectory coefficient ratios."
            ),
            "single_attribute_evidence": {
                "PBF": ["SAT-01B +1", "SAT-04 +6"],
                "PBP": ["SAT-08B +1", "SAT-02/SAT-05 +2", "SAT-06 +5"],
                "PBK": ["SAT-06B +4"],
            },
        },
        "center_model_comparison": {
            "canonical_center_observations": canonical_centers,
            "canonical_count": len(canonical_centers),
            "canonical_archetypes": sorted({card["archetype"] for card in canonical_centers}),
            "saturday_archetype_represented_in_canonical_cards": False,
            "repository_available_named_evidence": [
                "Ashton Beers",
                "Justin Evans",
                "Bruce Mitchell",
            ],
            "repository_unavailable_named_evidence": ["Brady Small", "Hinzman"],
            "madden_center_weight_reference_available": False,
            "assessment": (
                "Saturday adds strong Pass Protector local-boundary evidence, while all three "
                "canonical Centers are Raw Strength at OVR 84–85. The evidence layers do not "
                "provide an independent Pass Protector validation population or sufficient "
                "cross-OVR static coverage for a defensible Center formula fit."
            ),
            "candidate_model_tested": False,
        },
        "center_formula_status": "INSUFFICIENT EVIDENCE",
        "remaining_unknowns": [
            "Jeff Saturday TGH at every state",
            "RCK meaning and baseline in SAT-11B",
            "Exact hidden scores and threshold locations",
            "Independent Pass Protector Center observations",
            "Repository copies of Brady Small, Hinzman, and Madden-derived Center work",
        ],
        "formula_fitting_performed": False,
        "canonical_observations_modified": False,
        "unknown_ratings_guessed": False,
    }


def write_saturday_center_artifacts(directory: str | Path, analysis: dict[str, Any]) -> None:
    """Write deterministic Center reconstruction artifacts without replacing prior audits."""
    root = Path(directory)
    root.mkdir(parents=True, exist_ok=True)
    payloads = {
        "saturday_recovered_identity_provenance.json": analysis["evidence_record"],
        "saturday_recovered_base_ratings.json": analysis["evidence_record"]["base_ratings"],
        "saturday_reset_linkages.json": analysis["reset_linkages"],
        "saturday_reconstructed_states.json": analysis["reconstructed_series"],
        "saturday_center_transition_matrix.json": analysis["center_transition_matrix"],
        "saturday_sparse_boundary_analysis.json": analysis["sparse_boundary_analysis"],
        "saturday_center_model_comparison.json": analysis["center_model_comparison"],
        "saturday_center_weight_constraints.json": analysis["weight_constraints"],
        "saturday_center_remaining_unknowns.json": analysis["remaining_unknowns"],
        "saturday_center_analysis_summary.json": {
            key: value
            for key, value in analysis.items()
            if key
            not in {
                "evidence_record",
                "reset_linkages",
                "reconstructed_series",
                "center_transition_matrix",
                "sparse_boundary_analysis",
                "weight_constraints",
                "center_model_comparison",
                "remaining_unknowns",
            }
        },
    }
    for name, payload in payloads.items():
        (root / name).write_text(
            json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
