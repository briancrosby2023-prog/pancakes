"""Database-wide conservative progression mining and OVR constraint audit."""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from statistics import fmean
from typing import Any

from operation_pancake.importers.workbook_importer import WorkbookImporter

CONFIRMED = "CONFIRMED_PROGRESSION"
PROBABLE = "PROBABLE_PROGRESSION"
UNRESOLVED = "UNRESOLVED"
CONTRADICTED = "CONTRADICTED"

SHEETS = {
    "TE": ("TE_Cards", "Card_ID"),
    "C": ("Center_Cards", "Card_ID"),
    "QB": ("QB_Cards", "QB_ID"),
}
NON_ATTRIBUTES = {
    "Card_ID",
    "QB_ID",
    "Player",
    "OVR",
    "Program",
    "Archetype",
    "Jersey",
    "Source_ID",
    "Source_Page",
    "Source_Locator",
    "Validation_Status",
    "Notes",
    "Population_Scope",
    "Model_Role",
    "Unique_Profile_Key",
    "Duplicate_Note",
    "Frozen_Score_Check",
    "Frozen_Score_Formula",
    "Formula_Delta",
    "FB_OOP",
    "WR_OOP",
}
HARRINGTON_PAIRS = {
    ("QB-0074", "QB-0038"): "QB-JH-79-81",
    ("QB-0038", "QB-0013"): "QB-JH-81-84",
    ("QB-0013", "QB-0003"): "QB-JH-84-86",
}
DELTA_PATTERN = re.compile(r"(?:([A-Z]+)\s*([+-]\d+)|([+-]\d+)\s*([A-Z]+))")


def _rows(workbook: str | Path, sheet: str) -> list[dict[str, Any]]:
    return [record.values for record in WorkbookImporter(workbook).records(sheet)]


def _attribute_fields(row: dict[str, Any]) -> tuple[str, ...]:
    return tuple(
        key for key in row if key not in NON_ATTRIBUTES and isinstance(row[key], (int, float))
    )


def _canonical_cards(workbook: str | Path) -> list[dict[str, Any]]:
    cards = []
    for position, (sheet, id_field) in SHEETS.items():
        for row in _rows(workbook, sheet):
            locator = row.get("Source_Locator", row.get("Source_Page"))
            cards.append(
                {
                    "card_id": row[id_field],
                    "player": row["Player"],
                    "position": position,
                    "overall": int(row["OVR"]),
                    "program": row["Program"],
                    "archetype": row["Archetype"],
                    "attributes": {field: int(row[field]) for field in _attribute_fields(row)},
                    "source_id": row.get("Source_ID"),
                    "source_locator": locator,
                    "validation_status": row.get("Validation_Status"),
                    "notes": row.get("Notes"),
                    "workbook_sheet": sheet,
                }
            )
    return cards


def _parse_deltas(text: str) -> dict[str, int]:
    deltas: dict[str, int] = {}
    for left_field, left_value, right_value, right_field in DELTA_PATTERN.findall(text):
        field = left_field or right_field
        value = left_value or right_value
        deltas[field] = int(value)
    if not deltas:
        raise ValueError(f"No exact attribute deltas found in {text!r}.")
    return deltas


def _candidate_transition(lower: dict[str, Any], upper: dict[str, Any]) -> dict[str, Any]:
    common = tuple(field for field in lower["attributes"] if field in upper["attributes"])
    deltas = {field: upper["attributes"][field] - lower["attributes"][field] for field in common}
    pair = (lower["card_id"], upper["card_id"])
    if pair in HARRINGTON_PAIRS:
        classification = CONFIRMED
        reason = "Explicit same-program progression in Progression_Logs and QB_Progression."
        references = [
            f"Progression_Logs!{HARRINGTON_PAIRS[pair]}",
            "QB_Progression",
            "Research_Findings!QB-F-009",
        ]
    elif lower["program"] != upper["program"]:
        classification = CONTRADICTED
        reason = "Different card programs; no explicit progression record links them."
        references = [lower["workbook_sheet"], upper["workbook_sheet"]]
    else:
        classification = UNRESOLVED
        reason = (
            "Same player/program observations exist, but repository evidence does not "
            "explicitly establish progression."
        )
        references = [lower["workbook_sheet"], upper["workbook_sheet"]]
    return {
        "lower_card_id": lower["card_id"],
        "upper_card_id": upper["card_id"],
        "player": lower["player"],
        "position": lower["position"],
        "archetype": lower["archetype"] if lower["archetype"] == upper["archetype"] else None,
        "lower_program": lower["program"],
        "upper_program": upper["program"],
        "start_ovr": lower["overall"],
        "end_ovr": upper["overall"],
        "classification": classification,
        "classification_reason": reason,
        "provenance_references": references,
        "attribute_deltas": deltas,
    }


def _canonical_candidates(cards: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for card in cards:
        groups[(card["position"], card["player"].casefold())].append(card)
    candidates = []
    for group in groups.values():
        if len(group) < 2:
            continue
        group.sort(key=lambda card: (card["overall"], card["card_id"]))
        for lower, upper in zip(group[:-1], group[1:], strict=True):
            candidates.append(_candidate_transition(lower, upper))
    return sorted(
        candidates, key=lambda item: (item["position"], item["player"], item["lower_card_id"])
    )


def _transition_summary(
    transition_id: str,
    player: str,
    position: str,
    archetype: str | None,
    program: str | None,
    start: int,
    end: int,
    deltas: dict[str, int],
    source_id: str,
    source_locator: Any,
    evidence: str,
) -> dict[str, Any]:
    changed = {field: value for field, value in deltas.items() if value != 0}
    delta_ovr = end - start
    sparse = len(changed) <= 2
    score = 100 - 8 * len(changed) + (30 if delta_ovr == 1 else 0) + (20 if sparse else 0)
    direct_qb = position == "QB"
    return {
        "transition_id": transition_id,
        "player": player,
        "position": position,
        "archetype": archetype,
        "program": program,
        "source_id": source_id,
        "source_locator": source_locator,
        "start_ovr": start,
        "end_ovr": end,
        "delta_ovr": delta_ovr,
        "attribute_deltas": deltas,
        "changed_attributes": sorted(changed),
        "changed_attribute_count": len(changed),
        "total_positive_rating_points": sum(max(0, value) for value in deltas.values()),
        "total_negative_rating_points": sum(min(0, value) for value in deltas.values()),
        "unchanged_attributes": sorted(field for field, value in deltas.items() if value == 0),
        "crosses_multiple_ovr_levels": delta_ovr > 1,
        "classification": CONFIRMED,
        "evidence": evidence,
        "information_value_score": score,
        "information_value_category": "HIGH"
        if score >= 120
        else "MEDIUM"
        if score >= 80
        else "LOW",
        "applicable_research_questions": [
            "score_to_ovr_boundary",
            "attribute_sensitivity" if sparse else "aggregate_upgrade_response",
        ],
        "can_constrain_qb_directly": direct_qb,
        "general_ea_architecture_evidence_only": not direct_qb,
    }


def _confirmed_transitions(
    workbook: str | Path, cards: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    by_id = {card["card_id"]: card for card in cards}
    logs = _rows(workbook, "Progression_Logs")
    transitions = []
    for row in logs:
        record_id = row["Record_ID"]
        if record_id.startswith("SAT-"):
            deltas = _parse_deltas(row["Upgrade_Deltas"])
            transitions.append(
                _transition_summary(
                    record_id,
                    row["Entity"],
                    "UNSPECIFIED",
                    None,
                    None,
                    int(row["Start_OVR"]),
                    int(row["End_OVR"]),
                    deltas,
                    row["Source_ID"],
                    row["Source_Page"],
                    "Progression_Logs explicit controlled reset",
                )
            )
        elif record_id in HARRINGTON_PAIRS.values():
            pair = next(pair for pair, value in HARRINGTON_PAIRS.items() if value == record_id)
            lower, upper = by_id[pair[0]], by_id[pair[1]]
            deltas = {
                field: upper["attributes"][field] - lower["attributes"][field]
                for field in lower["attributes"]
            }
            transitions.append(
                _transition_summary(
                    record_id,
                    lower["player"],
                    "QB",
                    lower["archetype"],
                    lower["program"],
                    lower["overall"],
                    upper["overall"],
                    deltas,
                    row["Source_ID"],
                    row["Source_Page"],
                    "Progression_Logs and QB_Progression explicit same-program progression",
                )
            )
    return sorted(transitions, key=lambda item: item["transition_id"])


def _confirmed_chains(transitions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in transitions:
        chain = (
            "QB-JH"
            if item["transition_id"].startswith("QB-JH")
            else item["transition_id"].removesuffix("B")
        )
        groups[chain].append(item)
    return [
        {
            "chain_id": chain_id,
            "player_or_entity": rows[0]["player"],
            "position": rows[0]["position"],
            "transition_ids": [
                row["transition_id"] for row in sorted(rows, key=lambda x: x["start_ovr"])
            ],
            "observed_ovr_states": sorted(
                {value for row in rows for value in (row["start_ovr"], row["end_ovr"])}
            ),
            "state_vectors_complete": rows[0]["position"] == "QB",
        }
        for chain_id, rows in sorted(groups.items())
    ]


def build_progression_audit(workbook: str | Path, research_files: list[str]) -> dict[str, Any]:
    """Build a complete conservative inventory from repository-accessible evidence."""
    cards = _canonical_cards(workbook)
    candidates = _canonical_candidates(cards)
    transitions = _confirmed_transitions(workbook, cards)
    chains = _confirmed_chains(transitions)
    by_position = Counter(card["position"] for card in cards)
    unique_players = {
        position: len({card["player"] for card in cards if card["position"] == position})
        for position in by_position
    }
    repeated = Counter((card["position"], card["player"]) for card in cards)
    same_program_groups = Counter(
        (card["position"], card["player"], card["program"]) for card in cards
    )
    class_counts = Counter(item["classification"] for item in candidates)
    ranking = sorted(
        transitions, key=lambda item: (-item["information_value_score"], item["transition_id"])
    )
    reset_rows = [item for item in transitions if item["position"] == "UNSPECIFIED"]
    qb_rows = [item for item in transitions if item["position"] == "QB"]
    boundary_counts = Counter(f"{item['start_ovr']}→{item['end_ovr']}" for item in transitions)
    changed_counts = Counter(field for item in transitions for field in item["changed_attributes"])
    return {
        "schema_version": 1,
        "phase": "Database-Wide Progression Mining & OVR Constraint Audit",
        "formula_fitting_performed": False,
        "inventory": {
            "canonical_observation_count": len(cards),
            "positions": sorted(by_position),
            "observations_by_position": dict(sorted(by_position.items())),
            "unique_players_by_position": dict(sorted(unique_players.items())),
            "program_count": len({card["program"] for card in cards}),
            "programs": sorted({card["program"] for card in cards}),
            "repeated_player_groups": sum(value > 1 for value in repeated.values()),
            "repeated_player_observations": sum(value for value in repeated.values() if value > 1),
            "repeated_player_same_program_groups": sum(
                value > 1 for value in same_program_groups.values()
            ),
            "explicit_progression_log_count": len(_rows(workbook, "Progression_Logs")),
            "confirmed_transition_count": len(transitions),
            "canonical_candidate_count": len(candidates),
            "candidate_classification_counts": dict(sorted(class_counts.items())),
            "progression_research_files": sorted(
                path
                for path in research_files
                if "progression" in path.lower()
                or "harrington" in path.lower()
                or "provenance" in path.lower()
            ),
        },
        "canonical_cards": cards,
        "progression_candidates": candidates,
        "confirmed_chains": chains,
        "confirmed_transitions": transitions,
        "high_information_ranking": ranking,
        "pattern_analysis": {
            "confirmed_by_position": dict(
                sorted(Counter(item["position"] for item in transitions).items())
            ),
            "boundary_counts": dict(sorted(boundary_counts.items())),
            "changed_attribute_frequency": dict(sorted(changed_counts.items())),
            "mean_positive_points_by_position": {
                position: round(
                    fmean(
                        item["total_positive_rating_points"]
                        for item in transitions
                        if item["position"] == position
                    ),
                    6,
                )
                for position in sorted({item["position"] for item in transitions})
            },
            "zero_ovr_movement_count": sum(item["delta_ovr"] == 0 for item in transitions),
            "repeated_templates": [
                {"attribute_deltas": dict(key), "count": value}
                for key, value in sorted(
                    Counter(
                        tuple(sorted(item["attribute_deltas"].items())) for item in transitions
                    ).items(),
                    key=lambda pair: str(pair[0]),
                )
                if value > 1
            ],
        },
        "cross_position_evidence": {
            "H1": (
                "SUPPORTED ONLY AS PLAUSIBLE: resets show sparse position-dependent ratings "
                "can cross displayed 80→81→82 boundaries, but position is not recorded."
            ),
            "H2": (
                "UNRESOLVED: no confirmed full-vector non-QB chain permits conversion comparison."
            ),
            "H3": (
                "PLAUSIBLE: variable reset point totals produce identical +1 OVR outcomes; "
                "thresholds and starting band position confound weight inference."
            ),
            "H4": (
                "SUPPORTED DESCRIPTIVELY: raw points vary widely for the same +1 OVR result, "
                "consistent with weighted increments or unknown starting locations."
            ),
            "H5": (
                "NOT TESTABLE: reset archetypes are absent and only one confirmed QB "
                "archetype chain exists."
            ),
            "transferable": [
                "Displayed OVR boundaries permit diverse upgrade bundles.",
                "Raw point totals alone do not determine OVR movement.",
            ],
            "position_specific": [
                "Attribute weights",
                "Archetype effects",
                "Exact score-to-OVR conversion",
            ],
        },
        "constraint_matrix": ranking,
        "qb_implications": {
            "additional_confirmed_qb_chains_beyond_harrington": 0,
            "direct_qb_transition_count": len(qb_rows),
            "general_architecture_transition_count": len(reset_rows),
            "harrington_pattern_elsewhere": (
                "No identical +2/+3/+2 chain exists; resets only cover +1 transitions."
            ),
            "architecture_a": (
                "Reset evidence cannot directly constrain QB weights because position and "
                "full state vectors are absent."
            ),
            "awr_tac_tgh": (
                "AWR varies in two reset records, but unspecified position prevents direct "
                "QB constraint; TAC/TGH lack controlled non-Harrington variation."
            ),
            "qb_0074": (
                "Unchanged: confirmed Harrington baseline; database-wide evidence adds no "
                "factual correction or direct calibration constraint."
            ),
        },
        "coverage_gaps": {
            "strong": [
                "UNSPECIFIED controlled resets at 80→81 and 81→82",
                "QB Harrington states spanning 79→81→84→86",
            ],
            "weak_or_none": [
                "TE: no source-confirmed progression",
                "C: no repeated-player observations",
                "All other positions absent",
            ],
            "well_constrained_boundaries": dict(sorted(boundary_counts.items())),
            "poorly_constrained": [
                "Same-OVR controlled upgrades",
                "One-step QB boundaries",
                "Non-QB boundaries above 82",
            ],
            "controlled_attribute_frequency": dict(sorted(changed_counts.items())),
            "inseparable": [
                "Harrington's 12 changing QB attributes",
                "Position and archetype effects in Saturday Reset records",
            ],
        },
        "canonical_observations_modified": False,
        "speculative_progressions_promoted": False,
    }


def write_progression_artifacts(directory: str | Path, audit: dict[str, Any]) -> None:
    """Write deterministic database-wide progression artifacts."""
    root = Path(directory)
    root.mkdir(parents=True, exist_ok=True)
    payloads = {
        "progression_inventory.json": {
            "inventory": audit["inventory"],
            "canonical_cards": audit["canonical_cards"],
            "progression_candidates": audit["progression_candidates"],
        },
        "confirmed_progression_chains.json": audit["confirmed_chains"],
        "confirmed_transition_deltas.json": audit["confirmed_transitions"],
        "progression_pattern_analysis.json": audit["pattern_analysis"],
        "high_information_transition_ranking.json": audit["high_information_ranking"],
        "cross_position_structural_evidence.json": audit["cross_position_evidence"],
        "progression_constraint_matrix.json": audit["constraint_matrix"],
        "qb_progression_implications.json": audit["qb_implications"],
        "progression_coverage_gaps.json": audit["coverage_gaps"],
        "progression_audit_summary.json": {
            key: value
            for key, value in audit.items()
            if key
            not in {
                "canonical_cards",
                "progression_candidates",
                "confirmed_chains",
                "confirmed_transitions",
                "high_information_ranking",
                "constraint_matrix",
            }
        },
    }
    for name, payload in payloads.items():
        (root / name).write_text(
            json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
