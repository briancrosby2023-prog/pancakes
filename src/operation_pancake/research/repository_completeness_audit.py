"""Repository-wide data completeness and recovery-priority audit."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from operation_pancake.evidence.catalog import build_evidence_index
from operation_pancake.evidence.ingestion import IngestionState

INVENTORY = Path("data/research/progression_audit/progression_inventory.json")
STATE = Path("data/evidence/ingestion_state.json")
OUTPUT = Path("data/research/repository_completeness_audit")


def _level(value: int, ready: int, partial: int = 1) -> str:
    return "READY" if value >= ready else "PARTIAL" if value >= partial else "BLOCKED"


def _historical_progressions(state: IngestionState) -> list[dict[str, Any]]:
    return [
        record
        for record in state.records.values()
        if record.get("record_type") == "progression_observation"
    ]


def _position(record: dict[str, Any]) -> str:
    values = record.get("values", record)
    return values.get("position") or values.get("position_group") or "UNKNOWN"


def build_repository_audit(root: Path) -> dict[str, Any]:
    """Build deterministic audit artifacts from repository evidence only."""
    index = build_evidence_index(root)
    state = IngestionState.load(root / STATE)
    inventory = json.loads((root / INVENTORY).read_text(encoding="utf-8"))
    cards = inventory["canonical_cards"]
    historical_progressions = _historical_progressions(state)
    historical_centers = [
        values
        for (kind, _), values in index.records.items()
        if kind == "historical_center_observation"
    ]
    positions = sorted(
        {card["position"] for card in cards}
        | {_position(record) for record in historical_progressions}
        | {"C"}
    )
    confirmed = [
        item
        for item in inventory["progression_candidates"]
        if item["classification"] == "CONFIRMED_PROGRESSION"
    ]
    links_by_card: dict[str, set[str]] = defaultdict(set)
    for link in index.links.values():
        if link.target_type == "player_card":
            links_by_card[link.target_id].add(link.source_id)

    position_inventory: list[dict[str, Any]] = []
    progression_matrix: list[dict[str, Any]] = []
    readiness: list[dict[str, Any]] = []
    completeness: dict[str, list[dict[str, Any]]] = {
        "known_players_without_complete_vectors": [],
        "known_card_states_without_vectors": [],
        "cards_missing_archetype": [],
        "cards_missing_program": [],
        "cards_missing_source_locator": [],
        "historical_records_without_canonical_links": [],
        "canonical_cards_with_one_source": [],
        "likely_duplicate_identities": [],
        "same_player_multiple_programs": [],
    }

    identity_groups: dict[tuple[str, str, int], list[dict[str, Any]]] = defaultdict(list)
    player_programs: dict[tuple[str, str], set[str]] = defaultdict(set)
    for card in cards:
        identity_groups[(card["player"], card["position"], card["overall"])].append(card)
        player_programs[(card["player"], card["position"])].add(card.get("program") or "")
        if not card.get("archetype"):
            completeness["cards_missing_archetype"].append({"card_id": card["card_id"]})
        if not card.get("program"):
            completeness["cards_missing_program"].append({"card_id": card["card_id"]})
        if not card.get("source_locator"):
            completeness["cards_missing_source_locator"].append({"card_id": card["card_id"]})
        if len(links_by_card[card["card_id"]]) == 1:
            completeness["canonical_cards_with_one_source"].append({"card_id": card["card_id"]})
    completeness["likely_duplicate_identities"] = [
        {
            "player": key[0],
            "position": key[1],
            "overall": key[2],
            "card_ids": sorted(card["card_id"] for card in group),
        }
        for key, group in sorted(identity_groups.items())
        if len(group) > 1
    ]
    completeness["same_player_multiple_programs"] = [
        {"player": key[0], "position": key[1], "programs": sorted(programs)}
        for key, programs in sorted(player_programs.items())
        if len(programs) > 1
    ]

    for record in historical_progressions:
        values = record["values"]
        if values.get("missing_vectors"):
            item = {
                "record_id": record["record_id"],
                "player": values.get("player"),
                "position": _position(record),
                "missing_states": values["missing_vectors"],
            }
            completeness["known_card_states_without_vectors"].append(item)
            if values.get("player"):
                completeness["known_players_without_complete_vectors"].append(item)
        if not values.get("canonical_links"):
            completeness["historical_records_without_canonical_links"].append(
                {"record_id": record["record_id"], "position": _position(record)}
            )

    for position in positions:
        position_cards = [card for card in cards if card["position"] == position]
        historical = [r for r in historical_progressions if _position(r) == position]
        if position == "C":
            historical_count = len(historical_centers) + sum(
                len(r["values"].get("known_states", [])) for r in historical
            )
        else:
            historical_count = sum(len(r["values"].get("known_states", [])) for r in historical)
        ovrs = sorted({card["overall"] for card in position_cards})
        archetypes = sorted({card["archetype"] for card in position_cards if card.get("archetype")})
        programs = sorted({card["program"] for card in position_cards if card.get("program")})
        source_ids = sorted({card["source_id"] for card in position_cards if card.get("source_id")})
        confirmed_position = [item for item in confirmed if item["position"] == position]
        candidate_position = [
            item for item in inventory["progression_candidates"] if item["position"] == position
        ]
        historical_states = sum(len(r["values"].get("known_states", [])) for r in historical)
        missing_vectors = sum(len(r["values"].get("missing_vectors", [])) for r in historical)
        complete_vectors = len(position_cards)
        multi_source = sum(len(links_by_card[card["card_id"]]) > 1 for card in position_cards)
        position_inventory.append(
            {
                "position": position,
                "canonical_cards": len(position_cards),
                "historical_cards_or_states": historical_count,
                "ovr_range": [min(ovrs), max(ovrs)] if ovrs else None,
                "archetypes": archetypes,
                "programs": programs,
                "complete_rating_vectors": complete_vectors,
                "incomplete_rating_vectors": missing_vectors + (12 if position == "C" else 0),
                "progression_observations": len(candidate_position) + len(historical),
                "independent_validation_observations": multi_source,
                "source_count": len(source_ids),
                "multi_source_records": multi_source,
            }
        )
        progression_matrix.append(
            {
                "position": position,
                "known_chains": len(candidate_position) + len(historical),
                "validated_chains": len(confirmed_position),
                "historical_only_chains": len(historical),
                "known_states": len(position_cards) + historical_states,
                "complete_vectors": complete_vectors,
                "missing_vectors": missing_vectors,
                "controlled_transitions": len(confirmed_position),
                "card_types": programs,
            }
        )
        dimensions = {
            "STATIC_POPULATION": _level(len(position_cards), 20, 5),
            "OVR_COVERAGE": _level(len(ovrs), 6, 2),
            "ARCHETYPE_COVERAGE": _level(len(archetypes), 3),
            "PROGRESSION_EVIDENCE": _level(len(confirmed_position), 2)
            if not historical
            else ("PARTIAL" if not confirmed_position else "READY"),
            "SOURCE_PROVENANCE": "READY"
            if position_cards and len(source_ids)
            else "PARTIAL"
            if historical
            else "BLOCKED",
            "INDEPENDENT_VALIDATION": _level(multi_source, 2),
            "FORMULA_RESEARCH": "READY"
            if position == "QB"
            else "PARTIAL"
            if position in {"TE", "C"}
            else "BLOCKED",
            "PC_EVALUATOR_READINESS": "PARTIAL" if position in {"QB", "TE", "C"} else "BLOCKED",
        }
        blocked = sum(value == "BLOCKED" for value in dimensions.values())
        if not position_cards:
            priority = "CRITICAL"
        elif len(position_cards) < 5 or blocked >= 4:
            priority = "HIGH"
        elif blocked >= 2:
            priority = "MEDIUM"
        else:
            priority = "LOW"
        readiness.append({"position": position, **dimensions, "recovery_priority": priority})

    source_ranking = _source_value_ranking(index, state)
    screenshot_ranking = _screenshot_ranking(historical_progressions)
    formula_gaps = _formula_gaps(position_inventory, progression_matrix)
    pc_gaps = _pc_gap_map(position_inventory, state)
    external_schema = _external_schema()
    recovery_queue = _recovery_queue(index, state, readiness, source_ranking)
    top_ten = _top_ten(source_ranking, screenshot_ranking)
    return {
        "position_inventory": position_inventory,
        "readiness": readiness,
        "player_card_completeness": completeness,
        "progression_matrix": progression_matrix,
        "source_value_ranking": source_ranking,
        "screenshot_recovery_ranking": screenshot_ranking,
        "formula_gap_map": formula_gaps,
        "pc_application_gap_map": pc_gaps,
        "external_card_schema": external_schema,
        "recovery_work_queue": recovery_queue,
        "chatgpt_top_10_recovery_targets": top_ten,
        "audit_summary": {
            "positions": len(positions),
            "canonical_cards": len(cards),
            "historical_progression_records": len(historical_progressions),
            "queue_before": 20,
            "queue_after_deduplication": len(recovery_queue),
            "queue_duplicates_removed": 20
            + len(readiness)
            + len(source_ranking)
            - len(recovery_queue),
            "critical_queue_items": sum(item["priority"] == "CRITICAL" for item in recovery_queue),
            "high_queue_items": sum(item["priority"] == "HIGH" for item in recovery_queue),
        },
    }


def _source_value_ranking(index, state) -> list[dict[str, Any]]:
    unresolved = Counter(
        item.get("source_id")
        for item in state.reconciliation.values()
        if item["status"] != "RESOLVED"
    )
    unresolved.update(
        item.source_id
        for item in index.queue.values()
        if item.status != "RESOLVED" and item.item_id not in state.reconciliation
    )
    rankings = []
    for source_id, source in index.sources.items():
        effective = state.sources.get(source_id, {})
        status = effective.get("coverage", {}).get("status", source.extraction_status)
        if status not in {"PARTIAL", "UNPROCESSED", "NEEDS_REVIEW"}:
            continue
        progression = sum(
            item.get("source_id") == source_id
            and item.get("affected_type") in {"progression_recovery", "conflict_recovery"}
            for item in state.reconciliation.values()
        )
        position_count = len(source.positions) or (1 if progression else 0)
        file_library = source.origin == "CHATGPT_FILE_LIBRARY" or source_id in {
            "SRC-IMG-ARCH",
            "SRC-HIST-001",
        }
        score = unresolved[source_id] * 10 + progression * 8 + position_count * 3 + file_library * 5
        rankings.append(
            {
                "source_id": source_id,
                "filename": source.original_filename,
                "status": status,
                "unresolved_records": unresolved[source_id],
                "progression_relevance": progression,
                "positions_affected": position_count,
                "known_present": bool(file_library),
                "recovery_value_score": score,
                "why": (
                    "Rank reflects unresolved links, progression leverage, coverage, "
                    "and known presence."
                ),
            }
        )
    return sorted(rankings, key=lambda item: (-item["recovery_value_score"], item["source_id"]))


def _screenshot_ranking(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    maturity = {
        "WR": 3,
        "MLB": 4,
        "HB": 4,
        "CB": 4,
        "SS": 4,
        "QB": 1,
        "TE": 2,
        "FB": 5,
        "FS": 4,
        "GUARD": 5,
    }
    ranked = []
    for record in records:
        values = record["values"]
        states = values.get("known_states", [])
        transitions = sum(b - a == 1 for a, b in zip(states, states[1:], strict=False))
        position = _position(record)
        score = len(states) * 4 + transitions * 8 + maturity.get(position, 5) * 2
        ranked.append(
            {
                "record_id": record["record_id"],
                "target": values.get("player") or f"Unidentified {position}",
                "position": position,
                "states": states,
                "one_ovr_transitions": transitions,
                "information_value_score": score,
                "why": (
                    "More states and controlled one-OVR transitions provide stronger "
                    "isolation evidence."
                ),
            }
        )
    return sorted(ranked, key=lambda item: (-item["information_value_score"], item["record_id"]))


def _formula_gaps(inventory, matrix) -> list[dict[str, Any]]:
    matrix_by_position = {item["position"]: item for item in matrix}
    gaps = []
    for item in inventory:
        position = item["position"]
        canonical = item["canonical_cards"]
        if position == "C":
            need = (
                "Recover 5 complete regular CUT Center profiles spanning 80-85 and at "
                "least two archetypes."
            )
        elif canonical >= 20:
            need = (
                "Recover one complete confirmed progression chain and independent sources "
                "for boundary cards."
            )
        elif canonical:
            need = (
                f"Recover {max(5 - canonical, 1)} additional complete static profiles "
                "plus one confirmed chain."
            )
        else:
            need = (
                "Recover 5 complete cards across at least three OVRs and two archetypes, "
                "plus one progression."
            )
        gaps.append(
            {
                "position": position,
                "smallest_material_evidence_set": need,
                "current_complete_vectors": canonical,
                "validated_chains": matrix_by_position[position]["validated_chains"],
                "evaluation_ready_standard": "approximately 95% with independent validation",
                "operationally_solved_standard": ">=98% with no systematic failure pattern",
            }
        )
    return gaps


def _pc_gap_map(inventory, state) -> list[dict[str, str]]:
    canonical = sum(item["canonical_cards"] for item in inventory)
    return [
        {
            "capability": "card_lookup",
            "status": "READY",
            "dependency": f"{canonical} canonical cards indexed",
        },
        {
            "capability": "player_comparison",
            "status": "READY",
            "dependency": "complete canonical vectors",
        },
        {
            "capability": "positional_evaluation",
            "status": "PARTIAL",
            "dependency": "validated evaluators beyond research-only Center",
        },
        {
            "capability": "hidden_effective_ovr",
            "status": "BLOCKED",
            "dependency": "operationally solved positional formulas",
        },
        {
            "capability": "progression_analysis",
            "status": "PARTIAL",
            "dependency": "missing historical progression vectors",
        },
        {
            "capability": "source_provenance",
            "status": "READY",
            "dependency": "evidence index and field provenance",
        },
        {
            "capability": "archetype_comparison",
            "status": "PARTIAL",
            "dependency": "positions lacking archetype populations",
        },
        {
            "capability": "market_evaluation",
            "status": "BLOCKED",
            "dependency": "timestamped market observations",
        },
        {
            "capability": "roster_construction",
            "status": "BLOCKED",
            "dependency": "broad positional and market coverage",
        },
    ]


def _external_schema() -> dict[str, Any]:
    return {
        "required": [
            "external_id",
            "player",
            "position",
            "overall",
            "source_reference",
            "retrieved_at",
        ],
        "recommended": [
            "archetype",
            "program",
            "card_type",
            "displayed_ratings",
            "release_date",
            "market",
        ],
        "market_fields": ["price", "currency", "platform", "observed_at", "listing_type"],
        "staging_mapping": {
            "identity": ["external_id", "player", "position", "overall", "program", "card_type"],
            "attributes": "displayed_ratings",
            "provenance": ["source_reference", "retrieved_at"],
            "default_disposition": "REFERENCE_DATA",
            "automatic_canonical_promotion": False,
        },
    }


def _recovery_queue(index, state, readiness, source_ranking) -> list[dict[str, Any]]:
    items: dict[str, dict[str, Any]] = {}
    for item_id, item in state.reconciliation.items():
        if item["status"] == "RESOLVED":
            continue
        items[item_id] = {
            "item_id": item_id,
            "priority": item["priority"],
            "target": item.get("affected_id"),
            "why_it_matters": item["notes"],
            "source_or_record": item.get("source_id"),
            "expected_benefit": "Resolve indexed evidence gap",
            "blocked_by": "Source extraction/validation",
            "next_action": item["notes"],
        }
    for item in readiness:
        if item["recovery_priority"] in {"CRITICAL", "HIGH"}:
            key = f"GAP-POSITION-{item['position']}"
            items.setdefault(
                key,
                {
                    "item_id": key,
                    "priority": item["recovery_priority"],
                    "target": item["position"],
                    "why_it_matters": "Position lacks sufficient static/progression evidence.",
                    "source_or_record": None,
                    "expected_benefit": "Improve formula and PC readiness",
                    "blocked_by": "Complete sourced card vectors",
                    "next_action": "Acquire staged complete profiles.",
                },
            )
    for source in source_ranking[:5]:
        key = f"GAP-SOURCE-{source['source_id']}"
        items.setdefault(
            key,
            {
                "item_id": key,
                "priority": "HIGH" if source["recovery_value_score"] >= 50 else "MEDIUM",
                "target": source["filename"],
                "why_it_matters": source["why"],
                "source_or_record": source["source_id"],
                "expected_benefit": "Resolve multiple evidence gaps",
                "blocked_by": "File Library recovery/extraction",
                "next_action": "Recover and submit a bulk manifest.",
            },
        )
    order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    return sorted(items.values(), key=lambda item: (order[item["priority"]], item["item_id"]))


def _top_ten(sources, screenshots) -> list[dict[str, Any]]:
    preferred = [
        "RECOVERY-PROG-WR-76-83",
        "HIST-PROG-JUNIOR-SEAU",
        "HIST-PROG-MICHAEL-CRABTREE",
        "HIST-PROG-JOEY-HARRINGTON-OLD",
        "HIST-PROG-BO-JACKSON",
        "HIST-PROG-CHRIS-PEAL",
        "HIST-PROG-PEYTON-BOWEN",
        "RECOVERY-PROG-TE-80-85",
    ]
    by_id = {item["record_id"]: item for item in screenshots}
    queue_ids = {
        "RECOVERY-PROG-WR-76-83": "REC-PROG-WR-76-83",
        "HIST-PROG-JUNIOR-SEAU": "REC-PROG-SEAU",
        "HIST-PROG-MICHAEL-CRABTREE": "REC-PROG-CRABTREE",
        "HIST-PROG-JOEY-HARRINGTON-OLD": "REC-PROG-HARRINGTON-CROSSCHECK",
        "HIST-PROG-BO-JACKSON": "REC-PROG-BO-JACKSON",
        "HIST-PROG-CHRIS-PEAL": "REC-PROG-CHRIS-PEAL",
        "HIST-PROG-PEYTON-BOWEN": "REC-PROG-PEYTON-BOWEN",
        "RECOVERY-PROG-TE-80-85": "REC-PROG-TE-80-85",
    }
    result = []
    for record_id in preferred:
        item = by_id[record_id]
        result.append(
            {
                "rank": len(result) + 1,
                "search_terms": f"{item['target']} {item['position']} progression {item['states']}",
                "evidence_sought": "Original screenshots and complete displayed rating panels",
                "why_it_matters": item["why"],
                "resolves": [record_id, queue_ids[record_id]],
                "partial_evidence_useful": True,
            }
        )
    result.extend(
        [
            {
                "rank": 9,
                "search_terms": "raw str centers2(2).pdf pages 4-14 Center CUT",
                "evidence_sought": "Validated Center card rating panels",
                "why_it_matters": "Fills the smallest Center static-population gap.",
                "resolves": ["SRC-C-RAW-003", "Q-C-004-014"],
                "partial_evidence_useful": True,
            },
            {
                "rank": 10,
                "search_terms": "history(4).pdf progression Saturday Reset formula research",
                "evidence_sought": "Page-level progression and experiment evidence",
                "why_it_matters": "May resolve multiple positions and historical conclusions.",
                "resolves": ["SRC-HIST-001"],
                "partial_evidence_useful": True,
            },
        ]
    )
    return result


def write_repository_audit(root: Path) -> dict[str, Any]:
    """Write deterministic machine-readable audit artifacts."""
    audit = build_repository_audit(root)
    output = root / OUTPUT
    output.mkdir(parents=True, exist_ok=True)
    for key, value in audit.items():
        (output / f"{key}.json").write_text(
            json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    return audit
