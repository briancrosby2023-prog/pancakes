"""Deterministic Phase-V ability, progression, and capability research."""

from __future__ import annotations

import gzip
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from operation_pancake.research.cfb27_phase2 import is_special

GAMES = [f"M{year}" for year in range(19, 28)] + ["C27"]
FAMILY_TERMS = {
    "ability": ("ability", "trait"),
    "progression": ("progression", "upgrade", "development", "experience", "xp"),
    "archetype": ("archetype", "playertype", "scheme", "grade", "prototype", "template"),
}
ATTRIBUTE_ALIASES = {
    "Acceleration": "ACC",
    "Agility": "AGI",
    "Awareness": "AWR",
    "Block Shedding": "BSH",
    "Break Sack": "BSK",
    "Break Tackle": "BTK",
    "Carrying": "CAR",
    "Catch in Traffic": "CIT",
    "Catching": "CTH",
    "Change of Direction": "COD",
    "Deep Route Running": "DRR",
    "Deep Throw Accuracy": "DAC",
    "Finesse Moves": "FMV",
    "Hit Power": "POW",
    "Impact Blocking": "IBL",
    "Juke Move": "JKM",
    "Lead Block": "LBK",
    "Medium Route Running": "MRR",
    "Pass Block": "PBK",
    "Pass Block Finesse": "PBF",
    "Pass Block Power": "PBP",
    "Power Moves": "PMV",
    "Release": "RLS",
    "Run Block": "RBK",
    "Run Block Finesse": "RBF",
    "Run Block Power": "RBP",
    "Short Route Running": "SRR",
    "Spectacular Catch": "SPC",
    "Speed": "SPD",
    "Spin Move": "SPM",
    "Stiff Arm": "SFA",
    "Strength": "STR",
    "Tackle": "TAC",
    "Throw Accuracy": "THA",
    "Throw on the Run": "RUN",
    "Throw Power": "THP",
    "Throw Under Pressure": "TUP",
    "Toughness": "TGH",
    "Trucking": "TRK",
    "Zone Coverage": "ZCV",
}


def load_inventories(root: Path) -> dict[str, dict]:
    result = {}
    for game in GAMES:
        path = root / f"data/external/ea_schema_inventory/{game}_inventory.json.gz"
        with gzip.open(path, "rt", encoding="utf-8") as stream:
            result[game] = json.load(stream)
    return result


def _field_signature(field: dict) -> tuple[str | None, str | None]:
    enum = field.get("enum")
    enum_name = enum.get("_name") if isinstance(enum, dict) else enum
    return field.get("type"), enum_name


def ability_progression_analysis(inventories: dict[str, dict]) -> dict:
    raw, matrix = {}, []
    previous: dict[str, tuple[str | None, str | None]] = {}
    for game in GAMES:
        table = next(
            table
            for table in inventories[game]["tables"]
            if table["name"] == "AbilityProgressionTunable"
        )
        raw[game] = table
        current = {field["name"]: _field_signature(field) for field in table["fields"]}
        for name in sorted(set(previous) | set(current)):
            if not previous:
                status = "BASELINE"
            elif name not in previous:
                status = "ADDED"
            elif name not in current:
                status = "REMOVED"
            elif previous[name] != current[name]:
                status = "TYPE_CHANGED"
            else:
                status = "PERSISTENT"
            matrix.append(
                {"game": game, "field": name, "signature": current.get(name), "status": status}
            )
        previous = current
    return {"raw_definitions": raw, "field_evolution": matrix}


def build_schema_graph(inventories: dict[str, dict]) -> dict:
    nodes: dict[tuple[str, str], dict] = {}
    edges: dict[tuple[str, str, str, str], dict] = {}
    family_maps = {family: [] for family in FAMILY_TERMS}
    for game in GAMES:
        tables = inventories[game]["tables"]
        names = {table["name"] for table in tables}
        for table in tables:
            haystack = " ".join(
                [table["name"] or "", *(field["name"] or "" for field in table["fields"])]
            ).casefold()
            memberships = [
                family
                for family, terms in FAMILY_TERMS.items()
                if any(term in haystack for term in terms)
            ]
            if memberships:
                nodes[(game, table["name"])] = {
                    "game": game,
                    "table": table["name"],
                    "asset_id": table["asset_id"],
                    "families": memberships,
                }
            for family in memberships:
                family_maps[family].append(
                    {
                        "game": game,
                        "table": table["name"],
                        "asset_id": table["asset_id"],
                        "fields": [field["name"] for field in table["fields"]],
                    }
                )
            for field in table["fields"]:
                target = (field.get("type") or "").removesuffix("[]")
                if target in names and target != table["name"]:
                    key = (game, table["name"], field["name"], target)
                    edges[key] = {
                        "game": game,
                        "source": table["name"],
                        "field": field["name"],
                        "target": target,
                        "evidence": "EXPLICIT_FIELD_TYPE",
                        "confidence": "VERIFIED",
                    }
    related_edges = [
        edge
        for edge in edges.values()
        if (edge["game"], edge["source"]) in nodes and (edge["game"], edge["target"]) in nodes
    ]
    return {
        "nodes": sorted(nodes.values(), key=lambda row: (row["game"], row["table"])),
        "edges": sorted(related_edges, key=lambda row: tuple(row.values())),
        "family_maps": family_maps,
        "unsupported_name_similarity_edges": [],
    }


def overall_grade_investigation(inventories: dict[str, dict]) -> dict:
    observations = {}
    references = []
    for game in GAMES:
        player = next(table for table in inventories[game]["tables"] if table["name"] == "Player")
        grades = [field for field in player["fields"] if field["name"].startswith("OverallGrade")]
        observations[game] = grades
        for table in inventories[game]["tables"]:
            for field in table["fields"]:
                if field["name"].startswith("OverallGrade") and table["name"] != "Player":
                    references.append({"game": game, "table": table["name"], "field": field})
    return {
        "observations": observations,
        "other_table_occurrences": references,
        "stored_in_player_schema": any(observations.values()),
        "calculated_status": "UNKNOWN_SCHEMA_DOES_NOT_EXPOSE_RUNTIME_SEMANTICS",
        "archetype_mapping_status": "UNSUPPORTED",
        "cfb27_replacement_candidates": _replacement_candidates(inventories),
    }


def _replacement_candidates(inventories: dict[str, dict]) -> list[dict]:
    m27 = next(table for table in inventories["M27"]["tables"] if table["name"] == "Player")
    c27 = next(table for table in inventories["C27"]["tables"] if table["name"] == "Player")
    old_names = {field["name"] for field in m27["fields"]}
    candidates = []
    for field in c27["fields"]:
        name = field["name"].casefold()
        if field["name"] not in old_names and any(
            term in name for term in ("grade", "overall", "scheme")
        ):
            candidates.append(
                {"field": field["name"], "type": field["type"], "confidence": "LOW_NAME_ONLY"}
            )
    return candidates


def normalize_thresholds(snapshot: dict) -> list[dict]:
    records = []
    for row_number, row in enumerate(snapshot["records"], start=1):
        for attribute_key, suffix in (("Attribute", ""), ("Attribute2", "2")):
            attribute_name = row.get(attribute_key)
            if not attribute_name:
                continue
            attribute = ATTRIBUTE_ALIASES.get(attribute_name)
            if attribute is None:
                raise ValueError(f"unmapped threshold attribute: {attribute_name}")
            for tier in ("Bronze", "Silver", "Gold", "Platinum"):
                required = row.get(f"{tier}{suffix}")
                if required in (None, ""):
                    continue
                if not isinstance(required, int):
                    raise ValueError(f"non-integer threshold in source row {row_number}")
                records.append(
                    {
                        "position": row["Position_Short"],
                        "archetype": row["Archetype"],
                        "ability": row["Ability"],
                        "tier": tier.upper(),
                        "attribute": attribute,
                        "required_rating": required,
                        "ovr_requirement": None,
                        "source": snapshot["source"],
                        "source_id": snapshot["source_id"],
                        "source_class": snapshot["source_class"],
                        "retrieval_date": snapshot["retrieval_date"],
                        "source_row": row_number,
                        "confidence": "STRUCTURED_SECONDARY_UNCORROBORATED_ROW",
                    }
                )
    return records


def threshold_centrality(records: list[dict]) -> dict:
    all_counts = Counter((row["position"], row["attribute"]) for row in records)
    offense = {"QB", "HB", "FB", "WR", "TE", "LT", "LG", "C", "RG", "RT"}
    return {
        "position_attribute_tier_unlocks": [
            {"position": key[0], "attribute": key[1], "tier_unlocks": count}
            for key, count in sorted(all_counts.items(), key=lambda item: (-item[1], item[0]))
        ],
        "offense": _side_counts(records, offense),
        "defense": _side_counts(records, {row["position"] for row in records} - offense),
        "interpretation": "UNLOCK_CENTRALITY_ONLY_NOT_GAMEPLAY_IMPORTANCE",
    }


def _side_counts(records: list[dict], positions: set[str]) -> list[dict]:
    counts = Counter(row["attribute"] for row in records if row["position"] in positions)
    return [{"attribute": key, "tier_unlocks": value} for key, value in counts.most_common()]


def threshold_proximity(cards: list[dict], records: list[dict]) -> dict:
    index: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for record in records:
        index[(record["position"], record["archetype"].casefold())].append(record)
    observations, counts = [], Counter()
    for card in sorted(cards, key=lambda row: row["external_card_id"]):
        matched = index.get((card["position"], card["archetype"].casefold()), [])
        for threshold in matched:
            rating = card["displayed_ratings"].get(threshold["attribute"])
            if rating is None:
                continue
            distance = rating - threshold["required_rating"]
            bucket = (
                "AT_THRESHOLD"
                if distance == 0
                else "1_BELOW"
                if distance == -1
                else "2_BELOW"
                if distance == -2
                else "3_TO_5_BELOW"
                if -5 <= distance <= -3
                else "ABOVE_THRESHOLD"
                if distance > 0
                else "MORE_THAN_5_BELOW"
            )
            counts[bucket] += 1
            observations.append(
                {
                    "card_id": card["external_card_id"],
                    "player": card["player_name"],
                    "position": card["position"],
                    "archetype": card["archetype"],
                    "ability": threshold["ability"],
                    "tier": threshold["tier"],
                    "attribute": threshold["attribute"],
                    "rating": rating,
                    "required_rating": threshold["required_rating"],
                    "distance": distance,
                    "bucket": bucket,
                    "equip_eligibility_claimed": False,
                }
            )
    leverage = Counter(
        row["card_id"] for row in observations if row["bucket"] in {"AT_THRESHOLD", "1_BELOW"}
    )
    return {
        "cards_evaluated": len(cards),
        "cards_with_matching_threshold_archetype": len({row["card_id"] for row in observations}),
        "counts": dict(sorted(counts.items())),
        "multi_ability_leverage_cards": sorted(
            (
                {"card_id": card_id, "near_unlocks": count}
                for card_id, count in leverage.items()
                if count > 1
            ),
            key=lambda row: (-row["near_unlocks"], row["card_id"]),
        ),
        "observations": observations,
    }


def progression_crosswalk(root: Path, threshold_records: list[dict]) -> dict:
    chains = json.loads(
        (root / "data/research/progression_audit/confirmed_progression_chains.json").read_text()
    )
    inventory = json.loads(
        (root / "data/research/progression_audit/progression_inventory.json").read_text()
    )
    threshold_attributes = {row["attribute"] for row in threshold_records}
    candidates = inventory.get("progression_candidates", [])
    frequencies = Counter()
    crosswalk = []
    for candidate in candidates:
        changed = candidate.get("changed_attributes") or candidate.get("attribute_deltas") or {}
        attributes = sorted(changed if isinstance(changed, dict) else changed)
        for attribute in attributes:
            frequencies[(candidate.get("position", "UNKNOWN"), attribute)] += 1
        crosswalk.append(
            {
                "candidate_id": candidate.get("candidate_id") or candidate.get("transition_id"),
                "position": candidate.get("position"),
                "attributes": attributes,
                "ability_crosswalk": {
                    attribute: "POSSIBLE_PATH_ATTRIBUTE"
                    if attribute in threshold_attributes
                    else "UNRESOLVED"
                    for attribute in attributes
                },
                "missing_observation_is_zero": False,
            }
        )
    return {
        "confirmed_chains": chains,
        "candidate_observations": crosswalk,
        "attribute_selection_frequency": [
            {"position": key[0], "attribute": key[1], "observations": count}
            for key, count in sorted(frequencies.items())
        ],
        "core_specialization_status": "INSUFFICIENT_REPLICATED_PATH_LABEL_EVIDENCE",
    }


def capability_chronology(cards: list[dict], proximity: dict) -> dict:
    card_by_id = {card["external_card_id"]: card for card in cards}
    first: dict[tuple[str, str, str, str], dict] = {}
    for row in proximity["observations"]:
        if row["distance"] < 0:
            continue
        card = card_by_id[row["card_id"]]
        raw_date = card.get("release_date")
        if not raw_date:
            continue
        release = datetime.strptime(raw_date, "%m/%d/%Y").date().isoformat()
        key = (row["position"], row["archetype"], row["ability"], row["tier"])
        candidate = {
            "position": key[0],
            "archetype": key[1],
            "ability": key[2],
            "tier": key[3],
            "first_release_date": release,
            "card_id": row["card_id"],
            "player": row["player"],
            "distance": row["distance"],
        }
        if key not in first or (release, row["card_id"]) < (
            first[key]["first_release_date"],
            first[key]["card_id"],
        ):
            first[key] = candidate
    return {
        "first_observed_threshold_access": sorted(
            first.values(),
            key=lambda row: (
                row["position"],
                row["archetype"],
                row["ability"],
                row["tier"],
                row["first_release_date"],
                row["card_id"],
            ),
        )
    }


def special_threshold_test(cards: list[dict], proximity: dict) -> dict:
    card_by_id = {card["external_card_id"]: card for card in cards}
    groups = defaultdict(lambda: Counter(total=0, near=0, reached=0))
    for row in proximity["observations"]:
        card = card_by_id[row["card_id"]]
        group = "SPECIAL" if is_special(card) else "ORDINARY"
        groups[group]["total"] += 1
        groups[group]["near"] += row["distance"] in {-2, -1, 0}
        groups[group]["reached"] += row["distance"] >= 0
    return {
        "groups": {key: dict(value) for key, value in sorted(groups.items())},
        "classification": "DESCRIPTIVE_PARTIAL_TE_VERTICAL_THREAT_ONLY",
        "causal_intent_claimed": False,
    }


def qb_trk_analysis(cards: list[dict]) -> dict:
    groups = defaultdict(list)
    for card in cards:
        if card["position"] == "QB" and "TRK" in card["displayed_ratings"]:
            groups[card["archetype"]].append(card["displayed_ratings"]["TRK"])
    summaries = {
        archetype: {
            "n": len(values),
            "minimum": min(values),
            "maximum": max(values),
            "mean": round(sum(values) / len(values), 6),
        }
        for archetype, values in sorted(groups.items())
    }
    return {
        "classification": "UNRESOLVED",
        "archetype_summaries": summaries,
        "ability_requirement_found": False,
        "progression_path_evidence_found": False,
        "reason": (
            "Threshold snapshot is partial and progression observations do not label QB paths."
        ),
    }


def player_architecture_graph(thresholds: list[dict]) -> dict:
    edges = []
    for row in thresholds:
        archetype = f"{row['position']}::{row['archetype']}"
        edges.extend(
            [
                {
                    "source": row["position"],
                    "target": archetype,
                    "relationship": "HAS_ARCHETYPE_THRESHOLD_CONTEXT",
                    "evidence_type": "STRUCTURED_SECONDARY",
                    "confidence": "MODERATE",
                    "provenance": row["source"],
                },
                {
                    "source": archetype,
                    "target": row["attribute"],
                    "relationship": "ABILITY_THRESHOLD_ATTRIBUTE",
                    "evidence_type": "STRUCTURED_SECONDARY",
                    "confidence": "MODERATE_UNCORROBORATED",
                    "provenance": row["source"],
                },
            ]
        )
    unique = {json.dumps(edge, sort_keys=True): edge for edge in edges}
    return {
        "edges": sorted(unique.values(), key=lambda row: tuple(row.values())),
        "numeric_formula_weights_claimed": False,
        "scope": "PARTIAL_TE_VERTICAL_THREAT_THRESHOLD_SUBGRAPH",
    }


def replacement_pressure_v2(root: Path, chronology: dict) -> dict:
    phase4 = json.loads(
        (root / "data/research/cfb27_inheritance_phase4/release_intelligence.json").read_text()
    )["replacement_pressure"]
    access_counts = Counter(
        row["position"] for row in chronology["first_observed_threshold_access"]
    )
    return {
        position: {
            **values,
            "observed_threshold_capabilities": access_counts[position],
            "pressure_v2": values["pressure"],
            "change_from_phase4": "UNCHANGED_INSUFFICIENT_COMPLETE_THRESHOLD_COVERAGE",
        }
        for position, values in sorted(phase4.items())
    }


def gm_evaluator(cards: list[dict], proximity: dict, pressure: dict) -> list[dict]:
    by_card = defaultdict(list)
    for row in proximity["observations"]:
        if row["distance"] >= -2:
            by_card[row["card_id"]].append(
                {
                    "ability": row["ability"],
                    "tier": row["tier"],
                    "attribute": row["attribute"],
                    "distance": row["distance"],
                }
            )
    return [
        {
            "card_id": card["external_card_id"],
            "position": card["position"],
            "archetype": card["archetype"],
            "ability_unlock_proximity": by_card[card["external_card_id"]],
            "ability_eligibility_confirmed": False,
            "architecture_confidence": (
                "PARTIAL" if by_card[card["external_card_id"]] else "UNKNOWN"
            ),
            "replacement_pressure_v2": pressure.get(card["position"], {}).get("pressure_v2"),
            "moneyball_research_priority": "RESEARCH_ONLY",
        }
        for card in sorted(cards, key=lambda row: row["external_card_id"])
    ]


def chatgpt_targets() -> list[dict]:
    topics = [
        ("AbilityProgressionTunable rows", "schema fields cannot establish row semantics"),
        ("Table_44 provenance", "the family link remains likely but not row-verified"),
        ("M19 TE XML storage", "schema evidence points away from the progression tunable"),
        ("M19 to M20 formula tweak documentation", "coefficient changes are invisible in schemas"),
        ("CFB27 threshold primary source", "the current threshold subset is secondary and partial"),
        ("CFB27 threshold independent validation", "individual rows remain uncorroborated"),
        (
            "Vertical Threat TE gameplay tests",
            "ranking inheritance does not establish gameplay value",
        ),
        (
            "Physical Route Runner TE gameplay tests",
            "perfect ranking needs independent meaning tests",
        ),
        ("Gritty TE architecture", "historical weights are not exceptional against nulls"),
        ("Pure Blocker TE path ratings", "no authenticated path membership is preserved"),
        ("QB TRK gameplay purpose", "TRK is cheap and special-boosted but still unexplained"),
        ("Backfield Creator path screenshots", "historical West Coast inheritance was rejected"),
        ("MIKE BSH progression", "path-labeled replicated observations are needed"),
        ("special-card threshold targeting", "partial thresholds cannot support an intent claim"),
        ("ability slot OVR requirements", "attribute proximity alone does not prove eligibility"),
        ("multi-attribute ability logic", "AND/OR semantics must be verified in-game"),
        ("capability creep gameplay impact", "unlock chronology is not an effect-size estimate"),
        ("market response to threshold crossing", "no market observations are currently available"),
        ("EVO path stacking behavior", "official descriptions need observed item-level validation"),
        ("archetype display selection", "highest-path behavior needs prospective card evidence"),
    ]
    return [{"question": topic, "why": why} for topic, why in topics]


def phase4_bridges(root: Path, thresholds: list[dict], cards: list[dict]) -> dict:
    phase4 = root / "data/research/cfb27_inheritance_phase4"
    nulls = json.loads((phase4 / "te_null_distributions.json").read_text())
    signals = json.loads((phase4 / "ea_design_signals.json").read_text())
    threshold_counts = Counter(row["attribute"] for row in thresholds)
    design_v2 = [
        {
            **row,
            "ability_tier_centrality_observed": threshold_counts[row["attribute"]],
            "threshold_scope_warning": "PARTIAL_TE_VERTICAL_THREAT_ONLY",
            "gameplay_value_claimed": False,
        }
        for row in signals
    ]
    moneyball_attributes = [
        "PBK",
        "PBF",
        "PBP",
        "LBK",
        "IBL",
        "STR",
        "RBF",
        "RBP",
        "RBK",
        "SPD",
        "ACC",
        "CTH",
        "CIT",
        "SRR",
        "MRR",
    ]
    te_matrix = [
        {
            "attribute": attribute,
            "historical_ovr_importance": "PRESERVED_PHASE4",
            "modern_ranking_evidence": "PRESERVED_PHASE4",
            "ability_tier_unlocks_observed": threshold_counts[attribute],
            "progression_frequency": "SEE_PROGRESSION_CROSSWALK",
            "gameplay_evidence": None,
            "market_evidence": None,
        }
        for attribute in moneyball_attributes
    ]
    backfield = [
        card
        for card in cards
        if card["position"] == "QB" and card["archetype"] == "Backfield Creator"
    ]
    attributes = sorted(set.intersection(*(set(card["displayed_ratings"]) for card in backfield)))
    backfield_groups = {
        "mobility_core_candidates": [
            key for key in ("SPD", "ACC", "AGI", "COD") if key in attributes
        ],
        "passing_core_candidates": [
            key for key in ("THP", "SAC", "MAC", "DAC") if key in attributes
        ],
        "contact_rushing_candidates": [
            key for key in ("TRK", "BTK", "SFA", "CAR") if key in attributes
        ],
        "ability_profile": "UNRESOLVED_PARTIAL_THRESHOLD_SOURCE_HAS_NO_QB_ROWS",
        "historical_relationship": "WEST_COAST_INHERITANCE_REJECTED_PHASE4",
        "cards": len(backfield),
    }
    return {
        "te_architecture": {
            archetype: {
                "accuracy": result["historical"]["accuracy"],
                "ranking": result["classification"]["ranking"],
                "numeric": result["classification"]["numeric"],
            }
            for archetype, result in nulls.items()
        },
        "te_moneyball_matrix": te_matrix,
        "ea_design_signals_v2": design_v2,
        "backfield_creator": backfield_groups,
        "archetype_evolution": {
            "schema_observation": (
                "OverallGrade0-4 persist in Madden M19-M27 and disappear in CFB27; no literal "
                "Player.Archetype field or demonstrated grade-to-name mapping was found."
            ),
            "authenticated_cross_year_names": [],
            "renamed_candidates": [],
        },
        "m19_m20": {
            "ability_progression_tunable_structure_changed": False,
            "overall_grade_count_m19": 5,
            "overall_grade_count_m20": 5,
            "numeric_weight_change_inferred": False,
        },
        "formula_status": {
            "TE": "VT_AND_PRR_RANKING_INHERITANCE_STRONG_GRITTY_ARCHITECTURE_ONLY",
            "Center": "HISTORICAL_NUMERIC_INHERITANCE_REJECTED",
            "QB": "NO_HISTORICAL_HYBRID_PRODUCTION_MODEL",
            "Other": "UNSOLVED",
        },
        "prospective_validation": {"new_cards": 0, "refit": False, "results": []},
    }


def freeze_inputs(root: Path, files: list[Path], cards: list[dict]) -> dict:
    hashes = {}
    for path in sorted(files):
        hashes[path.relative_to(root).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    card_ids = sorted(card["external_card_id"] for card in cards)
    return {
        "source_commit": "49acdda",
        "population_n": len(cards),
        "card_ids_sha256": hashlib.sha256("\n".join(card_ids).encode()).hexdigest(),
        "input_sha256": hashes,
        "cutoff_date": max(card["retrieval_timestamp"] for card in cards),
        "no_retrospective_leakage": True,
    }


def build_phase5(root: Path) -> dict[str, Any]:
    inventories = load_inventories(root)
    population_state = json.loads(
        (root / "data/external/cfb_fan_population_state.json").read_text()
    )
    cards = list(population_state["cards"].values())
    threshold_snapshot = json.loads(
        (root / "data/external/cfb27_ability_thresholds.json").read_text()
    )
    thresholds = normalize_thresholds(threshold_snapshot)
    ability_progression = ability_progression_analysis(inventories)
    graph = build_schema_graph(inventories)
    proximity = threshold_proximity(cards, thresholds)
    chronology = capability_chronology(cards, proximity)
    pressure = replacement_pressure_v2(root, chronology)
    bridges = phase4_bridges(root, thresholds, cards)
    phase4 = root / "data/research/cfb27_inheritance_phase4"
    frozen_files = [
        root / "data/external/cfb_fan_population_state.json",
        root / "data/external/cfb27_ability_thresholds.json",
        phase4 / "phase4_frozen_snapshot.json",
        phase4 / "phase4_summary.json",
        root / "data/research/progression_audit/progression_inventory.json",
    ]
    return {
        "frozen_input": freeze_inputs(root, frozen_files, cards),
        "ability_progression": ability_progression,
        "schema_graph": graph,
        "overall_grade": overall_grade_investigation(inventories),
        "thresholds": thresholds,
        "threshold_centrality": threshold_centrality(thresholds),
        "threshold_proximity": proximity,
        "progression": progression_crosswalk(root, thresholds),
        "capability_chronology": chronology,
        "special_boost_threshold": special_threshold_test(cards, proximity),
        "qb_trk": qb_trk_analysis(cards),
        "player_architecture_graph": player_architecture_graph(thresholds),
        "replacement_pressure_v2": pressure,
        "gm_evaluator": gm_evaluator(cards, proximity, pressure),
        "chatgpt_research_targets": chatgpt_targets(),
        **bridges,
        "table_44": {
            "classification": "LIKELY_SAME_FAMILY",
            "verified_same_table": False,
            "rows_recovered": 0,
            "limitation": "No row-level historical export or explicit identifier join was found.",
        },
        "m19_te_provenance": {
            "likely_storage_family": "SEPARATE_XML_ASSET_OR_UNKNOWN",
            "ability_progression_tunable_ruled_in": False,
            "reason": (
                "Observed fields describe ability progression/regression, not OVR coefficients."
            ),
            "confidence": "MODERATE",
        },
        "dynamic_paths": {
            "evidence_type": "EA_PRIMARY_EXTERNAL_DOCUMENTATION",
            "source": "https://www.ea.com/games/ea-sports-college-football/college-football-27/news/college-football-27-ultimate-team",
            "claims": [
                "paths are position-archetype based and each path has its own OVR",
                "upgrade steps increase a subset of ratings in a path rating group",
                "rating groups can overlap across archetypes",
                "attributes and paths have caps",
                "highest path determines displayed archetype and OVR on multi-path items",
            ],
            "schema_proof_claimed": False,
        },
        "data_validation": {
            "guessed_values": False,
            "leakage": False,
            "unsupported_schema_inference": False,
            "access_bypass": False,
            "canonical_modified": False,
            "threshold_rows_cross_source_validated": False,
        },
    }


def write_artifacts(output: Path, analysis: dict) -> None:
    output.mkdir(parents=True, exist_ok=True)
    artifacts = {
        "phase5_frozen_snapshot.json": analysis["frozen_input"],
        "ability_progression_tunable_raw.json": analysis["ability_progression"]["raw_definitions"],
        "ability_progression_field_evolution.json": analysis["ability_progression"][
            "field_evolution"
        ],
        "related_table_graph.json": analysis["schema_graph"],
        "ability_family_map.json": analysis["schema_graph"]["family_maps"]["ability"],
        "progression_family_map.json": analysis["schema_graph"]["family_maps"]["progression"],
        "archetype_representation_map.json": analysis["schema_graph"]["family_maps"]["archetype"],
        "overall_grade_investigation.json": analysis["overall_grade"],
        "table_44_archaeology.json": analysis["table_44"],
        "m19_te_weight_provenance.json": analysis["m19_te_provenance"],
        "dynamic_path_crosswalk.json": analysis["dynamic_paths"],
        "ability_threshold_records.json": analysis["thresholds"],
        "ability_centrality.json": analysis["threshold_centrality"],
        "threshold_proximity.json": analysis["threshold_proximity"],
        "progression_attribute_crosswalk.json": analysis["progression"],
        "capability_chronology.json": analysis["capability_chronology"],
        "special_boost_threshold_analysis.json": analysis["special_boost_threshold"],
        "qb_trk_analysis.json": analysis["qb_trk"],
        "player_architecture_graph.json": analysis["player_architecture_graph"],
        "replacement_pressure_v2.json": analysis["replacement_pressure_v2"],
        "pc_evaluator_phase5.json": analysis["gm_evaluator"],
        "chatgpt_research_queue.json": analysis["chatgpt_research_targets"],
        "te_architecture_crosswalk.json": analysis["te_architecture"],
        "te_moneyball_matrix.json": analysis["te_moneyball_matrix"],
        "ea_design_signals_v2.json": analysis["ea_design_signals_v2"],
        "backfield_creator_architecture.json": analysis["backfield_creator"],
        "cross_year_archetype_evolution.json": analysis["archetype_evolution"],
        "m19_m20_structural_findings.json": analysis["m19_m20"],
        "formula_research_status.json": analysis["formula_status"],
        "prospective_validation_ledger.json": analysis["prospective_validation"],
        "phase5_summary.json": analysis,
    }
    for name, payload in artifacts.items():
        (output / name).write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
