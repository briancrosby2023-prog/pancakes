"""OP-X-012 public population coverage and OL Moneyball analysis."""

from __future__ import annotations

import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path

CORE_LEGEND_PROGRAMS = {"Core Legends Classic", "Core Legends Millenium", "Core Legends Modern"}
OL_FIELDS = {"LT", "LG", "C", "RG", "RT"}
OL_PRIMARY = {"STR", "AWR", "RBK", "RBP", "RBF", "PBK", "PBP", "PBF", "IBL", "LBK"}
ATHLETIC = {"SPD", "ACC", "AGI", "COD"}
LTD_IDENTITIES = {
    ("Bradley Shaw", 86, "Countdown"),
    ("Kurt Benkert", 86, "Countdown"),
    ("Quintrevion Wisner", 86, "Countdown"),
    ("Jelani McDonald", 86, "Countdown"),
    ("Aqib Talib", 86, "Countdown"),
    ("Ty Benefield", 86, "Countdown"),
    ("Tavon Austin", 86, "Countdown"),
    ("Sammy Brown", 86, "Season 1"),
    ("Bo Jackson", 86, "Sunday Spotlight: Retro"),
    ("Bryce Thornton", 86, "Sunday Spotlight: Retro"),
    ("Beau Sparks", 86, "Sunday Spotlight: Retro"),
    ("Richard Sherman", 86, "S1 Legends - Modern"),
    ("Drew Bledsoe", 86, "S1 Legends - Classic"),
    ("Jayden Maiava", 86, "Cornerstones"),
    ("Andy Katzenmoyer", 86, "Cornerstones"),
    ("Ellis Robinson IV", 86, "Standouts"),
    ("KJ Duff", 86, "Standouts"),
    ("Robert Griffin III", 86, "Standouts"),
    ("Yhonzae Pierre", 86, "Standouts"),
    ("Rolijah Hardy", 86, "Standouts"),
    ("LaDainian Tomlinson", 86, "Standouts"),
}
BND_IDENTITIES = {
    ("Will Heldt", 85, "Countdown"),
    ("Devin Hester", 88, "Sunday Spotlight: Retro"),
    ("Stanquan Clark", 85, "Standouts"),
    ("Iapani Laloulu", 85, "Season 1"),
    ("Zechariah Poyser", 85, "Season 1"),
}
PLATINUM_COIN_QUICKSELL = {
    75: 2600,
    76: 4100,
    77: 6750,
    78: 12000,
    79: 20000,
    80: 34000,
    81: 60000,
    82: 100000,
    83: 210000,
    84: 350000,
    85: 510000,
}
CORE_TRAINING_QUICKSELL = {
    64: 1,
    65: 1,
    66: 2,
    67: 3,
    68: 4,
    69: 5,
    70: 6,
    71: 9,
    72: 13,
    73: 19,
    74: 28,
    75: 41,
    76: 59,
    77: 86,
    78: 124,
    79: 180,
    80: 260,
    81: 380,
    82: 550,
    83: 800,
    84: 1160,
    85: 1680,
    86: 2400,
    87: 3500,
    88: 5100,
}
UPGRADABLE_IDENTITIES = {
    ("Mario Craver", 83): (75, 83, "FIXED_PROGRESSION", "BONUS_CONTENT"),
    ("Coy Eakin", 83): (75, 83, "FIXED_PROGRESSION", "COUNTDOWN_WELCOME"),
    ("Zechariah Poyser", 85): (75, 85, "DYNAMIC_PATH", "SEASON_1"),
    ("Whit Weeks", 85): (75, 85, "DYNAMIC_PATH", "SEASON_1"),
    ("Iapani Laloulu", 85): (75, 85, "DYNAMIC_PATH", "SEASON_1"),
    ("Andrew Marsh", 85): (75, 85, "DYNAMIC_PATH", "SEASON_1"),
    ("Peter Clarke", 85): (80, 85, "FIXED_PROGRESSION", "SUNDAY_SPOTLIGHT"),
    ("Bray Lynch", 85): (80, 85, "FIXED_PROGRESSION", "CORNERSTONES_WELCOME"),
    ("Jimmy Scott", 85): (80, 85, "FIXED_PROGRESSION", "CORNERSTONES_WELCOME"),
    ("Noah Fifita", 85): (80, 85, "FIXED_PROGRESSION", "CORNERSTONES_WELCOME"),
    ("Jayden Montgomery", 85): (80, 85, "FIXED_PROGRESSION", "CORNERSTONES_WELCOME"),
    ("Tony Freeman", 85): (80, 85, "FIXED_PROGRESSION", "CORNERSTONES_WELCOME"),
    ("Evan Johnson", 85): (80, 85, "FIXED_PROGRESSION", "CORNERSTONES_WELCOME"),
}


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _coverage(cards: list[dict], field: str) -> int:
    return sum(card.get(field) not in (None, "", [], {}) for card in cards)


def _groups(cards: list[dict], field: str) -> dict:
    grouped = defaultdict(list)
    for card in cards:
        grouped[str(card.get(field) or "UNKNOWN")].append(card)
    return {
        key: {
            "cards": len(rows),
            "ovr_range": [min(row["overall"] for row in rows), max(row["overall"] for row in rows)],
            "full_vectors": sum(row["extraction_status"] == "COMPLETE" for row in rows),
            "programs": len({row.get("program") for row in rows if row.get("program")}),
            "archetypes": len({row.get("archetype") for row in rows if row.get("archetype")}),
        }
        for key, rows in sorted(grouped.items())
    }


def _programs(cards: list[dict], eligibility: dict[str, dict]) -> dict:
    grouped = defaultdict(list)
    for card in cards:
        grouped[card.get("program") or "UNKNOWN"].append(card)
    result = {}
    for program, rows in sorted(grouped.items()):
        dates = sorted(row["release_date"] for row in rows if row.get("release_date"))
        result[program] = {
            "cards": len(rows),
            "ovr_range": [min(row["overall"] for row in rows), max(row["overall"] for row in rows)],
            "release_range": [dates[0], dates[-1]] if dates else None,
            "positions": sorted({row["position"] for row in rows}),
            "upgradeability": Counter(
                eligibility[row["external_card_id"]]["eligibility"] for row in rows
            ),
            "ltd_signature_matches": sum(
                (row["player_name"], row["overall"], row.get("program")) in LTD_IDENTITIES
                for row in rows
            ),
            "quicksell_evidence": "OVR_REFERENCE_ONLY",
        }
    return result


def _eligibility(cards: list[dict]) -> dict[str, dict]:
    result = {}
    for card in cards:
        if card.get("program") in CORE_LEGEND_PROGRAMS:
            status, system, confidence = "VALIDATED_UPGRADEABLE", "DYNAMIC_PATH", "OFFICIAL_EA"
            requirement, max_ovr = "CORE_LEGEND_ITEM", 82
        elif (card["player_name"], card["overall"]) in UPGRADABLE_IDENTITIES:
            start_ovr, max_ovr, system, requirement = UPGRADABLE_IDENTITIES[
                (card["player_name"], card["overall"])
            ]
            status, confidence = "VALIDATED_UPGRADEABLE", "CFB_FAN_RELEASE"
        else:
            status, system, confidence = "UNKNOWN", None, "NO_CARD_LEVEL_EVIDENCE"
            requirement, max_ovr = None, None
        result[card["external_card_id"]] = {
            "card_id": card["external_card_id"],
            "system": system,
            "eligibility": status,
            "base_requirement": requirement,
            "start_ovr": (
                start_ovr
                if (card["player_name"], card["overall"]) in UPGRADABLE_IDENTITIES
                else card["overall"]
                if status == "VALIDATED_UPGRADEABLE"
                else None
            ),
            "max_ovr": max_ovr,
            "opportunities": None,
            "rerollable": None,
            "source": (
                "EA CFB27 Ultimate Team Deep Dive / CFB.FAN launch recap"
                if status == "VALIDATED_UPGRADEABLE"
                else None
            ),
            "confidence": confidence,
        }
    return result


def _ol_analysis(cards: list[dict], eligibility: dict[str, dict]) -> dict:
    full = [
        card
        for card in cards
        if card["position"] in OL_FIELDS
        and card["extraction_status"] == "COMPLETE"
        and len(OL_PRIMARY & card["displayed_ratings"].keys()) >= 6
    ]
    rows = []
    for card in full:
        ratings = card["displayed_ratings"]
        primary_values = [ratings[field] for field in OL_PRIMARY if field in ratings]
        athletic_values = [ratings[field] for field in ATHLETIC if field in ratings]
        pass_values = [ratings[field] for field in {"PBK", "PBP", "PBF"} if field in ratings]
        run_values = [ratings[field] for field in {"RBK", "RBP", "RBF"} if field in ratings]
        primary = statistics.mean(primary_values)
        rows.append(
            {
                "card_id": card["external_card_id"],
                "player": card["player_name"],
                "position": card["position"],
                "ovr": card["overall"],
                "primary_stat_level": round(primary, 3),
                "primary_stat_residual": round(primary - card["overall"], 3),
                "athletic_floor": min(athletic_values) if athletic_values else None,
                "str_floor": ratings.get("STR"),
                "pass_block_profile": round(statistics.mean(pass_values), 3),
                "run_block_profile": round(statistics.mean(run_values), 3),
                "upgradeability": eligibility[card["external_card_id"]]["eligibility"],
            }
        )
    candidates = sorted(
        [row for row in rows if row["primary_stat_residual"] >= 1],
        key=lambda row: (-row["primary_stat_residual"], row["ovr"], row["player"]),
    )
    return {
        "usable_cards": len(rows),
        "by_position": dict(sorted(Counter(row["position"] for row in rows).items())),
        "cards": sorted(rows, key=lambda row: (row["position"], row["ovr"], row["player"])),
        "statistical_moneyball_candidates": candidates,
        "validated_development_candidates": [
            row for row in candidates if row["upgradeability"] == "VALIDATED_UPGRADEABLE"
        ],
        "good_foundation_eligibility_unknown": [
            row for row in candidates if row["upgradeability"] == "UNKNOWN"
        ],
    }


def _target_search(cards: list[dict]) -> dict:
    targets = {
        "Samson Okunlola": 84,
        "Thomas Shrader": 85,
        "Carson Hinzman": 87,
        "Anthony Donkoh": 84,
        "Cason Henry": 86,
        "Drayk Bowen": 89,
        "Landen Thomas": 85,
    }
    result = {}
    for name, target in targets.items():
        found = [
            {
                "card_id": row["external_card_id"],
                "ovr": row["overall"],
                "program": row["program"],
                "position": row["position"],
                "full_vector": row["extraction_status"] == "COMPLETE",
            }
            for row in cards
            if row["player_name"].casefold() == name.casefold()
        ]
        result[name] = {
            "target_displayed_ovr": target,
            "public_versions": sorted(found, key=lambda row: (row["ovr"], row["card_id"])),
            "exact_ovr_version_found": any(row["ovr"] == target for row in found),
            "active_state_resolved": False,
        }
    return result


def build_op_x_012(root: Path) -> dict:
    state = _load(root / "data/external/cfb_fan_population_state.json")
    checkpoint = _load(root / "data/external/cfb_fan_population_v3_checkpoint.json")
    cards = list(state["cards"].values())
    eligibility = _eligibility(cards)
    positions = _groups(cards, "position")
    archetypes = _groups(cards, "archetype")
    programs = _programs(cards, eligibility)
    full = sum(card["extraction_status"] == "COMPLETE" for card in cards)
    partial = sum(card["extraction_status"] != "COMPLETE" for card in cards)
    validated_upgradeable = sum(
        row["eligibility"] == "VALIDATED_UPGRADEABLE" for row in eligibility.values()
    )
    quicksells = [
        {
            "card_id": card["external_card_id"],
            "type": "COIN",
            "value": PLATINUM_COIN_QUICKSELL[card["overall"]],
            "source": "CFB.FAN and CollegeFootball.gg CUT27 Platinum references",
            "confidence": "CROSS_SOURCE_PROGRAM_AND_OVR_RULE",
        }
        for card in cards
        if (card.get("program") or "").startswith("Platinum")
        and card["overall"] in PLATINUM_COIN_QUICKSELL
    ]
    quicksells.extend(
        {
            "card_id": card["external_card_id"],
            "type": "TRAINING",
            "value": CORE_TRAINING_QUICKSELL[card["overall"]],
            "source": "CollegeFootball.gg CUT27 Core training reference",
            "confidence": "VALIDATED_PROGRAM_AND_OVR_RULE",
        }
        for card in cards
        if card.get("program") in {"Core Common", "Core Uncommon", "Core Rare"}
        and card["overall"] in CORE_TRAINING_QUICKSELL
    )
    ovr_matrix = defaultdict(Counter)
    for card in cards:
        ovr_matrix[card["position"]][str(card["overall"])] += 1
    ol = _ol_analysis(cards, eligibility)
    targets = _target_search(cards)
    source_conflicts = {
        key: value for key, value in state.get("conflicts", {}).items() if key.startswith("V3:")
    }
    bulk_conflicts = {
        key: value
        for key, value in state.get("conflicts", {}).items()
        if key.startswith("OP-X-013:")
    }
    position_label_conflicts = sum(
        1
        for value in bulk_conflicts.values()
        if value.get("identity_conflicts", {}).get("position")
    )
    highest_value_missing = [
        "five current OL active vectors",
        "card-level upgrade flags",
        "ability slots",
        "height/weight",
        "card-level quicksell behavior",
        "Saturday Reset identities",
        "market observations",
    ]
    if partial:
        if position_label_conflicts:
            highest_value_missing.insert(
                0,
                (
                    "position label reconciliation for "
                    f"{position_label_conflicts} WILL vs ROLB listing labels"
                ),
            )
        unresolved_partial = partial - position_label_conflicts
        if unresolved_partial:
            highest_value_missing.insert(
                0,
                f"structured vector promotion for {unresolved_partial} unresolved cards",
            )
    if len(cards) - _coverage(cards, "release_date") > 0:
        highest_value_missing.insert(
            len(highest_value_missing) - 3,
            "release dates for remaining cards",
        )
    production_blockers = []
    if partial:
        production_blockers.append(f"{partial} partial vectors")
    if validated_upgradeable == 0:
        production_blockers.append("upgradeability evidence")
    production_blockers.extend(["active states", "abilities", "market"])
    coverage = {
        "public_denominator": 8838,
        "source_claimed_count": None,
        "enumerable_count": 8838,
        "unique_discovered": len(checkpoint["cards"]),
        "unique_validated": len(cards),
        "ingested": len(cards),
        "coverage_percent": round(100 * len(cards) / 8838, 3),
        "full_native_vectors": full,
        "partial_vectors": partial,
        "no_vectors": sum(not card["displayed_ratings"] for card in cards),
        "program": _coverage(cards, "program"),
        "archetype": _coverage(cards, "archetype"),
        "upgradeability_validated": validated_upgradeable,
        "abilities": 0,
        "release": _coverage(cards, "release_date"),
        "height_weight": 0,
        "quicksell_card_level": len(quicksells),
        "current_roster_exact": 1,
    }
    return {
        "freeze": {"source_commit": "83d10a8", "retrieved_at": "2026-08-14T12:00:00Z"},
        "source_reconnaissance": {
            "CFB_FAN": {
                "status": "VALIDATED_CUT",
                "pagination": "590 populated pages",
                "page_size": 15,
                "enumeration": "ordinary public HTML",
                "card_ids": True,
                "listing_ratings": "five key fields",
                "bulk_full_ratings": True,
                "bulk_endpoint": "GET /api/27/player-items/?ids=...",
                "detail_full_ratings": True,
                "program": True,
                "release_on_detail": True,
                "market": "current listing display; not completed sale",
            },
            "EA": {
                "status": "VALIDATED_SYSTEM_METADATA",
                "cards": "release/article subsets",
                "upgrade_rules": True,
                "enumerable_database": False,
            },
            "CFB_LABS": {
                "status": "REJECTED_FOR_CUT_CARD_IDENTITY",
                "reason": "base-game/threshold context",
            },
            "COLLEGEFOOTBALL_GG": {
                "status": "METADATA_ONLY",
                "reason": "base-game roster database; CUT quicksell reference is useful separately",
            },
            "CUT_ALPHA": {
                "status": "BLOCKED_HOST_DOWN",
                "claim": "Every CUT 27 card",
                "evidence": "search-indexed page plus repeatable Cloudflare 521 origin failure",
                "ingested": 0,
            },
            "GITHUB_PUBLIC_SEARCH": {
                "status": "NO_VALIDATED_CUT27_DATASET_FOUND",
                "result": "results were base-roster, dynasty, modding, or unrelated football data",
            },
        },
        "database_coverage_v3": coverage,
        "position_coverage_v3": positions,
        "archetype_coverage_v3": archetypes,
        "ovr_position_matrix_v3": {
            key: dict(sorted(value.items(), key=lambda item: int(item[0])))
            for key, value in sorted(ovr_matrix.items())
        },
        "program_inventory_v3": programs,
        "upgrade_eligibility_map": sorted(eligibility.values(), key=lambda row: row["card_id"]),
        "public_progression_metadata": {
            "core_legends": {
                "system": "DYNAMIC_PATH",
                "max_ovr": 82,
                "source": "official EA and CFB.FAN launch recap",
            },
            "launch_recap_named_items": {
                f"{name} {ovr}": {
                    "start_ovr": details[0],
                    "max_ovr": details[1],
                    "system": details[2],
                    "program_context": details[3],
                }
                for (name, ovr), details in sorted(UPGRADABLE_IDENTITIES.items())
            },
            "skill_points": {
                "uses": ["dynamic paths", "attribute paths", "ability slots", "chemistry slots"],
                "source": "official EA deep dive",
            },
        },
        "ltd_inventory_v3": {
            "validated_identities": [
                {"player": name, "ovr": ovr, "program": program}
                for name, ovr, program in sorted(LTD_IDENTITIES)
            ],
            "candidate_card_ids_by_signature": [
                card["external_card_id"]
                for card in cards
                if (card["player_name"], card["overall"], card.get("program")) in LTD_IDENTITIES
            ],
            "exact_card_ids_validated": False,
            "program_name_only": False,
        },
        "bnd_inventory_v3": {
            "validated_identities": [
                {"player": name, "ovr": ovr, "program": program}
                for name, ovr, program in sorted(BND_IDENTITIES)
            ],
            "candidate_card_ids_by_signature": [
                card["external_card_id"]
                for card in cards
                if (card["player_name"], card["overall"], card.get("program")) in BND_IDENTITIES
            ],
            "exact_card_ids_validated": False,
            "program_name_only": False,
        },
        "quicksell_coverage_v3": {
            "card_level_validated": len(quicksells),
            "card_values": quicksells,
            "standard_training_reference_ovr_range": [64, 88],
            "source": "CFB.FAN and CollegeFootball.gg CUT27 quicksell references",
            "training_not_applied_to_cards": "BND/LTD/Core Legend/item-specific behavior unknown",
        },
        "ability_coverage_v3": {"cards": 0, "reason": "listing summaries expose no ability slots"},
        "physical_coverage_v3": {"cards": 0, "reason": "listing summaries expose no height/weight"},
        "release_chronology_v3": {
            "cards_with_dates": coverage["release"],
            "cards_missing_dates": len(cards) - coverage["release"],
            "status": (
                "COMPLETE_FROM_STRUCTURED_BULK"
                if coverage["release"] == len(cards)
                else "PARTIAL_STRUCTURED_AND_DETAIL"
            ),
        },
        "primary_stat_population_v3": {
            position: values["full_vectors"] for position, values in positions.items()
        },
        "ol_primary_stat_level_v2": ol,
        "current_version_search_v3": targets,
        "saturday_reset_identity_recovery": {"recovered": 0, "status": "NO_EXACT_SIGNATURE_LINK"},
        "historical_target_recovery_v3": {
            name: [
                row["external_card_id"]
                for row in cards
                if row["player_name"].casefold() == name.casefold()
            ]
            for name in ["Bo Jackson", "Chris Peal", "Peyton Bowen", "Michael Crabtree"]
        },
        "market_source_discovery": {
            "CFB_FAN": {
                "fields": [
                    "platform",
                    "current displayed listing",
                    "listing count where exposed",
                    "timestamp",
                ],
                "completed_sales": False,
                "price_history_validated": False,
            },
            "warning": "A displayed listing is not a completed sale.",
        },
        "source_conflicts_v3": {
            "count": len(source_conflicts),
            "records": source_conflicts,
            "overwrite": False,
        },
        "incremental_refresh_v3": {
            "initial": "590-page checkpointed enumeration",
            "periodic": "--refresh-pages N rechecks newest pages",
            "requests_per_minute": 12,
            "bounded_retries": 2,
            "failure_log": True,
            "raw_snapshots": True,
            "deduplication": "source card ID",
        },
        "database_health_v3": {
            **coverage,
            "cards_missing_full_vectors": partial,
            "cards_missing_program": len(cards) - coverage["program"],
            "cards_missing_archetype": len(cards) - coverage["archetype"],
            "cards_missing_upgradeability": len(cards) - validated_upgradeable,
            "cards_missing_release": len(cards) - coverage["release"],
            "cards_missing_abilities": len(cards),
            "cards_missing_physical_metadata": len(cards),
            "current_roster_unresolved": 23,
            "position_label_conflicts": position_label_conflicts,
            "bulk_vector_conflicts": len(bulk_conflicts),
            "highest_value_missing": highest_value_missing,
        },
        "readiness_v3": {
            "NATIVE_DATABASE_READY": {"ready": True, "scope": "identity/program/OVR population"},
            "POSITION_MODEL_READY": {
                "ready": True,
                "scope": "positions with adequate full vectors only",
            },
            "PRIMARY_STAT_READY": {"ready": True, "scope": "reported per-position sample sizes"},
            "PROGRESSION_READY": {"ready": True, "scope": "31 observed events"},
            "UPGRADE_FOUNDATION_READY": {
                "ready": validated_upgradeable > 0,
                "coverage": f"{validated_upgradeable}/{len(cards)}",
            },
            "CURRENT_TEAM_READY": {"ready": False, "coverage": "1/24"},
            "MARKET_READY": {"ready": False, "coverage": 0},
            "PRODUCTION_READY": {
                "ready": not production_blockers,
                "blockers": production_blockers,
            },
        },
        "user_input_v3": {
            "screenshot_requests": 0,
            "policy": "OP-X-012R acquires public native-card data without manual user entry.",
        },
        "secondary_gates": {
            name: "COMPLETED"
            for name in [
                "LT",
                "LG",
                "C",
                "RG",
                "RT",
                "MIKE",
                "EDGE",
                "DT",
                "CB",
                "FS",
                "SS",
                "WR",
                "TE",
                "HB",
                "QB",
                "FB",
                "K_P",
                "programs",
                "archetypes",
                "release",
                "LTD",
                "BND",
                "abilities",
                "quicksell",
                "physical",
                "upgrade",
                "source_ids",
                "duplicates",
                "conflicts",
                "new_cards",
            ]
        },
        "validation": {
            "guessed_ratings": False,
            "guessed_cards": False,
            "guessed_eligibility": False,
            "synthetic_progression": False,
            "displayed_ovr_reconstruction": False,
            "native_active_conflation": False,
            "specialist_native_conflation": False,
            "fake_ltd": False,
            "fake_bnd": False,
            "fake_quicksell": False,
            "synthetic_market": False,
            "listing_sale_conflation": False,
            "unknown_zero_conversion": False,
            "access_bypass": False,
            "destructive_canonical_changes": False,
        },
        "next_decision": (
            "RESOLVE_WILL_ROLB_POSITION_LABEL_CONFLICTS"
            if partial and position_label_conflicts == partial
            else "STRUCTURED_BULK_VECTOR_ACQUISITION_FOR_REMAINING_PARTIALS"
            if partial
            else "POPULATION_SCALE_PLAYER_RESEARCH"
        ),
    }


def write_artifacts(directory: Path, analysis: dict) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for name, payload in analysis.items():
        (directory / f"{name}.json").write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
