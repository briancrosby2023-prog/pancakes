"""Source-supported QB progression, provenance, and evidence-gap audit."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from operation_pancake.importers.workbook_importer import WorkbookImporter
from operation_pancake.research.qb_formula_phase import QB_RATING_FIELDS

CONFIRMED = "CONFIRMED_PROGRESSION"
PROBABLE = "PROBABLE_PROGRESSION"
UNRESOLVED = "UNRESOLVED"
CONTRADICTED = "CONTRADICTED"

SYSTEMATIC_ERROR_QB_IDS = (
    "QB-0016",
    "QB-0033",
    "QB-0034",
    "QB-0070",
    "QB-0071",
    "QB-0002",
    "QB-0005",
)

HIGH_INFORMATION_PAIRS = (
    ("QB-0013", "QB-0003"),
    ("QB-0038", "QB-0013"),
    ("QB-0050", "QB-0007"),
    ("QB-0027", "QB-0071"),
    ("QB-0010", "QB-0073"),
)

CONFIRMED_JOEY_LINKS = {
    ("QB-0074", "QB-0038"): "QB-JH-79-81",
    ("QB-0038", "QB-0013"): "QB-JH-81-84",
    ("QB-0013", "QB-0003"): "QB-JH-84-86",
}


def _records(workbook_path: str | Path, sheet: str) -> list[dict[str, Any]]:
    return [record.values for record in WorkbookImporter(workbook_path).records(sheet)]


def _source_registry(workbook_path: str | Path) -> dict[str, dict[str, Any]]:
    return {row["Source_ID"]: row for row in _records(workbook_path, "Source_Registry")}


def _cards(research: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {card["qb_id"]: card for card in research["observations"]}


def _delta(lower: dict[str, Any], upper: dict[str, Any]) -> dict[str, Any]:
    changes = {
        field: upper["ratings"][field] - lower["ratings"][field] for field in QB_RATING_FIELDS
    }
    return {
        "ovr_change": upper["overall"] - lower["overall"],
        "rating_changes": changes,
        "total_positive_rating_movement": sum(max(0, value) for value in changes.values()),
        "total_negative_rating_movement": sum(min(0, value) for value in changes.values()),
        "unchanged_ratings": [field for field, value in changes.items() if value == 0],
        "changed_rating_count": sum(value != 0 for value in changes.values()),
        "crosses_exactly_one_ovr_boundary": upper["overall"] - lower["overall"] == 1,
    }


def _meaningful_weights(model_comparison: dict[str, Any]) -> dict[str, float]:
    architecture_a = next(
        result for result in model_comparison["architectures"] if result["architecture"] == "A"
    )
    weights = architecture_a["parameterization"]["shared"]["standardized_nonnegative_weights"]
    return {field: value for field, value in weights.items() if value >= 0.1}


def _classification(
    lower: dict[str, Any], upper: dict[str, Any]
) -> tuple[str, str, list[dict[str, str]]]:
    pair = (lower["qb_id"], upper["qb_id"])
    if pair in CONFIRMED_JOEY_LINKS:
        record_id = CONFIRMED_JOEY_LINKS[pair]
        return (
            CONFIRMED,
            "Workbook QB_Progression and Progression_Logs explicitly identify validated "
            "same-program observed progression states.",
            [
                {"sheet": "QB_Progression", "record": record_id},
                {"sheet": "Progression_Logs", "record": record_id},
                {"sheet": "Research_Findings", "record": "QB-F-009"},
            ],
        )
    if lower["program"] != upper["program"]:
        return (
            CONTRADICTED,
            "The observations are explicitly different program/card variants. The source "
            "registry treats SRC-QB-001 rows as distinct card/version records, and no "
            "progression record links these programs.",
            [
                {"sheet": "Source_Registry", "record": "SRC-QB-001"},
                {"sheet": "QB_Cards", "record": lower["source_record"]},
                {"sheet": "QB_Cards", "record": upper["source_record"]},
            ],
        )
    return (
        UNRESOLVED,
        "Same player and program are present, but no explicit repository progression record "
        "links these observations.",
        [
            {"sheet": "QB_Cards", "record": lower["source_record"]},
            {"sheet": "QB_Cards", "record": upper["source_record"]},
        ],
    )


def _card_summary(card: dict[str, Any]) -> dict[str, Any]:
    return {
        "qb_id": card["qb_id"],
        "player": card["player"],
        "overall": card["overall"],
        "program": card["program"],
        "archetype": card["archetype"],
        "ratings": card["ratings"],
        "source_id": card["source_id"],
        "source_locator": card["source_locator"],
        "source_record": card["source_record"],
        "model_role": card["model_role"],
        "population_scope": card["population_scope"],
        "unique_profile_key": card["unique_profile_key"],
        "duplicate_note": card["duplicate_note"],
        "analysis_partition": card["analysis_partition"],
        "frozen_score_check": card["frozen_score_check"],
        "frozen_score_formula": card["frozen_score_formula"],
        "formula_delta": card["formula_delta"],
        "notes": None,
        "validation_status": (
            "No card-level validation field exists; canonical ingestion and research "
            "validation are preserved separately."
        ),
        "workbook_sheet": card["workbook_sheet"],
        "workbook_row": card["workbook_row"],
    }


def _sequence_audit(research: dict[str, Any], meaningful: dict[str, float]) -> list[dict[str, Any]]:
    cards = _cards(research)
    results = []
    for pair in research["boundary_evidence"]["same_player_card_sequences"]:
        lower, upper = cards[pair["lower_qb_id"]], cards[pair["upper_qb_id"]]
        classification, reason, references = _classification(lower, upper)
        delta = _delta(lower, upper)
        delta["meaningful_architecture_a_changes"] = {
            field: delta["rating_changes"][field]
            for field in meaningful
            if delta["rating_changes"][field] != 0
        }
        delta["constraint_value"] = (
            "Observed rating movement crossed the displayed OVR interval; exact weights "
            "are not inferred."
            if classification == CONFIRMED
            else "Not eligible as a progression constraint."
        )
        results.append(
            {
                "lower": _card_summary(lower),
                "upper": _card_summary(upper),
                "classification": classification,
                "classification_reason": reason,
                "provenance_references": references,
                "delta": delta,
                "high_information_priority": (
                    (lower["qb_id"], upper["qb_id"]) in HIGH_INFORMATION_PAIRS
                ),
            }
        )
    return results


def _confirmed_constraints(sequences: list[dict[str, Any]]) -> list[dict[str, Any]]:
    confirmed = [item for item in sequences if item["classification"] == CONFIRMED]
    return sorted(
        [
            {
                "lower_qb_id": item["lower"]["qb_id"],
                "upper_qb_id": item["upper"]["qb_id"],
                "player": item["lower"]["player"],
                "program": item["lower"]["program"],
                "ovr_change": item["delta"]["ovr_change"],
                "rating_changes": item["delta"]["rating_changes"],
                "changed_rating_count": item["delta"]["changed_rating_count"],
                "descriptive_constraint": (
                    "The observed combined rating change crosses the stated OVR interval; "
                    "unobserved intermediate thresholds remain unknown."
                ),
                "information_priority": round(
                    item["delta"]["ovr_change"] / max(item["delta"]["changed_rating_count"], 1),
                    8,
                ),
                "provenance_references": item["provenance_references"],
            }
            for item in confirmed
        ],
        key=lambda item: (-item["information_priority"], item["lower_qb_id"]),
    )


def _recovered_confirmed_constraints(
    cards: dict[str, dict[str, Any]], meaningful: dict[str, float]
) -> list[dict[str, Any]]:
    """Recover an explicit workbook link absent from heuristic consecutive pairs."""
    lower, upper = cards["QB-0074"], cards["QB-0038"]
    delta = _delta(lower, upper)
    return [
        {
            "lower_qb_id": lower["qb_id"],
            "upper_qb_id": upper["qb_id"],
            "player": lower["player"],
            "program": lower["program"],
            "ovr_change": delta["ovr_change"],
            "rating_changes": delta["rating_changes"],
            "meaningful_architecture_a_changes": {
                field: delta["rating_changes"][field]
                for field in meaningful
                if delta["rating_changes"][field] != 0
            },
            "changed_rating_count": delta["changed_rating_count"],
            "descriptive_constraint": (
                "The explicit workbook progression record links these states; the heuristic "
                "sequence list omitted the link because an unrelated same-player program "
                "occurs between their OVRs."
            ),
            "information_priority": round(
                delta["ovr_change"] / max(delta["changed_rating_count"], 1), 8
            ),
            "provenance_references": [
                {"sheet": "QB_Progression", "record": "QB-JH-79-81"},
                {"sheet": "Progression_Logs", "record": "QB-JH-79-81"},
                {"sheet": "Research_Findings", "record": "QB-F-009"},
            ],
            "recovered_outside_17_candidates": True,
        }
    ]


def _source_type(locator: str, registry_type: str) -> str:
    if locator.lower().endswith((".jpg", ".jpeg", ".png")) or "screenshot" in locator.lower():
        return "image"
    if ".pdf" in locator.lower() or "pdf" in registry_type.lower():
        return "pdf_page"
    return registry_type


def _source_inventory(
    sequences: list[dict[str, Any]],
    cards: dict[str, dict[str, Any]],
    registry: dict[str, dict[str, Any]],
    repository_files: set[str],
) -> list[dict[str, Any]]:
    target_ids = {"QB-0074", *SYSTEMATIC_ERROR_QB_IDS}
    for sequence in sequences:
        target_ids.update((sequence["lower"]["qb_id"], sequence["upper"]["qb_id"]))
    uses: dict[tuple[str, str], set[str]] = defaultdict(set)
    for qb_id in target_ids:
        card = cards[qb_id]
        uses[(card["source_id"], str(card["source_locator"]))].add(qb_id)
    inventory = []
    for (source_id, locator), qb_ids in sorted(uses.items()):
        entry = registry[source_id]
        source_file = str(entry.get("Source_File") or "")
        content_available = any(
            Path(path).name.casefold() == Path(source_file).name.casefold()
            for path in repository_files
        )
        sufficient = source_id == "SRC-QB-002" and set(qb_ids) == {"QB-0074"}
        inventory.append(
            {
                "source_id": source_id,
                "source_file": source_file,
                "locator": locator,
                "type": _source_type(locator, str(entry.get("Type") or "")),
                "registry_status": entry.get("Extraction_Status"),
                "source_content_directly_available_in_repository": content_available,
                "dependent_qb_ids": sorted(qb_ids),
                "sufficient_for_progression_confirmation": sufficient,
                "sufficiency_reason": (
                    "Workbook QB_Progression and Progression_Logs preserve an explicit "
                    "validated extraction from this source."
                    if sufficient
                    else "Card observation is supported, but this locator alone does not "
                    "explicitly link a progression relationship."
                ),
            }
        )
    return inventory


def _provenance_audit(card: dict[str, Any], repository_files: set[str]) -> dict[str, Any]:
    locator_name = Path(str(card["source_locator"])).name.casefold()
    direct = any(Path(path).name.casefold() == locator_name for path in repository_files)
    return {
        **_card_summary(card),
        "all_15_ratings_present": set(card["ratings"]) == set(QB_RATING_FIELDS),
        "overall_reliable": isinstance(card["overall"], int),
        "archetype_reliable": bool(card["archetype"]),
        "program_reliable": bool(card["program"]),
        "direct_source_locator_present": bool(card["source_locator"]),
        "source_content_directly_available_in_repository": direct,
        "formula_audit_matches": abs(card["formula_delta"]) < 1e-10,
    }


def build_provenance_audit(
    research: dict[str, Any],
    model_comparison: dict[str, Any],
    workbook_path: str | Path,
    repository_files: list[str],
) -> dict[str, Any]:
    """Build a deterministic evidence audit without inferring progression."""
    meaningful = _meaningful_weights(model_comparison)
    sequences = _sequence_audit(research, meaningful)
    cards = _cards(research)
    registry = _source_registry(workbook_path)
    file_set = set(repository_files)
    candidate_constraints = _confirmed_constraints(sequences)
    recovered_constraints = _recovered_confirmed_constraints(cards, meaningful)
    constraints = sorted(
        [*candidate_constraints, *recovered_constraints],
        key=lambda item: (-item["information_priority"], item["lower_qb_id"]),
    )
    inventory = _source_inventory(sequences, cards, registry, file_set)
    progression_logs = [
        row
        for row in _records(workbook_path, "Progression_Logs")
        if str(row.get("Record_ID", "")).startswith("QB-JH-")
    ]
    progression_pairs = {
        "QB-JH-79-81": ["QB-0074", "QB-0038"],
        "QB-JH-81-84": ["QB-0038", "QB-0013"],
        "QB-JH-84-86": ["QB-0013", "QB-0003"],
    }
    for row in progression_logs:
        source_id = row["Source_ID"]
        entry = registry[source_id]
        inventory.append(
            {
                "source_id": source_id,
                "source_file": entry.get("Source_File"),
                "locator": row["Source_Page"],
                "type": "image_pair",
                "registry_status": entry.get("Extraction_Status"),
                "source_content_directly_available_in_repository": False,
                "dependent_qb_ids": progression_pairs[row["Record_ID"]],
                "sufficient_for_progression_confirmation": True,
                "sufficiency_reason": (
                    "Progression_Logs explicitly labels this as same-program card "
                    "progression and QB_Progression preserves the validated states."
                ),
                "progression_record_id": row["Record_ID"],
            }
        )
    inventory.sort(key=lambda item: (item["source_id"], str(item["locator"])))
    unresolved = [item for item in sequences if item["classification"] == UNRESOLVED]
    backlog = [
        {
            "lower_qb_id": item["lower"]["qb_id"],
            "upper_qb_id": item["upper"]["qb_id"],
            "required_evidence": [
                "Source image or PDF pages showing both states as one upgrade chain",
                "Explicit before/after upgrade or level identifiers",
                "Confirmation that both observations belong to the same program/version chain",
            ],
            "referenced_sources": sorted({item["lower"]["source_id"], item["upper"]["source_id"]}),
        }
        for item in unresolved
    ]
    backlog.extend(
        [
            {
                "scope": "raw_source_preservation",
                "priority": "high",
                "qb_ids": ["QB-0074", "QB-0038", "QB-0013", "QB-0003"],
                "required_evidence": (
                    "Add the referenced SRC-QB-002 image archive to a controlled evidence "
                    "location for independent pixel-level re-verification."
                ),
                "current_status": (
                    "Workbook validation records support classification, but raw images "
                    "are absent from this repository."
                ),
            },
            {
                "scope": "systematic_error_source_reverification",
                "priority": "medium",
                "qb_ids": list(SYSTEMATIC_ERROR_QB_IDS),
                "required_evidence": (
                    "Preserve referenced SRC-QB-001 PDF pages for independent visual "
                    "transcription checks."
                ),
                "current_status": "The registered source PDF is absent from the repository.",
            },
        ]
    )
    return {
        "schema_version": 1,
        "phase": "QB Formula Phase — Progression, Provenance & High-Information Evidence Audit",
        "formula_expansion_performed": False,
        "sequence_classification_counts": dict(
            sorted(
                {
                    label: sum(item["classification"] == label for item in sequences)
                    for label in (CONFIRMED, PROBABLE, UNRESOLVED, CONTRADICTED)
                }.items()
            )
        ),
        "meaningful_architecture_a_weights": meaningful,
        "sequences": sequences,
        "candidate_confirmed_constraints": candidate_constraints,
        "recovered_confirmed_constraints": recovered_constraints,
        "confirmed_constraints": constraints,
        "qb_0074_provenance": {
            **_provenance_audit(cards["QB-0074"], file_set),
            "progression_relationship": (
                "Confirmed as the 79 OVR baseline of the Joey Harrington same-program "
                "79→81→84→86 chain."
            ),
            "progression_references": [
                "QB_Progression!QB-JH-79",
                "Progression_Logs!QB-JH-79-81",
                "Research_Findings!QB-F-009",
            ],
            "duplicate_profile_qb_ids": [],
            "transcription_or_mapping_issue_found": False,
        },
        "systematic_error_card_audits": [
            {
                **_provenance_audit(cards[qb_id], file_set),
                "progression_relationship_found": any(
                    qb_id in (constraint["lower_qb_id"], constraint["upper_qb_id"])
                    for constraint in constraints
                ),
                "profile_duplicate_qb_ids": [
                    other["qb_id"]
                    for other in cards.values()
                    if other["qb_id"] != qb_id
                    and other["unique_profile_key"] == cards[qb_id]["unique_profile_key"]
                ],
            }
            for qb_id in SYSTEMATIC_ERROR_QB_IDS
        ],
        "source_inventory": inventory,
        "evidence_acquisition_backlog": backlog,
        "workbook_progression_evidence": {
            "qb_progression_records": _records(workbook_path, "QB_Progression"),
            "progression_log_records": progression_logs,
            "qb_source_registry_records": [
                row
                for row in registry.values()
                if str(row.get("Source_ID", "")).startswith("SRC-QB")
            ],
        },
        "canonical_corrections_found": [],
    }


def write_provenance_artifacts(directory: str | Path, audit: dict[str, Any]) -> None:
    """Write separate deterministic progression and provenance artifacts."""
    root = Path(directory)
    root.mkdir(parents=True, exist_ok=True)
    payloads = {
        "qb_progression_candidate_classifications.json": audit["sequences"],
        "qb_progression_delta_analysis.json": [
            {
                "lower_qb_id": item["lower"]["qb_id"],
                "upper_qb_id": item["upper"]["qb_id"],
                "classification": item["classification"],
                "delta": item["delta"],
            }
            for item in audit["sequences"]
        ],
        "qb_confirmed_progression_constraints.json": audit["confirmed_constraints"],
        "qb_0074_provenance_audit.json": audit["qb_0074_provenance"],
        "qb_systematic_error_provenance_audit.json": audit["systematic_error_card_audits"],
        "qb_source_inventory.json": audit["source_inventory"],
        "qb_evidence_acquisition_backlog.json": audit["evidence_acquisition_backlog"],
        "qb_provenance_audit_summary.json": {
            key: value
            for key, value in audit.items()
            if key
            not in {
                "sequences",
                "candidate_confirmed_constraints",
                "recovered_confirmed_constraints",
                "confirmed_constraints",
                "qb_0074_provenance",
                "systematic_error_card_audits",
                "source_inventory",
                "evidence_acquisition_backlog",
            }
        },
    }
    for name, payload in payloads.items():
        (root / name).write_text(
            json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
