"""Saturday Reset context reconstruction and TE progression resolution."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from operation_pancake.importers.workbook_importer import WorkbookImporter

UNRESOLVED = "UNRESOLVED"
TE_CANDIDATE_IDS = {
    ("TE-0020", "TE-0011"): "TE-EFINLEY-83-84",
    ("TE-0048", "TE-0038"): None,
    ("TE-0037", "TE-0013"): None,
}
SPARSE_IDS = ("SAT-01B", "SAT-08B", "SAT-02", "SAT-05", "SAT-04", "SAT-06", "SAT-06B")


def _rows(workbook: str | Path, sheet: str) -> list[dict[str, Any]]:
    return [record.values for record in WorkbookImporter(workbook).records(sheet)]


def _source_registry(workbook: str | Path) -> dict[str, dict[str, Any]]:
    return {row["Source_ID"]: row for row in _rows(workbook, "Source_Registry")}


def _reset_linkages(
    transitions: list[dict[str, Any]], registry: dict[str, dict[str, Any]], files: list[str]
) -> list[dict[str, Any]]:
    repository_names = {Path(path).name.casefold() for path in files}
    results = []
    for series_number in range(1, 12):
        series_id = f"SAT-{series_number:02d}"
        rows = [
            item for item in transitions if item["transition_id"] in {series_id, f"{series_id}B"}
        ]
        source = registry[rows[0]["source_id"]]
        source_file = str(source["Source_File"])
        results.append(
            {
                "reset_id": series_id,
                "transition_ids": [item["transition_id"] for item in rows],
                "transitions": rows,
                "classification": UNRESOLVED,
                "classification_reason": (
                    "Progression_Logs confirms controlled transitions but supplies no player, "
                    "card, position, archetype, program, timestamp, or full vectors."
                ),
                "source_id": rows[0]["source_id"],
                "source_file": source_file,
                "source_pages": sorted({str(item["source_locator"]) for item in rows}),
                "raw_source_present": source_file.casefold() in repository_names,
                "repository_references": [
                    "Source_Registry!SRC-HIST-001",
                    *[f"Progression_Logs!{item['transition_id']}" for item in rows],
                    "data/research/progression_audit",
                ],
                "recovered_context": {
                    "player_or_card_id": None,
                    "position": None,
                    "archetype": None,
                    "program": None,
                    "timestamp_or_date": None,
                    "primary_secondary_designation": None,
                },
                "full_vectors": {
                    "start": {"status": "MISSING", "ratings": None},
                    "intermediate": {"status": "MISSING", "ratings": None},
                    "end": {"status": "MISSING", "ratings": None},
                },
            }
        )
    return results


def _te_classifications(
    candidates: list[dict[str, Any]], cards: list[dict[str, Any]], logs: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    by_id = {card["card_id"]: card for card in cards}
    log_by_id = {row["Record_ID"]: row for row in logs}
    results = []
    for candidate in candidates:
        pair = (candidate["lower_card_id"], candidate["upper_card_id"])
        if candidate["position"] != "TE" or pair not in TE_CANDIDATE_IDS:
            continue
        lower, upper = by_id[pair[0]], by_id[pair[1]]
        log_id = TE_CANDIDATE_IDS[pair]
        references = [
            f"TE_Cards!{lower['card_id']}",
            f"TE_Cards!{upper['card_id']}",
        ]
        reason = (
            "Same player, program, and archetype with complete observed vectors, but no "
            "repository record explicitly establishes an upgrade relationship."
        )
        if log_id:
            references.append(f"Progression_Logs!{log_id}")
            reason = (
                "The progression log explicitly labels this only a same-player card "
                "comparison and warns that the TGH decrease may indicate distinct tuning."
            )
        decreases = {
            field: value for field, value in candidate["attribute_deltas"].items() if value < 0
        }
        results.append(
            {
                "player": candidate["player"],
                "lower_te_id": pair[0],
                "upper_te_id": pair[1],
                "program": candidate["lower_program"],
                "archetype": candidate["archetype"],
                "ovr_sequence": [candidate["start_ovr"], candidate["end_ovr"]],
                "lower_vector": lower["attributes"],
                "upper_vector": upper["attributes"],
                "vector_provenance": "DIRECTLY_OBSERVED",
                "attribute_deltas": candidate["attribute_deltas"],
                "negative_deltas": decreases,
                "classification": UNRESOLVED,
                "classification_reason": reason,
                "provenance_references": references,
                "source_ids": sorted({lower["source_id"], upper["source_id"]}),
                "source_locators": [lower["source_locator"], upper["source_locator"]],
                "progression_metadata": log_by_id.get(log_id) if log_id else None,
                "actual_upgrade_chain_established": False,
            }
        )
    return sorted(results, key=lambda item: item["lower_te_id"])


def _template_analysis(transitions: list[dict[str, Any]]) -> dict[str, Any]:
    resets = [item for item in transitions if item["transition_id"].startswith("SAT-")]
    templates = Counter(tuple(sorted(item["attribute_deltas"].items())) for item in resets)
    return {
        "exact_templates": [
            {
                "attribute_deltas": dict(template),
                "frequency": count,
                "transition_ids": [
                    item["transition_id"]
                    for item in resets
                    if tuple(sorted(item["attribute_deltas"].items())) == template
                ],
                "ovr_transitions": sorted(
                    {
                        f"{item['start_ovr']}→{item['end_ovr']}"
                        for item in resets
                        if tuple(sorted(item["attribute_deltas"].items())) == template
                    }
                ),
            }
            for template, count in sorted(templates.items(), key=lambda item: str(item[0]))
        ],
        "repeated_exact_template_count": sum(count > 1 for count in templates.values()),
        "raw_positive_point_range": [
            min(item["total_positive_rating_points"] for item in resets),
            max(item["total_positive_rating_points"] for item in resets),
        ],
        "interpretations": {
            "raw_rating_point_totals": (
                "Not sufficient: totals vary from 1 to 26 for the same +1 displayed OVR."
            ),
            "weighted_hidden_score_increments": (
                "Plausible but unproven because positions, weights, and starting band "
                "locations are absent."
            ),
            "fixed_upgrade_templates": (
                "Not generally supported: only the +2 PBP bundle repeats exactly."
            ),
            "targeted_boundary_crossing": (
                "Consistent with all 22 records ending exactly one OVR higher, but source "
                "selection and starting hidden scores are unknown."
            ),
            "primary_secondary_groups": (
                "Not testable: no primary/secondary designation exists in the records."
            ),
        },
    }


def build_reset_context_audit(
    progression_audit: dict[str, Any], workbook: str | Path, repository_files: list[str]
) -> dict[str, Any]:
    """Resolve all repository-supported context without inventing missing linkages."""
    transitions = progression_audit["confirmed_transitions"]
    candidates = progression_audit["progression_candidates"]
    cards = progression_audit["canonical_cards"]
    logs = _rows(workbook, "Progression_Logs")
    registry = _source_registry(workbook)
    linkages = _reset_linkages(transitions, registry, repository_files)
    te = _te_classifications(candidates, cards, logs)
    sparse = [
        {
            **next(item for item in transitions if item["transition_id"] == transition_id),
            "context_linkage": UNRESOLVED,
            "positional_information_value": "UNASSIGNABLE",
            "reason": (
                "Sparse +1 OVR evidence is preserved, but absent player, position, "
                "archetype, program, and full starting vector prevent positional use."
            ),
        }
        for transition_id in SPARSE_IDS
    ]
    return {
        "schema_version": 1,
        "phase": "Saturday Reset Context Reconstruction & TE Progression Resolution",
        "formula_fitting_performed": False,
        "reset_linkages": linkages,
        "reconstructed_vectors": [
            {
                "reset_id": item["reset_id"],
                "vectors": item["full_vectors"],
                "known_transition_deltas": [
                    {
                        "transition_id": transition["transition_id"],
                        "status": "DIRECTLY_OBSERVED",
                        "attribute_deltas": transition["attribute_deltas"],
                    }
                    for transition in item["transitions"]
                ],
            }
            for item in linkages
        ],
        "position_archetype_context": [
            {
                "reset_id": item["reset_id"],
                **item["recovered_context"],
                "status": "MISSING",
            }
            for item in linkages
        ],
        "sparse_transitions": sparse,
        "te_progression_classifications": te,
        "te_research_implications": {
            "confirmed_transition_count": 0,
            "new_boundary_constraints": [],
            "formula_refit_performed": False,
            "descriptive_observations": [
                "Eli Finley and Jalen Hoffman each show a TGH decrease, consistent with "
                "distinct card tuning rather than a clean monotonic upgrade template.",
                "Ozzie Newsome has a uniform +3 bundle on 28 attributes with AWR/TGH "
                "unchanged, but provenance does not establish progression.",
            ],
        },
        "reset_template_analysis": _template_analysis(transitions),
        "source_gaps": {
            "REFERENCED_BUT_RAW_SOURCE_ABSENT": [
                {
                    "scope": "SAT-01 through SAT-11",
                    "source_id": "SRC-HIST-001",
                    "source_file": "history(4).pdf",
                    "required": [
                        "Source PDF pages 4, 5, 13, and 14",
                        "Originating player/card identity and position",
                        "Archetype/program context",
                        "Complete before/intermediate/after vectors",
                        "Any primary/secondary labels and timestamps",
                    ],
                }
            ],
            "NO_REFERENCE_EXISTS": [
                {
                    "scope": f"{item['lower_te_id']}→{item['upper_te_id']}",
                    "required": (
                        "Explicit upgrade-chain identifier or source evidence linking the "
                        "two observed card states."
                    ),
                }
                for item in te
            ],
        },
        "canonical_observations_modified": False,
        "unsupported_linkages_promoted": False,
    }


def write_reset_context_artifacts(directory: str | Path, audit: dict[str, Any]) -> None:
    """Write deterministic context-reconstruction artifacts."""
    root = Path(directory)
    root.mkdir(parents=True, exist_ok=True)
    payloads = {
        "reset_linkage_classifications.json": audit["reset_linkages"],
        "reset_reconstructed_vectors.json": audit["reconstructed_vectors"],
        "reset_position_archetype_context.json": audit["position_archetype_context"],
        "reset_sparse_transition_inventory.json": audit["sparse_transitions"],
        "te_progression_classifications.json": audit["te_progression_classifications"],
        "reset_template_analysis.json": audit["reset_template_analysis"],
        "reset_te_source_gaps.json": audit["source_gaps"],
        "reset_context_audit_summary.json": {
            key: value
            for key, value in audit.items()
            if key
            not in {
                "reset_linkages",
                "reconstructed_vectors",
                "position_archetype_context",
                "sparse_transitions",
                "te_progression_classifications",
                "reset_template_analysis",
                "source_gaps",
            }
        },
    }
    for name, payload in payloads.items():
        (root / name).write_text(
            json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
