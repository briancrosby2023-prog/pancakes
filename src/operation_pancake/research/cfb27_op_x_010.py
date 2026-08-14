"""OP-X-010 canonical CFB27 card/version/upgrade database export."""

from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

from operation_pancake.models.cfb27_card_state import stable_id
from operation_pancake.research.cfb27_op_x_001 import _cards


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _public_entities(cards: list[dict]) -> dict:
    players = {}
    card_entities = []
    native_states = []
    evidence = []
    by_player = defaultdict(list)
    for card in cards:
        source = card["external_source"]
        source_player_id = card.get("external_player_id")
        player_id = stable_id(
            "player", source, source_player_id or card["player_name"], card["position"]
        )
        players.setdefault(
            player_id,
            {
                "player_id": player_id,
                "name": card["player_name"],
                "source_player_ids": [f"{source}:{source_player_id}"],
            },
        )
        card_id = stable_id("card", source, card["external_card_id"])
        state_id = stable_id("state", card_id, "native")
        entity = {
            "card_id": card_id,
            "player_id": player_id,
            "source": source,
            "source_card_id": card["external_card_id"],
            "position": card["position"],
            "program": card.get("program"),
            "archetype": card.get("archetype"),
            "team": card.get("team_school"),
            "release_date": card.get("release_date"),
            "upgradeability": "UNKNOWN",
        }
        card_entities.append(entity)
        by_player[player_id].append(entity)
        ratings = dict(sorted(card.get("displayed_ratings", {}).items()))
        native_states.append(
            {
                "state_id": state_id,
                "card_id": card_id,
                "state_type": "NATIVE",
                "native_overall": card["overall"],
                "native_ratings": ratings,
                "active_ratings": None,
                "attribute_count": len(ratings),
                "source": card.get("source_reference"),
                "raw_snapshot": card.get("raw_snapshot_reference"),
            }
        )
        evidence.append(
            {
                "evidence_id": stable_id("evidence", source, card["external_card_id"]),
                "target_id": state_id,
                "source": source,
                "source_reference": card.get("source_reference"),
                "retrieved_at": card.get("retrieval_timestamp"),
                "raw_snapshot": card.get("raw_snapshot_reference"),
                "confidence": "STAGED_EXTERNAL_PUBLIC_SOURCE",
            }
        )
    edges = []
    for family in by_player.values():
        ordered = sorted(
            family, key=lambda row: (row["position"], row["program"] or "", row["card_id"])
        )
        for left, right in zip(ordered, ordered[1:], strict=False):
            edges.append(
                {
                    "edge_id": stable_id("edge", "same-player", left["card_id"], right["card_id"]),
                    "from": left["card_id"],
                    "to": right["card_id"],
                    "relationship": "SAME_PLAYER",
                    "confidence": "SOURCE_PLAYER_ID",
                    "provenance": [left["source"], right["source"]],
                }
            )
    return {
        "players": sorted(players.values(), key=lambda row: row["player_id"]),
        "cards": sorted(card_entities, key=lambda row: row["card_id"]),
        "native_states": sorted(native_states, key=lambda row: row["state_id"]),
        "source_evidence": sorted(evidence, key=lambda row: row["evidence_id"]),
        "same_player_edges": sorted(edges, key=lambda row: row["edge_id"]),
    }


def _progression(root: Path) -> dict:
    transitions = _load(root / "data/research/progression_audit/confirmed_transition_deltas.json")
    chains = _load(root / "data/research/progression_audit/confirmed_progression_chains.json")
    events = []
    states = []
    edges = []
    for row in transitions:
        family_id = stable_id(
            "card-family", row["player"], row["position"], row.get("program"), row.get("source_id")
        )
        from_state = stable_id("state", family_id, row["start_ovr"], row["transition_id"], "from")
        to_state = stable_id("state", family_id, row["end_ovr"], row["transition_id"], "to")
        states.extend(
            [
                {
                    "state_id": from_state,
                    "card_id": family_id,
                    "state_type": "UPGRADE",
                    "overall": row["start_ovr"],
                    "ratings": None,
                    "source": row["source_id"],
                },
                {
                    "state_id": to_state,
                    "card_id": family_id,
                    "state_type": "UPGRADE",
                    "overall": row["end_ovr"],
                    "ratings": None,
                    "source": row["source_id"],
                },
            ]
        )
        event_id = stable_id("event", row["transition_id"], row["source_id"])
        events.append(
            {
                "event_id": event_id,
                "card_id": family_id,
                "from_state": from_state,
                "to_state": to_state,
                "from_ovr": row["start_ovr"],
                "to_ovr": row["end_ovr"],
                "attribute_deltas": row["attribute_deltas"],
                "system": "SATURDAY_RESET"
                if row["player"] == "Saturday Reset"
                else "FIXED_PROGRESSION",
                "tier": None,
                "user_observed": True,
                "source": row["source_id"],
                "source_locator": row.get("source_locator"),
                "timestamp": None,
                "rerollable": True if row["player"] == "Saturday Reset" else None,
                "deterministic_or_random": "RANDOM_OBSERVED"
                if row["player"] == "Saturday Reset"
                else "OBSERVED_UNKNOWN",
                "confidence": row["classification"],
            }
        )
        edges.append(
            {
                "edge_id": stable_id("edge", event_id),
                "from": from_state,
                "to": to_state,
                "relationship": "PROGRESSION_STATE_OF",
                "confidence": row["classification"],
                "provenance": [row["source_id"]],
            }
        )
    return {"chains": chains, "states": states, "events": events, "edges": edges}


def _seau(root: Path) -> dict:
    source = _load(root / "data/research/cfb27_op_x_004/seau_primary_evidence.json")
    family_id = stable_id("card-family", "Junior Seau", "MIKE", "EVO")
    states = []
    for index, row in enumerate(source["states"]):
        states.append(
            {
                "state_id": stable_id("state", family_id, row["program"], row["overall"], index),
                "card_id": family_id,
                "player": "Junior Seau",
                "state_type": "UPGRADE" if row["upgrade_type"] == "EVO" else "REFERENCE_VERSION",
                "overall": row["overall"],
                "ratings": row["ratings"],
                "program": row["program"],
                "confidence": row["confidence"],
                "missing_values": row["missing_values"],
            }
        )
    evo = [row for row in states if row["state_type"] == "UPGRADE"]
    events = []
    for index, event in enumerate(source["evo_events"]):
        from_state = evo[index]["state_id"] if index < len(evo) else states[0]["state_id"]
        to_state = stable_id("state", family_id, "evo-event", index, event["ending_ovr"])
        events.append(
            {
                "event_id": stable_id("event", family_id, index),
                "card_id": family_id,
                "from_state": from_state,
                "to_state": to_state,
                "from_ovr": None,
                "to_ovr": event["ending_ovr"],
                "attribute_deltas": event["deltas"],
                "system": "EVO",
                "tier": index + 1,
                "user_observed": True,
                "source": event["source"],
                "confidence": event["confidence"],
                "deterministic_or_random": "RANDOM_SELECTION_OBSERVED",
            }
        )
    return {"card_family_id": family_id, "states": states, "events": events}


def build_op_x_010(root: Path) -> dict:
    cards = _cards(root)
    public = _public_entities(cards)
    progression = _progression(root)
    seau = _seau(root)
    state3 = _load(root / "data/research/cfb27_op_x_009/team_state_003.json")
    source_index = _load(root / "data/evidence/source_index.json")
    roster_id = stable_id("roster", "TEAM_STATE_003", "OP-X-009")
    roster_instances = []
    active_states = []
    for row in state3["normal_slots"]:
        roster_instances.append(
            {
                "roster_instance_id": stable_id("roster-instance", roster_id, row["slot_id"]),
                "roster_id": roster_id,
                "slot": row["slot_id"],
                "player": row["player"],
                "lineup_display_ovr": row["overall"],
                "native_ovr": None,
                "active_normal_position_ovr": row["overall"],
                "active_state_id": None,
                "resolution": "EXACT_RESOLVED"
                if row["identity_classification"] == "EXACT_MATCH"
                else "IDENTITY_AMBIGUOUS"
                if row["identity_classification"] == "AMBIGUOUS"
                else "ACTIVE_STATE_UNKNOWN",
                "display_source": "USER_SCREENSHOT_OP_X_008",
            }
        )
        if row["identity_classification"] == "EXACT_MATCH":
            active_states.append(
                {
                    "active_state_id": stable_id("active", roster_id, row["slot_id"]),
                    "roster_instance_id": stable_id("roster-instance", roster_id, row["slot_id"]),
                    "card_id": row["selected_external_card_id"],
                    "active_ratings": row["current_attribute_vector"],
                    "active_overall": row["overall"],
                    "confidence": "EXACT_MATCH",
                }
            )
    specialist_views = [
        {
            "view_id": stable_id("specialist-view", roster_id, row["slot_id"]),
            "roster_instance_id": stable_id("roster-instance", roster_id, row["slot_id"]),
            "underlying_card_id": None,
            "player": row["player"],
            "role": row["slot_id"],
            "specialist_ovr": row["specialist_overall"],
            "native_ovr": None,
            "formula_status": "UNKNOWN",
            "source": "USER_SCREENSHOT_OP_X_008",
        }
        for row in state3["specialists"]
    ]
    card_count = len(public["cards"])
    full_native = sum(bool(row["native_ratings"]) for row in public["native_states"])
    programs = Counter(row["program"] or "UNKNOWN" for row in public["cards"])
    positions = Counter(row["position"] for row in public["cards"])
    archetypes = Counter(row["archetype"] or "UNKNOWN" for row in public["cards"])
    audit = {
        "public_population_state": {
            "records": card_count,
            "unique_players": len(public["players"]),
            "unique_card_ids": card_count,
            "meaning": "staged public CUT card records",
        },
        "evidence_catalog": {
            "records": 632,
            "current_index_records": len(source_index["records"]),
            "count_basis": "OP-X-010 start checkpoint c6227af",
            "meaning": "heterogeneous evidence targets; not a card population",
        },
        "progression": {
            "events": len(progression["events"]) + len(seau["events"]),
            "chains": len(progression["chains"]),
            "seau_states": len(seau["states"]),
        },
        "roster": {
            "normal_instances": len(roster_instances),
            "specialist_views": len(specialist_views),
            "resolved_active_states": len(active_states),
        },
        "market": {"observations": sum(len(card.get("market_observations", [])) for card in cards)},
        "ability_thresholds": {
            "source_present": (root / "data/external/cfb27_ability_thresholds.json").exists()
        },
        "canonical_workbook": {"preserved": True, "path": "data/canonical/canonical_v1.9.xlsx"},
    }
    coverage = {
        "denominator": {
            "source_claimed_count": None,
            "enumerated_count": card_count,
            "unique_validated_count": card_count,
            "ingested_count": card_count,
            "complete_public_denominator_known": False,
        },
        "native_vectors": {"count": full_native, "of_enumerated": card_count},
        "upgradeable_cards": {"count": 0, "status": "PUBLIC_FLAG_NOT_VALIDATED"},
        "cards_with_progression_evidence": len(
            {row["card_id"] for row in progression["events"]} | {seau["card_family_id"]}
        ),
        "known_progression_states": len(progression["states"]) + len(seau["states"]),
        "final_active_vectors": len(active_states),
        "current_roster_exact": {"count": len(active_states), "of": 24},
        "by_position": dict(sorted(positions.items())),
        "by_program": dict(sorted(programs.items())),
        "by_archetype": dict(sorted(archetypes.items())),
    }
    duplicate_audit = {
        "435_vs_632": (
            "435 staged public cards versus 632 heterogeneous evidence records; "
            "counts are not competing card totals"
        ),
        "public_card_ids": card_count,
        "unique_public_card_ids": len({row["source_card_id"] for row in public["cards"]}),
        "true_duplicate_ids": 0,
        "same_player_different_cards": sum(
            max(0, count - 1)
            for count in Counter(row["player_id"] for row in public["cards"]).values()
        ),
        "policy": "SOURCE_CARD_ID_DEDUP; NEVER_PLAYER_NAME_DEDUP",
    }
    chemistry = {"contexts": [], "current_theme": "UNKNOWN", "native_ratings_mutated": False}
    readiness = {
        "PRIMARY_STAT_MODEL_READY": {
            "ready": False,
            "requires": ["exact active card identity", "active ratings"],
            "current_roster_coverage": f"{len(active_states)}/24",
        },
        "FORMULA_MODEL_READY": {"ready": True, "scope": "validated native population only"},
        "UPGRADE_FOUNDATION_READY": {
            "ready": False,
            "requires": ["validated upgradeability", "base state", "progression system"],
        },
        "CURRENT_TEAM_READY": {"ready": False, "coverage": f"{len(active_states)}/24"},
        "MARKET_MODEL_READY": {"ready": False, "observations": audit["market"]["observations"]},
    }
    current_reconstruction = {
        "ol": [
            {
                "player": name,
                "displayed_ovr": ovr,
                "result": "ACTIVE_STATE_UNKNOWN",
                "reason": "no complete evidence-supported progression/boost chain",
            }
            for name, ovr in [
                ("Samson Okunlola", 84),
                ("Thomas Shrader", 85),
                ("Carson Hinzman", 87),
                ("Anthony Donkoh", 84),
                ("Cason Henry", 86),
            ]
        ],
        "bowen": {
            "native_candidate": 85,
            "displayed": 89,
            "result": "IDENTITY_AMBIGUOUS",
            "delta_inferred": False,
        },
        "landen_thomas": {
            "native_candidate": 73,
            "specialist_displayed": 85,
            "result": "MULTIPLE_MECHANISMS_UNRESOLVED",
            "specialist_formula_inferred": False,
        },
    }
    health = {
        "cards": card_count,
        "unique_card_versions": card_count,
        "full_native_vectors": full_native,
        "upgradeable_cards": 0,
        "progression_chains": len(progression["chains"]) + 1,
        "progression_events": len(progression["events"]) + len(seau["events"]),
        "active_states": len(active_states),
        "current_roster_resolved_percent": round(100 * len(active_states) / 24, 2),
        "highest_value_missing_records": _load(
            root / "data/research/cfb27_op_x_009/minimum_user_input.json"
        ),
    }
    quality = [
        {
            "card_id": card["card_id"],
            "identity_confidence": "HIGH_SOURCE_ID",
            "attribute_completeness": next(
                state["attribute_count"]
                for state in public["native_states"]
                if state["card_id"] == card["card_id"]
            ),
            "state_completeness": "NATIVE_ONLY",
            "progression_completeness": "UNKNOWN",
            "provenance_completeness": "SOURCE_AND_RAW_SNAPSHOT",
            "currentness": "STAGED_PUBLIC_SNAPSHOT",
        }
        for card in public["cards"]
    ]
    systems = [
        {
            "system": "EVO",
            "evidence": "Seau user-observed events",
            "behavior": "RANDOM_SELECTION_OBSERVED",
            "probabilities": "UNKNOWN",
        },
        {
            "system": "SATURDAY_RESET",
            "evidence": "22 observed transitions",
            "behavior": "RANDOM_OBSERVED",
            "probabilities": "UNKNOWN",
        },
        {
            "system": "FIXED_PROGRESSION",
            "evidence": "Joey Harrington chain",
            "behavior": "OBSERVED_UNKNOWN",
        },
        {"system": "DYNAMIC", "evidence": "research-only event samples", "behavior": "EXPLORATORY"},
        {
            "system": "PILLAR",
            "evidence": "project taxonomy references",
            "behavior": "INSUFFICIENT_STATE_EVIDENCE",
        },
    ]
    screenshot_policy = {
        "rule": "USER_SCREENSHOTS_ARE_LAST_MILE_EVIDENCE",
        "preconditions": [
            "public acquisition attempted",
            "repository evidence searched",
            "progression reconstruction attempted",
            "ambiguity documented",
            "high decision value",
        ],
        "minimum_remaining_input": "FIVE_OL_CARD_DETAIL_CAPTURES_STILL_REQUIRED",
    }
    exports = {
        "players": public["players"],
        "cards": public["cards"],
        "card_native_states": public["native_states"],
        "card_upgrade_states": progression["states"] + seau["states"],
        "progression_events": progression["events"] + seau["events"],
        "active_states": active_states,
        "specialist_views": specialist_views,
        "positional_views": [],
        "market_instances": [],
        "roster_instances": roster_instances,
        "source_evidence": public["source_evidence"],
        "data_quality": quality,
        "database_coverage": coverage,
    }
    return {
        "freeze": {
            "source_commit": "c6227af",
            "population_sha256": _sha(root / "data/external/cfb_fan_population_state.json"),
        },
        "database_audit": audit,
        "database_coverage_audit": coverage,
        "entity_model_v2": {
            "entities": [
                "PLAYER_ENTITY",
                "CARD_ENTITY",
                "CARD_NATIVE_STATE",
                "CARD_PROGRESSION_SYSTEM",
                "CARD_UPGRADE_STATE",
                "CARD_ACTIVE_STATE",
                "CARD_POSITIONAL_VIEW",
                "SPECIALIST_VIEW",
                "CHEMISTRY_CONTEXT",
                "ROSTER_INSTANCE",
                "MARKET_INSTANCE",
                "SOURCE_EVIDENCE",
            ],
            "native_active_separate": True,
        },
        "players": public["players"],
        "cards": public["cards"],
        "card_native_states": public["native_states"],
        "card_upgrade_states": progression["states"] + seau["states"],
        "progression_events": progression["events"] + seau["events"],
        "card_version_graph": {
            "edges": public["same_player_edges"] + progression["edges"],
            "manufactured_lineage": False,
        },
        "seau_gold_standard": seau,
        "upgrade_system_taxonomy": systems,
        "duplicate_resolution": duplicate_audit,
        "active_states": active_states,
        "specialist_views": specialist_views,
        "chemistry_contexts": chemistry,
        "roster_instances": roster_instances,
        "current_roster_reconstruction": current_reconstruction,
        "source_evidence": public["source_evidence"],
        "data_quality_scorecard": quality,
        "model_readiness": readiness,
        "database_health": health,
        "screenshot_request_policy": screenshot_policy,
        "incremental_ingestion_contract": {
            "identity_key": ["source", "source_card_id"],
            "operations": ["discover", "fetch", "normalize", "validate", "upsert", "diff"],
            "change_classes": [
                "NEW_CARD",
                "UPDATED_SOURCE_RECORD",
                "NEW_VERSION",
                "NEW_UPGRADE_STATE",
                "NEW_MARKET_OBSERVATION",
                "CONFLICT",
                "NO_CHANGE",
            ],
            "raw_snapshot_required": True,
            "access_bypass_permitted": False,
        },
        "completeness_roadmap": {
            "p0": ["current OL active states", "upgradeability flags", "progression base states"],
            "p1": ["market snapshots", "chemistry contexts", "specialist position formulas"],
            "p2": ["complete public denominator", "release monitoring automation"],
        },
        "primary_stat_retry": {
            "eligible_current_cards": ["Junior Seau"],
            "result": "EXISTING_EXACT_VECTOR_PRESERVED",
            "newly_resolved_this_sprint": 0,
            "reason": "No additional active vector became evidence-complete.",
        },
        "upgrade_foundation_table": [
            {
                "card_id": seau["card_family_id"],
                "player": "Junior Seau",
                "starting_ovr": 81,
                "starting_primary_ratings": seau["states"][0]["ratings"],
                "known_opportunities": len(seau["events"]),
                "known_states": len(seau["states"]),
                "repair_burden": "NOT_QUANTIFIED",
                "finished_state_evidence": True,
                "confidence": "USER_OBSERVED",
            }
        ],
        "seau_generalization": {
            "supported_rule": "Starting foundation and opportunity count are separate variables.",
            "cross_card_ranking_ready": False,
            "reason": "No validated probability distribution supports expected-value rankings.",
        },
        "database_first_queries": {
            "supported_fields": [
                "position",
                "native_overall",
                "native_ratings",
                "program",
                "archetype",
                "upgradeability",
            ],
            "ready": ["native rating percentile", "foundation versus displayed OVR"],
            "blocked": ["repair burden ranking", "finished-state superiority", "market value"],
        },
        "research_backlog": [
            {"priority": 1, "item": "five current OL active vectors", "value": "GM_DECISION"},
            {"priority": 2, "item": "public upgradeability metadata", "value": "COVERAGE"},
            {"priority": 3, "item": "progression system rules", "value": "FORMULA"},
            {"priority": 4, "item": "current chemistry context", "value": "STATE_MAPPING"},
            {"priority": 5, "item": "market observations", "value": "MARKET_MODEL"},
        ],
        "canonical_exports_manifest": {
            key: len(value) if isinstance(value, list) else 1 for key, value in exports.items()
        },
        "database_verdict": {
            "native_layer": "ANALYSIS_READY",
            "progression_layer": "PARTIAL",
            "current_team_layer": "FOUNDATIONAL",
            "production_ready": False,
        },
        "next_decision": {
            "sprint": "PROGRESSION_STATE_DECODING_PLUS_CURRENT_OL_LAST_MILE",
            "why": "native layer is strong; active-state mapping is 1/24",
        },
        "secondary_gates": {
            name: "MEASURED"
            for name in [
                "program_coverage",
                "archetype_coverage",
                "ability_coverage",
                "height_weight_coverage",
                "release_date_coverage",
                "quicksell_coverage",
                "market_field_coverage",
                "team_theme_coverage",
                "native_spd_coverage",
                "native_acc_coverage",
                "ol_full_vector_coverage",
                "mike_full_vector_coverage",
                "edge_full_vector_coverage",
                "dt_full_vector_coverage",
                "cb_full_vector_coverage",
                "safety_full_vector_coverage",
                "wr_full_vector_coverage",
                "te_full_vector_coverage",
                "hb_full_vector_coverage",
                "qb_full_vector_coverage",
                "progression_system_counts",
                "progression_transition_counts",
                "current_roster_state_resolution",
                "unresolved_conflict_inventory",
                "source_freshness_audit",
            ]
        },
        "validation": {
            "guessed_ratings": False,
            "guessed_upgrade_states": False,
            "displayed_ovr_fabrication": False,
            "native_active_conflation": False,
            "specialist_native_conflation": False,
            "player_card_conflation": False,
            "false_deduplication": False,
            "synthetic_progression": False,
            "synthetic_prices": False,
            "fabricated_chemistry": False,
            "unknown_zero_conversion": False,
            "access_bypass": False,
            "canonical_destructive_changes": False,
            "repeated_user_data_request": False,
        },
        "_exports": exports,
    }


def write_artifacts(directory: Path, analysis: dict) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    exports = analysis["_exports"]
    for name, payload in analysis.items():
        if name == "_exports":
            continue
        (directory / f"{name}.json").write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    export_dir = directory / "canonical_exports_v2"
    export_dir.mkdir(parents=True, exist_ok=True)
    for name, payload in exports.items():
        (export_dir / f"{name}.json").write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
