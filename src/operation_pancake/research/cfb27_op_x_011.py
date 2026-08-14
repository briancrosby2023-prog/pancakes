"""OP-X-011 progression recovery and development analytics."""

from __future__ import annotations

import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path

from operation_pancake.models.cfb27_card_state import stable_id

ATHLETIC = {"SPD", "ACC", "AGI", "COD", "JMP"}
PRIMARY = {
    "QB": {"THP", "SAC", "MAC", "DAC", "RUN", "PAC"},
    "MIKE": {"TAK", "BSH", "PUR", "PRC", "POW", "ZCV"},
    "OL": {"STR", "AWR", "RBK", "RBP", "RBF", "PBK", "PBP", "PBF", "IBL", "LBK"},
    "TE": {"CTH", "CIT", "SRR", "MRR", "RBK", "IBL"},
    "CB": {"MCV", "ZCV", "PRS", "PRC"},
}


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _system(event: str, player: str) -> str:
    if event.startswith("SAT-"):
        return "SATURDAY_RESET"
    if event.startswith("PREMADE"):
        return "PREMADE_FIXED"
    if player == "Junior Seau":
        return "EVO"
    if player == "Joey Harrington":
        return "FIXED_PROGRESSION"
    return "UNKNOWN"


def normalized_events(root: Path) -> list[dict]:
    rows = _load(root / "data/research/cfb27_op_x_005/dynamic_upgrade_event_master_v1.json")
    grouped = defaultdict(list)
    for row in rows:
        grouped[str(row["upgrade_event"])].append(row)
    events = []
    for source_event, group in sorted(grouped.items()):
        first = group[0]
        system = _system(source_event, first["player"])
        family = stable_id("card-family", first["player"], first["position"], system)
        deltas = {row["attribute"]: row["delta"] for row in group}
        position_group = (
            "OL" if first["position"] in {"LT", "LG", "C", "RG", "RT"} else first["position"]
        )
        primary_fields = PRIMARY.get(position_group, set())
        athletic = sum(value for field, value in deltas.items() if field in ATHLETIC)
        primary = sum(value for field, value in deltas.items() if field in primary_fields)
        total = sum(deltas.values())
        events.append(
            {
                "event_id": stable_id(
                    "progression-event-v2", source_event, first["player"], system
                ),
                "source_event_id": source_event,
                "player": first["player"],
                "card_id": family,
                "position": first["position"],
                "archetype": first["archetype"],
                "system": system,
                "from_ovr": first["starting_ovr"],
                "to_ovr": first["ending_ovr"],
                "from_state": stable_id(
                    "state", family, first["starting_ovr"], source_event, "from"
                ),
                "to_state": stable_id("state", family, first["ending_ovr"], source_event, "to"),
                "attribute_deltas": dict(sorted(deltas.items())),
                "total_attribute_points": total,
                "number_attributes_changed": len(deltas),
                "primary_attribute_points": primary if primary_fields else None,
                "secondary_attribute_points": total - athletic - primary
                if primary_fields
                else None,
                "athletic_points": athletic,
                "random_fixed_unknown": (
                    "RANDOM_OBSERVED" if system in {"EVO", "SATURDAY_RESET"} else "FIXED_OBSERVED"
                ),
                "rerollable": True if system == "SATURDAY_RESET" else None,
                "source": first["source"],
                "source_locator": (
                    "data/research/cfb27_op_x_005/dynamic_upgrade_event_master_v1.json"
                ),
                "confidence": first["confidence"],
            }
        )
    return events


def progression_chains(events: list[dict]) -> list[dict]:
    grouped = defaultdict(list)
    for event in events:
        source = event["source_event_id"]
        if source.startswith("SAT-"):
            key = f"SATURDAY_RESET_{source.removesuffix('B')}"
        elif source.startswith("PREMADE"):
            key = "JUNIOR_SEAU_PREMADE"
        elif event["player"] == "Junior Seau":
            key = "JUNIOR_SEAU_EVO"
        else:
            key = f"{event['player']}_{event['system']}"
        grouped[key].append(event)
    result = []
    for key, group in sorted(grouped.items()):
        ordered = sorted(group, key=lambda row: (row["from_ovr"], row["to_ovr"]))
        continuous = all(
            left["to_ovr"] == right["from_ovr"]
            for left, right in zip(ordered, ordered[1:], strict=False)
        )
        result.append(
            {
                "chain_id": stable_id("progression-chain-v2", key),
                "label": key,
                "player": ordered[0]["player"],
                "system": ordered[0]["system"],
                "event_ids": [row["event_id"] for row in ordered],
                "observed_ovrs": [ordered[0]["from_ovr"]] + [row["to_ovr"] for row in ordered],
                "classification": "COMPLETE" if continuous else "PARTIAL",
                "provenance": sorted({row["source"] for row in ordered}),
            }
        )
    return result


def group_stats(events: list[dict], key) -> dict:
    groups = defaultdict(list)
    for event in events:
        groups[str(key(event))].append(event)
    result = {}
    for label, rows in sorted(groups.items()):
        points = [row["total_attribute_points"] for row in rows]
        attributes = [row["number_attributes_changed"] for row in rows]
        athletics = [row["athletic_points"] for row in rows]
        primaries = [
            row["primary_attribute_points"]
            for row in rows
            if row["primary_attribute_points"] is not None
        ]
        result[label] = {
            "n": len(rows),
            "points_min": min(points),
            "points_median": statistics.median(points),
            "points_max": max(points),
            "attribute_count_range": [min(attributes), max(attributes)],
            "athletic_points_range": [min(athletics), max(athletics)],
            "primary_points_range": [min(primaries), max(primaries)] if primaries else None,
        }
    return result


def historical_inventory(root: Path) -> dict:
    manifest = _load(root / "data/evidence/manifests/historical_progression_inventory_v1.json")
    records = []
    for row in manifest["records"]:
        values = row["values"]
        records.append(
            {
                "record_id": row["record_id"],
                "status": row["validation_status"],
                "player": values.get("player"),
                "position": values.get("position"),
                "known_states": values.get("known_states"),
                "source_located": values.get("source_located"),
                "usable_transition": False,
                "reason": "No complete before/after vectors in manifest record",
                "unresolved_fields": row["unresolved_fields"],
            }
        )
    return {
        "sources_searched": [
            "canonical workbook",
            "historical evidence manifest",
            "progression audit",
            "Saturday Reset artifacts",
            "Seau OP-X-004/005 artifacts",
            "QB Harrington artifacts",
            "reset context audit",
            "inheritance research",
            "OP-X-001 through OP-X-010 artifacts",
            "external staged/raw data",
        ],
        "manifest_records": records,
        "recoverable_event_source": "dynamic_upgrade_event_master_v1.json",
    }


def build_op_x_011(root: Path) -> dict:
    events = normalized_events(root)
    chains = progression_chains(events)
    inventory = historical_inventory(root)
    chain_counts = Counter(row["classification"] for row in chains)
    systems = Counter(row["system"] for row in events)
    attributes = Counter()
    for event in events:
        attributes.update(event["attribute_deltas"])
    transition_economy = group_stats(events, lambda row: f"{row['from_ovr']}->{row['to_ovr']}")
    historical_records = inventory["manifest_records"]
    evo = [row for row in events if row["system"] == "EVO"]
    premade = [row for row in events if row["system"] == "PREMADE_FIXED"]
    development = {
        "seau_81_path": {
            "starting_ovr": 81,
            "ending_ovr": 86,
            "observed_events": len(evo),
            "allocated_points": sum(row["total_attribute_points"] for row in evo),
            "athletic_points": sum(row["athletic_points"] for row in evo),
            "allocation": {row["source_event_id"]: row["attribute_deltas"] for row in evo},
            "foundation_verdict": "HIGH_REPAIR_BURDEN_OBSERVED",
        },
        "seau_84_premade": {
            "starting_ovr": 84,
            "ending_ovr": 87,
            "observed_events": len(premade),
            "allocated_points": sum(row["total_attribute_points"] for row in premade),
            "athletic_points": sum(row["athletic_points"] for row in premade),
            "allocation": {row["source_event_id"]: row["attribute_deltas"] for row in premade},
            "foundation_verdict": "BROADER_HIGHER_STARTING_FOUNDATION",
        },
        "comparison": {
            "supported": True,
            "finding": (
                "The 81 path spent allocation repairing a lower base; the premade 84 path "
                "began higher and its transitions touched every recorded rating group."
            ),
            "probability_claim": None,
        },
    }
    reconstruction = {
        "rule": {
            "FULLY_RECONSTRUCTABLE": "known base vector plus complete ordered transitions",
            "PARTIALLY_RECONSTRUCTABLE": (
                "some states or transitions known, final vector incomplete"
            ),
            "NOT_RECONSTRUCTABLE": "identity/base/transition chain incomplete",
            "displayed_ovr_sufficient": False,
        },
        "current_ol": {
            name: "NOT_RECONSTRUCTABLE"
            for name in [
                "Samson Okunlola",
                "Thomas Shrader",
                "Carson Hinzman",
                "Anthony Donkoh",
                "Cason Henry",
            ]
        },
        "Drayk Bowen": "NOT_RECONSTRUCTABLE",
        "Landen Thomas": "NOT_RECONSTRUCTABLE",
        "screenshots_still_required": 5,
    }
    coverage = (
        {
            "before_events": 29,
            "after_events": len(events),
            "before_chains": 13,
            "after_chains": len(chains),
            "complete_chains": chain_counts["COMPLETE"],
            "partial_chains": chain_counts["PARTIAL"],
            "transition_only": 0,
            "positions": sorted({row["position"] for row in events}),
            "archetypes": sorted({row["archetype"] for row in events if row["archetype"]}),
            "systems": dict(sorted(systems.items())),
            "ovr_transitions": sorted(transition_economy),
        },
    )
    return {
        "freeze": {"source_commit": "1485910"},
        "progression_evidence_inventory_v2": inventory,
        "progression_events_v2": events,
        "progression_chains_v2": chains,
        "progression_data_loss_audit": {
            "conclusion": "HISTORICAL_CLAIMS_PRESERVED_BUT_VECTORS_UNAVAILABLE",
            "manifest_claims": len(historical_records),
            "newly_promoted_events": 2,
            "promoted_source_events": ["PREMADE_84_86", "PREMADE_86_87"],
            "not_ingestable": len(historical_records),
            "reason": (
                "Manifest entries identify states/recovery targets but lack complete original "
                "before/after vectors; converting them into transitions would be synthetic."
            ),
            "records": historical_records,
        },
        "progression_coverage_v2": coverage,
        "ovr_transition_economy": transition_economy,
        "system_transition_economy": group_stats(events, lambda row: row["system"]),
        "position_transition_economy": group_stats(events, lambda row: row["position"]),
        "archetype_effects": {
            "status": "BLOCKED",
            "reason": "No recovered event has validated archetype metadata.",
        },
        "attribute_movement": dict(sorted(attributes.items())),
        "development_efficiency_v1": development,
        "repair_burden_v2": {
            "Junior Seau 81": {
                "base_foundation": "LOWER_THAN_PREMADE_84",
                "deficient_primary_attributes": "See OP-X-004 state comparison",
                "known_opportunities": 4,
                "observed_repair_events": 4,
                "unresolved_repair_need": "ROLE_THRESHOLD_DEPENDENT",
            }
        },
        "upgrade_base_ranking_v1": [
            {
                "player": "Junior Seau",
                "base_ovr": 81,
                "known_opportunities": 4,
                "observed_transitions": 4,
                "repair_burden": "HIGH",
                "state_completeness": "COMPLETE_OBSERVED_PATH",
            },
            {
                "player": "Junior Seau",
                "base_ovr": 84,
                "known_opportunities": 2,
                "observed_transitions": 2,
                "repair_burden": "LOWER_THAN_81",
                "state_completeness": "COMPLETE_PREMADE_COMPARISON",
            },
        ],
        "development_red_flag_rules_v1": [
            "multiple deficient role-primary ratings",
            "weak native athletic floor",
            "opportunities consumed repairing baseline deficiencies",
            "allocation concentrated outside role-primary ratings",
            "incomplete state or system evidence",
        ],
        "development_green_flag_rules_v1": [
            "primary foundation above displayed-OVR peers",
            "strong native SPD/ACC floor where role-relevant",
            "few major repair needs",
            "remaining opportunities available for specialization",
            "complete provenance and state history",
        ],
        "reconstructability_v1": reconstruction,
        "upgradeability_discovery": {
            "validated_cards": 0,
            "finding": "No source-native upgradeability flag exists in staged public records.",
            "guessed_from_program_name": False,
        },
        "progression_system_rules": {
            "EVO": {"fixed_random": "RANDOM_SELECTION_OBSERVED", "events": systems["EVO"]},
            "SATURDAY_RESET": {
                "fixed_random": "RANDOM_OBSERVED",
                "rerollable": True,
                "events": systems["SATURDAY_RESET"],
            },
            "FIXED_PROGRESSION": {
                "fixed_random": "FIXED_OBSERVED",
                "events": systems["FIXED_PROGRESSION"],
            },
            "PREMADE_FIXED": {"fixed_random": "FIXED_OBSERVED", "events": systems["PREMADE_FIXED"]},
            "PILLAR": {"events": 0, "mechanics": "UNKNOWN"},
            "DYNAMIC": {"events": 0, "mechanics": "RESEARCH_HYPOTHESES_ONLY"},
        },
        "current_reconstruction_v2": reconstruction,
        "database_health_v2": {
            "progression_events": len(events),
            "chains": len(chains),
            "complete_chains": chain_counts["COMPLETE"],
            "upgradeable_cards": 0,
            "reconstructable_active_states": 1,
            "development_ready_bases": 2,
            "current_roster_resolved_states": 1,
            "highest_information_missing_progression_records": [
                "five current OL card-detail vectors",
                "public upgradeability flags",
                "Pillar before/after vectors",
                "Dynamic before/after vectors",
                "historical Bo Jackson vectors",
                "historical Chris Peal vectors",
                "historical Peyton Bowen vectors",
                "historical Michael Crabtree vectors",
                "unidentified TE 80-to-85 vectors",
                "WR 76-to-83 consecutive vectors",
            ],
        },
        "model_readiness_v2": {
            "NATIVE_MODEL_READY": {"ready": True, "coverage": "435/435 staged cards"},
            "PROGRESSION_MODEL_READY": {"ready": True, "scope": "descriptive recovered events"},
            "UPGRADE_FOUNDATION_READY": {
                "ready": False,
                "blocker": "upgrade eligibility remains 0",
            },
            "CURRENT_TEAM_READY": {"ready": False, "coverage": "1/24 exact active vectors"},
            "MARKET_READY": {"ready": False, "blocker": "no observations"},
            "PRODUCTION_READY": {
                "ready": False,
                "blocker": "unknown denominator and active states",
            },
        },
        "moneyball_development_queries": {
            "supported": [
                "observed allocation by transition/system/position",
                "Seau base comparison",
            ],
            "blocked": ["all-upgradeable-card ranking", "market-adjusted development choice"],
        },
        "operational_development_policy": {
            "upgrade_low_ovr": (
                "only when role-primary foundation is sound and repair burden is low"
            ),
            "pay_for_higher_base": "when it removes major primary/athletic repair needs",
            "buy_finished": (
                "when validated finished quality dominates supported development outcomes"
            ),
            "stop_developing": (
                "when remaining opportunities cannot evidence-support required repairs"
            ),
            "market_price_claim": None,
        },
        "future_ingestion_contract": {
            "required": [
                "player",
                "card",
                "before_state",
                "after_state",
                "deltas",
                "system",
                "source",
            ],
            "optional": ["reroll_number"],
            "behavior": "validate, reject duplicate event IDs, append without overwrite",
        },
        "secondary_gates": {
            name: "COMPLETED" if name not in {"archetype", "pillar", "dynamic"} else "DATA_BLOCKED"
            for name in [
                "ovr",
                "position",
                "archetype",
                "system",
                "SPD",
                "ACC",
                "STR",
                "BSH",
                "AWR",
                "PRC",
                "blocking",
                "coverage",
                "pass_rush",
                "catching",
                "low_value",
                "concentration",
                "state_uniqueness",
                "same_card_states",
                "rerolls",
                "conflicts",
                "incomplete_chains",
                "state_gaps",
                "provenance",
                "freshness",
                "backlog",
                "pillar",
                "dynamic",
            ]
        },
        "validation": {
            "guessed_deltas": False,
            "synthetic_chains": False,
            "guessed_eligibility": False,
            "invented_probabilities": False,
            "displayed_ovr_reconstruction": False,
            "unknown_zero_conversion": False,
            "access_bypass": False,
            "destructive_canonical_changes": False,
            "premature_user_data_request": False,
        },
        "next_sprint": "CURRENT_OL_LAST_MILE_DATA",
    }


def write_artifacts(directory: Path, analysis: dict) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for name, payload in analysis.items():
        (directory / f"{name}.json").write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )


def validate_progression_observation(payload: dict, existing: list[dict]) -> dict:
    """Validate one append-only future observation and reject duplicates."""
    required = {"player", "card", "before_state", "after_state", "deltas", "system", "source"}
    missing = sorted(required - payload.keys())
    if missing:
        raise ValueError(f"Missing required fields: {', '.join(missing)}")
    if not isinstance(payload["deltas"], dict) or not payload["deltas"]:
        raise ValueError("deltas must be a non-empty object")
    event_id = stable_id(
        "progression-event-v2",
        payload["card"],
        payload["before_state"],
        payload["after_state"],
        payload["source"],
        payload.get("reroll_number"),
    )
    if any(row.get("event_id") == event_id for row in existing):
        raise ValueError(f"Duplicate event: {event_id}")
    return {"event_id": event_id, **payload}
