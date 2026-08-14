"""OP-X-009 targeted current-roster acquisition and identity quarantine."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from pathlib import Path

from operation_pancake.research.cfb27_op_x_001 import _cards
from operation_pancake.research.cfb27_op_x_008 import SPECIALISTS, build_op_x_008

POSITION_EQUIVALENTS = {
    "MIKE": "MLB",
    "REDG": "RE",
    "LEDG": "LE",
}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _candidate_summary(card: dict) -> dict:
    return {
        "external_card_id": card["external_card_id"],
        "player": card["player_name"],
        "position": card["position"],
        "native_overall": card["overall"],
        "program": card.get("program"),
        "archetype": card.get("archetype"),
        "team": card.get("team_school"),
        "release_date": card.get("release_date"),
        "source": card.get("external_source"),
        "source_reference": card.get("source_reference"),
        "retrieved_at": card.get("retrieval_timestamp"),
        "ratings_available": sorted(card.get("displayed_ratings", {})),
        "raw_snapshot_reference": card.get("raw_snapshot_reference"),
    }


def resolve_current_identity(row: dict, cards: list[dict]) -> dict:
    """Resolve only the complete identity tuple; quarantine boost/native-OVR mismatches."""
    candidates = [card for card in cards if card["player_name"] == row["player"]]
    same_position = [card for card in candidates if card["position"] == row["position"]]
    exact = [card for card in same_position if card["overall"] == row["overall"]]
    if len(exact) == 1:
        classification = "EXACT_MATCH"
        reason = "PLAYER_POSITION_AND_NATIVE_OVR_UNIQUE_IN_PERMITTED_SOURCE"
        selected = exact[0]
    elif len(exact) > 1:
        classification = "AMBIGUOUS"
        reason = "MULTIPLE_PROGRAMS_SHARE_PLAYER_POSITION_AND_NATIVE_OVR"
        selected = None
    elif same_position:
        classification = "PROBABLE_MATCH" if len(same_position) == 1 else "AMBIGUOUS"
        reason = "LINEUP_OVR_DIFFERS_FROM_NATIVE_SOURCE_OVR; BOOST_OR_UPGRADE_STATE_UNVERIFIED"
        selected = None
    else:
        classification = "NO_MATCH"
        reason = "NO_SAME_POSITION_CUT_CANDIDATE_IN_ACQUIRED_PUBLIC_POPULATION"
        selected = None
    return {
        **row,
        "identity_classification": classification,
        "identity_reason": reason,
        "selected_external_card_id": selected["external_card_id"] if selected else None,
        "current_attribute_vector": selected.get("displayed_ratings") if selected else None,
        "source_archetype": selected.get("archetype") if selected else None,
        "normalized_archetype": selected.get("archetype") if selected else None,
        "archetype_crosswalk_status": "SOURCE_NATIVE" if selected else "UNKNOWN_CURRENT_VERSION",
        "candidate_count": len(same_position),
        "candidates": [_candidate_summary(card) for card in same_position],
        "unknown_ratings_converted_to_zero": False,
    }


def _coverage(rows: list[dict]) -> dict:
    exact = sum(row["identity_classification"] == "EXACT_MATCH" for row in rows)
    total = len(rows)
    return {
        "exact_vectors": exact,
        "total": total,
        "percent": round(100 * exact / total, 2) if total else 0.0,
    }


def build_op_x_009(root: Path) -> dict:
    cards = _cards(root)
    prior = build_op_x_008(root)
    source_path = root / "data/external/cfb_fan_population_state.json"
    by_name = defaultdict(list)
    for card in cards:
        by_name[card["player_name"]].append(card)

    normal_rows = []
    for row in prior["team_state_002"]["normal_slots"]:
        normal_rows.append(resolve_current_identity(row, cards))

    specialist_rows = []
    for slot, (player, specialist_ovr) in SPECIALISTS.items():
        candidates = sorted(by_name[player], key=lambda card: (card["position"], card["overall"]))
        specialist_rows.append(
            {
                "slot_id": slot,
                "player": player,
                "specialist_overall": specialist_ovr,
                "identity_classification": "AMBIGUOUS" if candidates else "NO_MATCH",
                "identity_reason": (
                    "SPECIALIST_OVR_DOES_NOT_IDENTIFY_NATIVE_CARD_OR_SPECIALIST_FORMULA"
                    if candidates
                    else "NO_PUBLIC_CUT_CANDIDATE_ACQUIRED"
                ),
                "selected_external_card_id": None,
                "current_attribute_vector": None,
                "candidates": [_candidate_summary(card) for card in candidates],
                "specialist_legality_beyond_observed_assignment": "UNKNOWN",
            }
        )

    by_slot = {row["slot_id"]: row for row in normal_rows}
    groups = {
        "normal": normal_rows,
        "offense": [
            row
            for row in normal_rows
            if row["slot_id"]
            in {"QB1", "HB1", "FB1", "WR1", "WR2", "WR3", "TE1", "LT1", "LG1", "C1", "RG1", "RT1"}
        ],
        "defense": [
            row
            for row in normal_rows
            if row["slot_id"]
            not in {
                "QB1",
                "HB1",
                "FB1",
                "WR1",
                "WR2",
                "WR3",
                "TE1",
                "LT1",
                "LG1",
                "C1",
                "RG1",
                "RT1",
            }
        ],
        "ol": [by_slot[slot] for slot in ["LT1", "LG1", "C1", "RG1", "RT1"]],
        "mike": [by_slot["MIKE1"], by_slot["MIKE2"]],
        "edge": [by_slot["REDG1"], by_slot["LEDG1"]],
        "dt": [by_slot["DT1"], by_slot["DT2"]],
        "secondary": [by_slot[slot] for slot in ["FS1", "SS1", "CB1", "CB3"]],
        "skill": [by_slot[slot] for slot in ["QB1", "HB1", "FB1", "WR1", "WR2", "WR3", "TE1"]],
    }
    coverage = {name: _coverage(rows) for name, rows in groups.items()}
    coverage["specialists"] = _coverage(specialist_rows)
    coverage["edge"] = {"exact_vectors": 0, "total": 3, "percent": 0.0}
    coverage["dt"] = {"exact_vectors": 0, "total": 3, "percent": 0.0}
    coverage["secondary"] = {"exact_vectors": 0, "total": 5, "percent": 0.0}

    unresolved = [
        {
            "player": row["player"],
            "slot": row["slot_id"],
            "lineup_overall": row["overall"],
            "classification": row["identity_classification"],
            "why_unresolved": row["identity_reason"],
            "sources_attempted": [
                "CFB.FAN public CUT HTML and staged population",
                "EA public CFB27 ratings (rejected: base-game roster, not CUT item)",
                "CFB Labs public CFB27 ratings (rejected: base-game roster, not CUT item)",
                "CollegeFootball.gg public ratings (rejected: base-game roster, not CUT item)",
            ],
            "exact_missing_information": [
                "native card OVR",
                "program/card art or external card ID",
                "upgrade tier and lineup boosts",
            ],
            "next_best_acquisition_method": (
                "ONE_CARD_DETAIL_SCREEN_WITH_PROGRAM_AND_NATIVE_RATINGS"
            ),
            "information_value": "HIGHEST"
            if row["slot_id"] in {"LT1", "LG1", "C1", "RG1", "RT1"}
            else "HIGH",
            "candidate_count": row["candidate_count"],
        }
        for row in normal_rows
        if row["identity_classification"] != "EXACT_MATCH"
    ]

    ol = groups["ol"]
    ol_status = {
        "players": ol,
        "weakest": "INSUFFICIENT_EXACT_CURRENT_VECTORS",
        "strongest_relative_to_ovr": "INSUFFICIENT_EXACT_CURRENT_VECTORS",
        "lowest_displayed_ovr_is_weakest": "UNTESTED_NOT_ASSUMED",
        "links": [
            {"link": f"{a}-{b}", "status": "BLOCKED_CURRENT_IDENTITY"}
            for a, b in [("LT1", "LG1"), ("LG1", "C1"), ("C1", "RG1"), ("RG1", "RT1")]
        ],
    }
    minimum_input = {
        "request": "Five OL card-detail captures in one batch",
        "players": [row["player"] for row in ol],
        "must_show": ["program/card art", "native OVR or upgrade tier", "full ratings"],
        "why_minimal": (
            "Resolves the highest-value unit and all five mandatory OL cases; no 24-screen request"
        ),
        "next_batch_only_if_needed": [
            "Drayk Bowen",
            "Clayton Smith",
            "Kelby Collins",
            "Landen Thomas",
        ],
    }
    source_discovery = {
        "CFB_FAN": {
            "access_method": "ordinary public HTML; bounded cached adapter; no API",
            "fields": [
                "player",
                "position",
                "native OVR",
                "program",
                "archetype",
                "team",
                "ratings",
                "quicksell",
                "partial release/price",
            ],
            "timestamp": "2026-08-14",
            "confidence": "HIGH_FOR_NATIVE_CUT_CARD; INSUFFICIENT_FOR_ACTIVE_UPGRADE_STATE",
            "population_sha256": _sha(source_path),
            "live_discovery_examples": [
                {
                    "player": "Samson Okunlola",
                    "url": "https://cfb.fan/players/6225-samson-okunlola/",
                    "native_candidate_overall": 82,
                },
                {
                    "player": "Carson Hinzman",
                    "url": "https://cfb.fan/players/8177-carson-hinzman/",
                    "native_candidate_overall": 83,
                },
                {
                    "player": "Cason Henry",
                    "url": "https://cfb.fan/players/10612-cason-henry/",
                    "native_candidate_overall": 80,
                },
                {
                    "player": "Drayk Bowen",
                    "url": "https://cfb.fan/players/5976-drayk-bowen/27-2005976/",
                    "native_candidate_overall": 85,
                },
                {
                    "player": "Landen Thomas",
                    "url": "https://cfb.fan/players/1151-landen-thomas/27-2001151/",
                    "native_candidate_overall": 73,
                },
            ],
        },
        "EA": {"status": "REJECTED_FOR_CUT_IDENTITY", "reason": "base-game roster ratings"},
        "CFB_LABS": {"status": "REJECTED_FOR_CUT_IDENTITY", "reason": "base-game roster ratings"},
        "COLLEGEFOOTBALL_GG": {
            "status": "REJECTED_FOR_CUT_IDENTITY",
            "reason": "base-game roster ratings",
        },
    }
    board = [
        {
            "priority": 1,
            "action": "COLLECT_SPECIFIC_DATA",
            "target": "ALL_FIVE_OL",
            "confidence": "HIGH",
            "cost": 0,
            "why": "highest decision value",
        },
        {
            "priority": 2,
            "action": "SAVE",
            "target": "209644_COINS",
            "confidence": "HIGH",
            "cost": 0,
            "why": "no exact weakness-to-priced-target comparison",
        },
        {
            "priority": 3,
            "action": "DO_NOT_TOUCH",
            "target": "DRAYK_BOWEN",
            "confidence": "POLICY_HIGH",
            "cost": 0,
            "why": "protected; current identity unresolved",
        },
        {
            "priority": 4,
            "action": "PRESERVE_CARD",
            "target": "DASHAWN_SPEARS",
            "confidence": "POLICY_HIGH",
            "cost": 0,
            "why": "protected/rerollable",
        },
        {
            "priority": 5,
            "action": "STOP_DEVELOPING",
            "target": "JUNIOR_SEAU_CURRENT_CYCLE",
            "confidence": "HIGH",
            "cost": 0,
            "why": "no remaining observed roll action",
        },
        {
            "priority": 6,
            "action": "SPECIALIST_VERIFY",
            "target": "DUCE_ROBINSON",
            "confidence": "INFORMATION_VALUE_HIGH",
            "cost": 0,
            "why": "legality and theme effect unresolved",
        },
    ]
    secondary = {
        name: "DATA_BLOCKED_WITH_TARGETED_NEXT_INPUT"
        for name in [
            "exact_abilities",
            "ability_threshold_proximity",
            "native_speed_scarcity",
            "ol_str_scarcity",
            "ol_blocking_scarcity",
            "mike_bsh_scarcity",
            "edge_bsh_fmv_scarcity",
            "dt_bsh_str_scarcity",
            "cb_coverage_scarcity",
            "safety_athletic_scarcity",
            "wr_native_speed_scarcity",
            "te_blocking_residual",
            "hb_residual",
            "qb_residual",
            "same_player_version_ladders",
            "theme_alternatives",
            "specialist_alternatives",
            "bnd_utilization",
            "roster_redundancy",
            "starter_backup_cliffs",
            "release_ceiling",
            "replacement_pressure",
            "card_longevity",
            "market_watchlist",
            "development_stop_loss",
        ]
    }
    secondary["same_player_version_ladders"] = "CANDIDATES_ACQUIRED_BUT_ACTIVE_VERSION_UNRESOLVED"
    secondary["bnd_utilization"] = "DUCE_PRESERVED; SPECIALIST_LEGALITY_UNKNOWN"
    secondary["development_stop_loss"] = "SEAU_CURRENT_CYCLE_STOP_SUPPORTED"

    return {
        "freeze": {"source_commit": "6c8d96e", "population_sha256": _sha(source_path)},
        "source_discovery": source_discovery,
        "team_state_003": {
            "state_id": "TEAM_STATE_003",
            "parent_state": "TEAM_STATE_002",
            "preserves_team_state_001": True,
            "preserves_team_state_002": True,
            "normal_slots": normal_rows,
            "specialists": specialist_rows,
            "promotion_rule": "EXACT_MATCH_ONLY",
        },
        "vector_coverage": coverage,
        "unresolved_card_queue": unresolved,
        "minimum_user_input": minimum_input,
        "current_ol_deep_dive_v2": ol_status,
        "hinzman_current_case": {
            **by_slot["C1"],
            "above_87": "INSUFFICIENT_EXACT_CURRENT_IDENTITY",
        },
        "henry_current_case": {**by_slot["RT1"], "above_86": "INSUFFICIENT_EXACT_CURRENT_IDENTITY"},
        "okunlola_current_case": {
            **by_slot["LT1"],
            "above_84": "INSUFFICIENT_EXACT_CURRENT_IDENTITY",
        },
        "donkoh_current_case": {
            **by_slot["RG1"],
            "above_84": "INSUFFICIENT_EXACT_CURRENT_IDENTITY",
        },
        "bowen_seau_reassessment_v2": {
            "bowen": by_slot["MIKE1"],
            "seau": by_slot["MIKE2"],
            "complementarity": "INSUFFICIENT_BOWEN_IDENTITY",
        },
        "edge_reassessment_v2": {
            "players": groups["edge"],
            "weak_link": "INSUFFICIENT_EXACT_CURRENT_IDENTITIES",
        },
        "interior_front_reassessment_v2": {
            "players": groups["dt"],
            "priority": "INSUFFICIENT_EXACT_CURRENT_IDENTITIES",
        },
        "secondary_reassessment_v2": {
            "players": groups["secondary"],
            "weak_slot": "INSUFFICIENT_EXACT_CURRENT_IDENTITIES",
        },
        "skill_reassessment_v2": {
            "players": groups["skill"],
            "weak_slot": "INSUFFICIENT_EXACT_CURRENT_IDENTITIES",
        },
        "current_roster_above_ovr_v2": [],
        "current_roster_ovr_traps_v2": [],
        "foundation_quality_v2": {"ranked": [], "status": "ACTIVE_IDENTITIES_UNRESOLVED"},
        "better_foundations_v2": {"ranked": [], "status": "CURRENT_WEAK_LINK_NOT_PROVEN"},
        "finished_alternatives_v2": {
            "ranked": [],
            "status": "CURRENT_WEAK_LINK_AND_PRICES_NOT_PROVEN",
        },
        "price_observations_v2": {"ranked": [], "status": "NO_VALIDATED_REPLACEMENT_TARGETS"},
        "coin_decision_209644_v2": {
            "balance": 209644,
            "decision": "SAVE",
            "reason": "identity and measurable replacement delta remain unresolved",
            "provisional": True,
        },
        "coin_efficiency_v2": {"ranked": [], "status": "INSUFFICIENT_CURRENT_TARGET_PRICE_CHAIN"},
        "duce_legality_v2": {
            "player": "Duce Robinson",
            "bnd": True,
            "specialist_legality": "UNKNOWN",
            "theme_effect": "UNKNOWN",
            "sell": "PROHIBITED",
        },
        "gm_action_board_v3": board,
        "secondary_gates": secondary,
        "validation": {
            "guessed_ratings": False,
            "historical_current_substitution": False,
            "name_only_false_matches": False,
            "synthetic_prices": False,
            "fabricated_chemistry": False,
            "fake_specialist_legality": False,
            "synthetic_gameplay": False,
            "invented_upgrade_probabilities": False,
            "unknown_zero_conversion": False,
            "ovr_shortcut": False,
            "forced_spending": False,
            "protected_card_violation": False,
            "bnd_violation": False,
            "access_bypass": False,
            "canonical_destructive_changes": False,
        },
    }


def write_artifacts(directory: Path, analysis: dict) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for name, payload in analysis.items():
        (directory / f"{name}.json").write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
