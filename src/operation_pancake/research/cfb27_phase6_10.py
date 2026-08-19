"""Phase VI-X complete ability intelligence and descriptive GM layers."""

from __future__ import annotations

import gzip
import hashlib
import json
import statistics
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

from operation_pancake.research.cfb27_phase2 import is_special
from operation_pancake.research.cfb27_phase5 import ATTRIBUTE_ALIASES, normalize_thresholds

TIERS = ("BRONZE", "SILVER", "GOLD", "PLATINUM")
OFFENSE = {"QB", "HB", "WR", "TE"}
POSITION_EQUIVALENTS = {"MLB": "MIKE", "LE": "EDGE", "RE": "EDGE"}
CFB_FAN_CROSS_CHECKS = [
    {
        "position": "MIKE",
        "archetype": "Lurker",
        "ability": "House Call",
        "tier": "BRONZE",
        "cfb_fan_attribute": "CTH",
        "cfb_fan_required_rating": 80,
        "cfb_labs_attribute": "CTH",
        "cfb_labs_required_rating": 71,
        "classification": "CONFLICT_DOMAIN_UNRESOLVED",
        "source": "https://cfb.fan/players/26550-junior-seau/27-110026550/",
    },
    {
        "position": "MIKE",
        "archetype": "Lurker",
        "ability": "Robber",
        "tier": "BRONZE",
        "cfb_fan_attribute": "COD",
        "cfb_fan_required_rating": 80,
        "cfb_labs_attribute": "ACC",
        "cfb_labs_required_rating": 91,
        "classification": "CONFLICT_DOMAIN_UNRESOLVED",
        "source": "https://cfb.fan/players/26550-junior-seau/27-110026550/",
    },
]


def _parse_release_date(value: str) -> datetime:
    """Accept legacy M/D/Y and canonical ISO-8601 release timestamps."""
    try:
        return datetime.strptime(value, "%m/%d/%Y")
    except ValueError:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)


def _json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def grouped_thresholds(snapshot: dict) -> list[dict]:
    groups = []
    for source_row, row in enumerate(snapshot["records"], start=1):
        for tier in TIERS:
            requirements = []
            title = tier.title()
            for attribute_key, suffix in (("Attribute", ""), ("Attribute2", "2")):
                name = row.get(attribute_key)
                required = row.get(f"{title}{suffix}")
                if not name or required in (None, ""):
                    continue
                attribute = ATTRIBUTE_ALIASES.get(name)
                if attribute is None:
                    raise ValueError(f"unmapped threshold attribute: {name}")
                if not isinstance(required, int):
                    raise ValueError(f"non-integer threshold in source row {source_row}")
                requirements.append({"attribute": attribute, "required_rating": required})
            if not requirements:
                continue
            groups.append(
                {
                    "position": row["Position_Short"],
                    "archetype": row["Archetype"],
                    "ability": row["Ability"],
                    "tier": tier,
                    "requirements": requirements,
                    "ovr_requirement": None,
                    "ability_slot_requirement": None,
                    "source_id": snapshot["source_id"],
                    "source": snapshot["source"],
                    "source_row": source_row,
                    "validation": "SINGLE_STRUCTURED_SOURCE",
                }
            )
    return groups


def source_discovery(snapshot: dict) -> dict:
    return {
        "sources": [
            {
                "source_id": snapshot["source_id"],
                "name": "CFB Labs CFB27 Ability Requirements",
                "numeric_threshold_records": True,
                "source_rows": len(snapshot["records"]),
                "access": "ORDINARY_PUBLIC_PAGE_STRUCTURED_PAYLOAD",
                "validation_role": "SINGLE_STRUCTURED_SOURCE",
            },
            {
                "source_id": "EA-CFB27-UPGRADE-DOC",
                "name": "EA CFB27 Ultimate Team Deep Dive",
                "numeric_threshold_records": False,
                "validation_role": "PRIMARY_ARCHITECTURE_ONLY",
            },
            {
                "source_id": "TEAMCRAFTERS-CFB27-ABILITIES",
                "name": "TeamCrafters CFB27 Ability Catalog",
                "numeric_threshold_records": False,
                "validation_role": "ABILITY_EXISTENCE_CROSS_CHECK_ONLY",
            },
            {
                "source_id": "COLLEGEFOOTBALL-GG",
                "name": "CollegeFootball.gg public ability pages",
                "numeric_threshold_records": False,
                "validation_role": "CFB26_ONLY_NOT_CFB27_THRESHOLD_VALIDATION",
            },
            {
                "source_id": "CFB-FAN-CARD-ABILITIES",
                "name": "CFB.FAN card-specific ability panels",
                "numeric_threshold_records": True,
                "validation_role": (
                    "CARD_POSITION_SPECIFIC_CROSS_CHECK; NO MATCHING POSITION-ARCHETYPE "
                    "RECORD VALIDATED"
                ),
            },
        ],
        "numeric_cross_source_validation_available": False,
        "access_bypass": False,
    }


def ability_catalog(groups: list[dict], snapshot: dict) -> dict:
    combos = {(row["position"], row["archetype"]) for row in groups}
    return {
        "source_rows": len(snapshot["records"]),
        "tier_requirement_groups": len(groups),
        "attribute_constraints": sum(len(row["requirements"]) for row in groups),
        "positions": sorted({row["position"] for row in groups}),
        "position_count": len({row["position"] for row in groups}),
        "position_archetype_count": len(combos),
        "archetypes": sorted({row["archetype"] for row in groups}),
        "abilities": sorted({row["ability"] for row in groups}),
        "ability_count": len({row["ability"] for row in groups}),
        "tiers": list(TIERS),
        "source_claimed_rows": snapshot.get("source_record_count_claimed", 170),
        "source_row_coverage": round(
            len(snapshot["records"]) / snapshot.get("source_record_count_claimed", 170), 6
        ),
    }


def cross_source_validation(groups: list[dict]) -> dict:
    conflicting = {
        (row["position"], row["archetype"], row["ability"], row["tier"])
        for row in CFB_FAN_CROSS_CHECKS
    }
    return {
        "counts": {
            "PRIMARY_CONFIRMED": 0,
            "MULTI_SOURCE_CONFIRMED": 0,
            "SINGLE_STRUCTURED_SOURCE": sum(
                (row["position"], row["archetype"], row["ability"], row["tier"]) not in conflicting
                for row in groups
            ),
            "COMMUNITY_ONLY": 0,
            "CONFLICT": len(CFB_FAN_CROSS_CHECKS),
            "UNRESOLVED": 0,
        },
        "conflicts": CFB_FAN_CROSS_CHECKS,
        "domain_interchangeability_proven": False,
        "cut_equip_availability_claimed_from_cfb_labs": False,
    }


def unlock_centrality(groups: list[dict]) -> dict:
    rows = [(group, requirement) for group in groups for requirement in group["requirements"]]

    def summarize(selected) -> list[dict]:
        buckets = defaultdict(
            lambda: {"abilities": set(), "tiers": 0, "positions": set(), "archetypes": set()}
        )
        for group, requirement in selected:
            item = buckets[requirement["attribute"]]
            item["abilities"].add(group["ability"])
            item["tiers"] += 1
            item["positions"].add(group["position"])
            item["archetypes"].add((group["position"], group["archetype"]))
        return sorted(
            (
                {
                    "attribute": attribute,
                    "abilities_gated": len(item["abilities"]),
                    "tiers_gated": item["tiers"],
                    "positions_affected": len(item["positions"]),
                    "archetypes_affected": len(item["archetypes"]),
                }
                for attribute, item in buckets.items()
            ),
            key=lambda row: (-row["tiers_gated"], -row["abilities_gated"], row["attribute"]),
        )

    positions = sorted({group["position"] for group in groups})
    archetypes = sorted({(group["position"], group["archetype"]) for group in groups})
    return {
        "global": summarize(rows),
        "by_position": {
            position: summarize(row for row in rows if row[0]["position"] == position)
            for position in positions
        },
        "by_archetype": {
            f"{position}::{archetype}": summarize(
                row
                for row in rows
                if row[0]["position"] == position and row[0]["archetype"] == archetype
            )
            for position, archetype in archetypes
        },
        "interpretation": "UNLOCK_CENTRALITY_NOT_GAMEPLAY_VALUE",
    }


def threshold_distributions(groups: list[dict]) -> dict:
    values = defaultdict(list)
    tier_values = defaultdict(lambda: defaultdict(list))
    leverage = Counter()
    for group in groups:
        for requirement in group["requirements"]:
            attribute = requirement["attribute"]
            rating = requirement["required_rating"]
            values[attribute].append(rating)
            tier_values[attribute][group["tier"]].append(rating)
            leverage[(attribute, rating)] += 1
    return {
        "attributes": {
            attribute: {
                "count": len(ratings),
                "minimum": min(ratings),
                "median": statistics.median(ratings),
                "maximum": max(ratings),
                "by_tier": {
                    tier: {
                        "minimum": min(tier_values[attribute][tier]),
                        "median": statistics.median(tier_values[attribute][tier]),
                        "maximum": max(tier_values[attribute][tier]),
                    }
                    for tier in TIERS
                    if tier_values[attribute][tier]
                },
            }
            for attribute, ratings in sorted(values.items())
        },
        "high_leverage_ratings": [
            {"attribute": key[0], "rating": key[1], "tier_constraints": count}
            for key, count in sorted(leverage.items(), key=lambda item: (-item[1], item[0]))[:25]
        ],
    }


def _card_position(card: dict) -> str:
    source_position = card.get("metadata", {}).get("source_position")
    if source_position:
        return source_position
    return POSITION_EQUIVALENTS.get(card["position"], card["position"])


def card_proximity(cards: list[dict], groups: list[dict]) -> dict:
    index = defaultdict(list)
    for group in groups:
        index[(group["position"], group["archetype"].casefold())].append(group)
    observations = []
    card_summaries = []
    counts = Counter()
    for card in sorted(cards, key=lambda row: row["external_card_id"]):
        matches = index.get((_card_position(card), card["archetype"].casefold()), [])
        if not matches:
            counts["NOT_APPLICABLE"] += 1
            card_summaries.append(
                {"card_id": card["external_card_id"], "status": "NOT_APPLICABLE", "thresholds": 0}
            )
            continue
        usable = 0
        for group in matches:
            missing = [
                req["attribute"]
                for req in group["requirements"]
                if req["attribute"] not in card["displayed_ratings"]
            ]
            if missing:
                observations.append(
                    {
                        "card_id": card["external_card_id"],
                        **group,
                        "status": "INSUFFICIENT_REQUIREMENTS",
                        "missing_attributes": missing,
                    }
                )
                continue
            usable += 1
            deficits = {
                req["attribute"]: req["required_rating"]
                - card["displayed_ratings"][req["attribute"]]
                for req in group["requirements"]
            }
            maximum = max(deficits.values())
            if maximum <= 0:
                status = "AT_THRESHOLD" if 0 in deficits.values() else "ABOVE"
            elif maximum == 1:
                status = "1_BELOW"
            elif maximum == 2:
                status = "2_BELOW"
            elif maximum == 3:
                status = "3_BELOW"
            elif maximum <= 5:
                status = "4_TO_5_BELOW"
            else:
                status = "MORE_THAN_5_BELOW"
            counts[status] += 1
            observations.append(
                {
                    "card_id": card["external_card_id"],
                    "player": card["player_name"],
                    "overall": card["overall"],
                    "program": card["program"],
                    "release_date": card["release_date"],
                    "special": is_special(card),
                    **group,
                    "deficits": deficits,
                    "status": status,
                    "equip_eligibility_claimed": False,
                }
            )
        card_summaries.append(
            {
                "card_id": card["external_card_id"],
                "status": "EVALUATED" if usable else "INSUFFICIENT_REQUIREMENTS",
                "thresholds": usable,
            }
        )
    leverage = defaultdict(lambda: {"plus_1": [], "plus_2": []})
    for row in observations:
        if row["status"] not in {"1_BELOW", "2_BELOW"}:
            continue
        positive = [attribute for attribute, deficit in row["deficits"].items() if deficit > 0]
        if len(positive) == 1:
            key = f"{row['card_id']}::{positive[0]}"
            leverage[key]["plus_1" if row["status"] == "1_BELOW" else "plus_2"].append(
                f"{row['ability']}::{row['tier']}"
            )
    multi = sorted(
        (
            {
                "card_id": key.split("::")[0],
                "attribute": key.split("::")[1],
                "plus_1_unlocks": len(value["plus_1"]),
                "plus_2_unlocks": len(value["plus_2"]),
                "thresholds": value,
            }
            for key, value in leverage.items()
            if len(value["plus_1"]) + len(value["plus_2"]) > 1
        ),
        key=lambda row: (
            -(row["plus_1_unlocks"] + row["plus_2_unlocks"]),
            row["card_id"],
            row["attribute"],
        ),
    )
    return {
        "cards_evaluated": len(cards),
        "card_summaries": card_summaries,
        "observations": observations,
        "counts": dict(sorted(counts.items())),
        "multi_unlock_candidates": multi,
    }


def spline_analysis(root: Path) -> dict:
    path = root / "data/external/ea_schema_inventory/C27_inventory.json.gz"
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        inventory = json.load(stream)
    tables = {table["name"]: table for table in inventory["tables"]}
    tunable = tables["AbilityProgressionTunable"]
    spline = tables["Spline"]
    direct = [
        {
            "source_table": tunable["name"],
            "field": field["name"],
            "field_type": field["type"],
            "target_table": "Spline",
            "evidence": "EXPLICIT_FIELD_TYPE",
        }
        for field in tunable["fields"]
        if field["type"] == "Spline"
    ]
    all_refs = [
        {"table": table["name"], "field": field["name"], "type": field["type"]}
        for table in inventory["tables"]
        for field in table["fields"]
        if field["type"].removesuffix("[]") == "Spline"
    ]
    return {
        "ability_progression_tunable": tunable,
        "spline_definition": spline,
        "direct_reference_edges": direct,
        "all_cfb27_spline_references": all_refs,
        "all_cfb27_spline_reference_count": len(all_refs),
        "row_data_status": "ROW_DATA_UNAVAILABLE",
        "height_semantics": "UNKNOWN",
        "weight_semantics": "UNKNOWN",
        "upgrade_cost_semantics": "UNKNOWN_BEYOND_FIELD_NAME",
        "safe_structural_finding": (
            "Each named field is a Spline with CalculateY and integer X/Y arrays."
        ),
    }


def case_maps(cards: list[dict], groups: list[dict], proximity: dict) -> dict:
    by_card = defaultdict(list)
    for row in proximity["observations"]:
        by_card[row["card_id"]].append(row)
    seau_cards = [card for card in cards if card["player_name"] == "Junior Seau"]
    seau = {
        "cards": [
            {
                "card_id": card["external_card_id"],
                "overall": card["overall"],
                "archetype": card["archetype"],
                "ratings": card["displayed_ratings"],
                "thresholds": by_card[card["external_card_id"]],
            }
            for card in sorted(seau_cards, key=lambda row: row["overall"])
        ],
        "known_progression_states": [81, 84, 86, 87],
        "validated_vectors_available": [86, 87],
        "missing_states": [81, 84],
        "final_ratings_inferred": False,
    }
    te = {}
    for archetype in (
        "Vertical Threat",
        "Physical Route Runner",
        "Gritty Possession",
        "Pure Blocker",
        "Pure Possession",
    ):
        te[archetype] = {
            "ability_tier_groups": sum(
                1
                for group in groups
                if group["position"] == "TE" and group["archetype"] == archetype
            ),
            "cards": sum(
                1 for card in cards if card["position"] == "TE" and card["archetype"] == archetype
            ),
            "inheritance_status": (
                "RANKING_INHERITANCE_STRONG"
                if archetype in {"Vertical Threat", "Physical Route Runner"}
                else "ARCHITECTURE_ONLY"
                if archetype == "Gritty Possession"
                else "NO_HISTORICAL_RANKING_RESULT"
            ),
        }
    return {"seau": seau, "te": te}


def progression_reconstruction(root: Path, groups: list[dict]) -> dict:
    chains = _json(root / "data/research/progression_audit/confirmed_progression_chains.json")
    inventory = _json(root / "data/research/progression_audit/progression_inventory.json")
    candidates = inventory["progression_candidates"]
    threshold_attributes = {req["attribute"] for group in groups for req in group["requirements"]}
    frequencies = Counter()
    transitions = []
    for candidate in candidates:
        changes = candidate.get("attribute_changes") or candidate.get("attribute_deltas") or {}
        observed_positive = (
            sorted(
                attribute
                for attribute, value in changes.items()
                if isinstance(value, (int, float)) and value > 0
            )
            if isinstance(changes, dict)
            else []
        )
        confirmed = candidate.get("classification") == "CONFIRMED_PROGRESSION"
        selected = observed_positive if confirmed else []
        for attribute in selected:
            frequencies[(candidate.get("position", "UNKNOWN"), attribute)] += 1
        transitions.append(
            {
                "lower_card_id": candidate.get("lower_card_id"),
                "upper_card_id": candidate.get("upper_card_id"),
                "position": candidate.get("position"),
                "classification": candidate.get("classification"),
                "observed_positive_deltas": observed_positive,
                "selected_attributes": selected,
                "threshold_relevant": [
                    attribute for attribute in selected if attribute in threshold_attributes
                ],
                "path_label": None,
                "missing_changes_are_zero": False,
            }
        )
    return {
        "chains": chains,
        "transitions": transitions,
        "selection_frequency": [
            {"position": key[0], "attribute": key[1], "observations": value}
            for key, value in sorted(frequencies.items(), key=lambda item: (-item[1], item[0]))
        ],
        "path_membership": "INSUFFICIENT_PATH_LABELED_REPLICATION",
        "path_overlap": "INSUFFICIENT_PATH_LABELED_REPLICATION",
        "path_caps": "NO_REPEATED_BOUNDARY_EVIDENCE",
        "cost_benefit": "UPGRADE_COSTS_UNAVAILABLE",
    }


def capability_chronology(cards: list[dict], proximity: dict) -> dict:
    card_map = {card["external_card_id"]: card for card in cards}
    first = {}
    for row in proximity["observations"]:
        if row["status"] not in {"AT_THRESHOLD", "ABOVE"}:
            continue
        card = card_map[row["card_id"]]
        release = _parse_release_date(card["release_date"]).date().isoformat()
        key = (row["position"], row["archetype"], row["ability"], row["tier"])
        candidate = {
            "position": key[0],
            "archetype": key[1],
            "ability": key[2],
            "tier": key[3],
            "date": release,
            "card_id": row["card_id"],
            "overall": card["overall"],
        }
        if key not in first or (release, row["card_id"]) < (
            first[key]["date"],
            first[key]["card_id"],
        ):
            first[key] = candidate
    by_date = defaultdict(list)
    for row in first.values():
        by_date[row["date"]].append(row)
    return {
        "first_access": sorted(
            first.values(),
            key=lambda row: (
                row["date"],
                row["position"],
                row["archetype"],
                row["ability"],
                row["tier"],
            ),
        ),
        "by_release_date": {
            date: sorted(rows, key=lambda row: tuple(row.values()))
            for date, rows in sorted(by_date.items())
        },
    }


def special_targeting(proximity: dict) -> dict:
    cells = defaultdict(lambda: {"ordinary": Counter(), "special": Counter()})
    for row in proximity["observations"]:
        if row["status"] == "INSUFFICIENT_REQUIREMENTS":
            continue
        month = (
            _parse_release_date(row["release_date"]).strftime("%Y-%m")
            if row.get("release_date")
            else "UNKNOWN"
        )
        key = (row["position"], row["archetype"], row["overall"], month)
        group = "special" if row["special"] else "ordinary"
        cells[key][group][row["status"]] += 1
    matched = [
        {
            "position": key[0],
            "archetype": key[1],
            "overall": key[2],
            "release_period": key[3],
            "ordinary": dict(value["ordinary"]),
            "special": dict(value["special"]),
        }
        for key, value in sorted(cells.items())
        if value["ordinary"] and value["special"]
    ]
    return {
        "matched_cells": matched,
        "matched_cell_count": len(matched),
        "classification": "DESCRIPTIVE" if matched else "INSUFFICIENT_MATCHED_CONTROLS",
        "intent_claimed": False,
    }


def program_signatures(proximity: dict) -> list[dict]:
    buckets = defaultdict(Counter)
    for row in proximity["observations"]:
        if row.get("program") and row["status"] in {"AT_THRESHOLD", "ABOVE"}:
            buckets[row["program"]][f"{row['position']}::{row['ability']}::{row['tier']}"] += 1
    return [
        {
            "program": program,
            "capabilities": dict(counts.most_common()),
            "causal_program_design_claimed": False,
        }
        for program, counts in sorted(buckets.items())
    ]


def ea_design_signals(groups: list[dict], proximity: dict) -> list[dict]:
    tier_counts = Counter(
        requirement["attribute"] for group in groups for requirement in group["requirements"]
    )
    near_counts = Counter()
    special_near = Counter()
    for row in proximity["observations"]:
        if row["status"] not in {"AT_THRESHOLD", "1_BELOW", "2_BELOW"}:
            continue
        for attribute in row.get("deficits", {}):
            near_counts[attribute] += 1
            special_near[attribute] += bool(row.get("special"))
    signals = []
    for attribute in sorted(tier_counts):
        evidence = tier_counts[attribute] + near_counts[attribute]
        classification = (
            "STRONG_EA_DESIGN_SIGNAL"
            if evidence >= 100
            else "MODERATE"
            if evidence >= 40
            else "WEAK"
            if evidence >= 10
            else "INSUFFICIENT"
        )
        signals.append(
            {
                "attribute": attribute,
                "tier_constraints": tier_counts[attribute],
                "near_threshold_card_observations": near_counts[attribute],
                "special_near_observations": special_near[attribute],
                "classification": classification,
                "gameplay_proof": False,
            }
        )
    return sorted(
        signals,
        key=lambda row: (
            -(row["tier_constraints"] + row["near_threshold_card_observations"]),
            row["attribute"],
        ),
    )


def ovr_capability_comparison(cards: list[dict], chronology: dict) -> dict:
    by_position = defaultdict(list)
    for card in cards:
        by_position[_card_position(card)].append(card)
    ceiling_events = []
    ceilings_before = {}
    for position, position_cards in sorted(by_position.items()):
        ceiling = -1
        for card in sorted(
            position_cards,
            key=lambda row: (
                _parse_release_date(row["release_date"]).date(),
                row["external_card_id"],
            ),
        ):
            release = _parse_release_date(card["release_date"]).date().isoformat()
            ceilings_before[(position, release)] = ceiling
            if card["overall"] > ceiling:
                ceiling = card["overall"]
                ceiling_events.append(
                    {
                        "position": position,
                        "date": release,
                        "new_ceiling": ceiling,
                        "card_id": card["external_card_id"],
                    }
                )
    capability_without_higher_ovr = []
    for row in chronology["first_access"]:
        previous = ceilings_before.get((row["position"], row["date"]), -1)
        if previous >= row["overall"]:
            capability_without_higher_ovr.append({**row, "prior_position_ceiling": previous})
    return {
        "ovr_ceiling_events": ceiling_events,
        "capability_first_access_events": len(chronology["first_access"]),
        "capability_without_ovr_increase": capability_without_higher_ovr,
        "finding": (
            "Observed capability can advance without a new position OVR ceiling."
            if capability_without_higher_ovr
            else "No such event is demonstrated in compatible covered cards."
        ),
    }


def chatgpt_targets() -> list[dict]:
    topics = [
        (
            "Validate CFB27 numeric thresholds from an independent source",
            "all 680 groups remain single-source",
        ),
        (
            "Test Seau Lurker ability effects",
            "threshold access alone does not measure defensive impact",
        ),
        ("Recover Seau 81 and 84 rating panels", "two progression states lack validated vectors"),
        ("Identify HeightModifierSpline rows", "schema shape cannot reveal curve values"),
        ("Identify WeightModifierSpline rows", "physical effects remain unknown"),
        ("Identify UpgradeCostSpline rows", "cost-benefit cannot be computed without X/Y points"),
        (
            "Verify multi-attribute threshold AND semantics",
            "grouped requirements are source-structured but not gameplay-tested",
        ),
        ("Verify ability-slot OVR gates", "numeric source provides no slot requirements"),
        (
            "Evaluate VT TE threshold abilities",
            "strong OVR ranking does not establish ability value",
        ),
        (
            "Evaluate PRR TE threshold abilities",
            "perfect historical ranking needs gameplay interpretation",
        ),
        (
            "Evaluate Gritty TE threshold abilities",
            "historical coefficients remain non-exceptional",
        ),
        ("Evaluate Pure Blocker TE ability value", "no historical ranking result exists"),
        ("Measure MIKE speed versus coverage thresholds", "GM tradeoffs require gameplay evidence"),
        (
            "Test BSH threshold effects for MIKE",
            "construction signal is not shed-performance proof",
        ),
        ("Price threshold-crossing cards", "market-value evidence is absent"),
        ("Validate special-card threshold targeting", "matched cells are descriptive, not causal"),
        (
            "Confirm capability-without-OVR replacement behavior",
            "chronology suggests non-OVR replacement events",
        ),
        (
            "Recover path-labeled progression screenshots",
            "rating-group membership lacks replicated labels",
        ),
        ("Recover repeated path-cap boundaries", "single stopped upgrades cannot establish caps"),
        (
            "Prospectively score post-cutoff releases",
            "all current models remain frozen at the Phase V cutoff",
        ),
    ]
    return [{"question": question, "why": why} for question, why in topics]


def replacement_pressure_v3(root: Path, cards: list[dict], chronology: dict, catalog: dict) -> dict:
    phase4 = _json(root / "data/research/cfb27_inheritance_phase4/release_intelligence.json")[
        "replacement_pressure"
    ]
    latest = max(
        _parse_release_date(card["release_date"]).date()
        for card in cards
        if card.get("release_date")
    )
    last_capability = {}
    for row in chronology["first_access"]:
        date = datetime.fromisoformat(row["date"]).date()
        last_capability[row["position"]] = max(date, last_capability.get(row["position"], date))
    results = {}
    covered_positions = set(catalog["positions"])
    for position, base in sorted(phase4.items()):
        normalized = POSITION_EQUIVALENTS.get(position, position)
        capability_date = last_capability.get(normalized)
        gap = normalized not in covered_positions
        days = (latest - capability_date).days if capability_date else None
        if gap:
            pressure = "NORMAL"
        elif base["pressure"] == "ELEVATED" and days is not None and days >= 14:
            pressure = "HIGH"
        elif base["pressure"] == "ELEVATED":
            pressure = "ELEVATED"
        elif base["pressure"] == "LOWER":
            pressure = "LOW"
        else:
            pressure = "NORMAL"
        results[position] = {
            "pressure": pressure,
            "ovr_ceiling": base["current_ceiling"],
            "days_since_ceiling_change": base["days_since_ceiling_change"],
            "days_since_first_observed_latest_capability": days,
            "threshold_position_coverage": not gap,
            "archetype_coverage": base["archetype_coverage"],
            "release_count": base["release_count"],
            "prediction_claimed": False,
        }
    return results


def gm_layers(cards: list[dict], proximity: dict, pressure: dict) -> dict:
    by_card = defaultdict(list)
    for row in proximity["observations"]:
        if row["status"] in {"AT_THRESHOLD", "ABOVE", "1_BELOW", "2_BELOW"}:
            by_card[row["card_id"]].append(
                {
                    "ability": row["ability"],
                    "tier": row["tier"],
                    "status": row["status"],
                    "deficits": row.get("deficits"),
                }
            )
    ability = []
    replacement = []
    for card in sorted(cards, key=lambda row: row["external_card_id"]):
        ability.append(
            {
                "card_id": card["external_card_id"],
                "threshold_evidence": by_card[card["external_card_id"]],
                "source_confidence": "SINGLE_STRUCTURED_SOURCE",
                "actual_equip_availability_claimed": False,
                "gameplay_value_claimed": False,
            }
        )
        replacement.append(
            {
                "card_id": card["external_card_id"],
                "position": card["position"],
                "archetype": card["archetype"],
                "position_pressure": pressure.get(card["position"], {}).get("pressure"),
                "capability_gap": not bool(by_card[card["external_card_id"]]),
            }
        )
    return {"ability": ability, "replacement": replacement}


def freeze_inputs(root: Path, cards: list[dict]) -> dict:
    paths = [
        root / "data/external/cfb_fan_population_state.json",
        root / "data/external/cfb27_ability_thresholds.json",
        root / "data/research/cfb27_inheritance_phase5/phase5_frozen_snapshot.json",
        root / "data/research/progression_audit/progression_inventory.json",
        root / "data/research/cfb27_inheritance_phase5/related_table_graph.json",
        root / "data/research/cfb27_inheritance_phase4/release_intelligence.json",
        root / "data/research/cfb27_inheritance_phase5/prospective_validation_ledger.json",
        root / "data/research/cfb27_inheritance_phase5/te_moneyball_matrix.json",
    ]
    return {
        "source_commit": "8555000",
        "population_n": len(cards),
        "input_sha256": {
            path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in paths
        },
        "no_retrospective_leakage": True,
    }


def build_phase6_10(root: Path) -> dict:
    snapshot = _json(root / "data/external/cfb27_ability_thresholds.json")
    state = _json(root / "data/external/cfb_fan_population_state.json")
    cards = list(state["cards"].values())
    constraints = normalize_thresholds(snapshot)
    groups = grouped_thresholds(snapshot)
    catalog = ability_catalog(groups, snapshot)
    proximity = card_proximity(cards, groups)
    chronology = capability_chronology(cards, proximity)
    pressure = replacement_pressure_v3(root, cards, chronology, catalog)
    layers = gm_layers(cards, proximity, pressure)
    return {
        "frozen_input": freeze_inputs(root, cards),
        "source_discovery": source_discovery(snapshot),
        "ability_catalog": catalog,
        "threshold_constraints": constraints,
        "threshold_groups": groups,
        "validation": cross_source_validation(groups),
        "unlock_centrality": unlock_centrality(groups),
        "threshold_distributions": threshold_distributions(groups),
        "card_proximity": proximity,
        "case_maps": case_maps(cards, groups, proximity),
        "splines": spline_analysis(root),
        "physical_dimensions": {
            "status": "UNAVAILABLE_IN_CUT_POPULATION",
            "correlation_claimed": False,
            "spline_mechanics_inferred": False,
        },
        "progression": progression_reconstruction(root, groups),
        "special_threshold_targeting": special_targeting(proximity),
        "capability_chronology": chronology,
        "program_capability_signatures": program_signatures(proximity),
        "ea_design_signals": ea_design_signals(groups, proximity),
        "ovr_capability_comparison": ovr_capability_comparison(cards, chronology),
        "replacement_pressure_v3": pressure,
        "position_capability_gaps": sorted(
            position for position, row in pressure.items() if not row["threshold_position_coverage"]
        ),
        "prospective": {
            "new_cards": 0,
            "te_results": [],
            "center_results": [],
            "refit": False,
            "public_listing_checked": "https://cfb.fan/players/",
            "latest_untracked_card_inspected": {
                "player": "Justin Okoronkwo",
                "overall": 90,
                "position": "SAM",
                "date_added": "2026-08-01",
                "after_phase5_cutoff": False,
            },
        },
        "gm_ability_layer": layers["ability"],
        "gm_replacement_layer": layers["replacement"],
        "moneyball": {
            "ability_leverage_added": True,
            "gameplay_value": None,
            "market_value": None,
            "ea_design_signal_is_gameplay_proof": False,
        },
        "chatgpt_targets": chatgpt_targets(),
        "data_validation": {
            "guessed_values": False,
            "leakage": False,
            "access_bypass": False,
            "unsupported_spline_claims": False,
            "conflicts_preserved": True,
            "canonical_modified": False,
        },
    }


def write_artifacts(output: Path, analysis: dict) -> None:
    output.mkdir(parents=True, exist_ok=True)
    names = {
        "phase6_10_frozen_snapshot.json": "frozen_input",
        "ability_source_discovery.json": "source_discovery",
        "ability_catalog.json": "ability_catalog",
        "ability_threshold_constraints.json": "threshold_constraints",
        "ability_threshold_groups.json": "threshold_groups",
        "cross_source_validation.json": "validation",
        "unlock_centrality.json": "unlock_centrality",
        "threshold_distributions.json": "threshold_distributions",
        "card_threshold_proximity.json": "card_proximity",
        "position_case_maps.json": "case_maps",
        "cfb27_spline_analysis.json": "splines",
        "physical_dimension_analysis.json": "physical_dimensions",
        "progression_path_reconstruction.json": "progression",
        "special_threshold_targeting.json": "special_threshold_targeting",
        "capability_chronology.json": "capability_chronology",
        "program_capability_signatures.json": "program_capability_signatures",
        "ea_design_signals.json": "ea_design_signals",
        "ovr_capability_creep_comparison.json": "ovr_capability_comparison",
        "replacement_pressure_v3.json": "replacement_pressure_v3",
        "position_capability_gaps.json": "position_capability_gaps",
        "prospective_validation.json": "prospective",
        "gm_ability_layer.json": "gm_ability_layer",
        "gm_replacement_layer.json": "gm_replacement_layer",
        "moneyball_ability_crosswalk.json": "moneyball",
        "chatgpt_research_targets.json": "chatgpt_targets",
        "phase6_10_summary.json": None,
    }
    for filename, key in names.items():
        payload = analysis if key is None else analysis[key]
        (output / filename).write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
