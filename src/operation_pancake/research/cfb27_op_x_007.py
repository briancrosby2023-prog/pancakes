"""OP-X-007 partial, versioned CFB27 team Digital Twin and GM optimization."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from operation_pancake.research.cfb27_op_x_001 import _cards

NORMAL_SLOTS = [
    "QB1",
    "HB1",
    "WR1",
    "WR2",
    "WR3",
    "TE1",
    "LT",
    "LG",
    "C",
    "RG",
    "RT",
    "EDGE1",
    "EDGE2",
    "DT",
    "MIKE1",
    "MIKE2",
    "CB1",
    "CB2",
    "CB3",
    "FS1",
    "SS1",
]
SPECIALIST_CONCEPTS = ["SUB_LB", "SLOT_CB", "RUSH_EDGE", "RUSH_DT", "OFFENSIVE_SPECIALIST"]
PROTECTED = ["FS1", "MIKE1", "MIKE2"]


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def roster_slots() -> list[dict]:
    return [
        {
            "slot_id": slot,
            "object_type": "ROSTER_SLOT",
            "player_card_id": None,
            "protected_policy": slot in PROTECTED,
            "status": "UNKNOWN",
            "source": None,
            "confidence": "UNKNOWN",
        }
        for slot in NORMAL_SLOTS
    ] + [
        {
            "slot_id": slot,
            "object_type": "SPECIALIST_CONCEPT",
            "player_card_id": None,
            "legal_placement": "UNKNOWN",
            "status": "UNKNOWN",
            "source": None,
            "confidence": "UNKNOWN",
        }
        for slot in SPECIALIST_CONCEPTS
    ]


def apply_snapshot_delta(previous: list[dict], visible: list[dict]) -> dict:
    """Produce an idempotent slot delta without guessing absent or unreadable slots."""
    old = {row["slot_id"]: row for row in previous}
    new = {row["slot_id"]: row for row in visible}
    changes = []
    for slot in sorted(set(old) | set(new)):
        before, after = old.get(slot), new.get(slot)
        if before is None:
            classification = "ADDED"
        elif after is None:
            classification = "AMBIGUOUS"
        elif after.get("readable") is False:
            classification = "AMBIGUOUS"
        elif before.get("card_id") != after.get("card_id"):
            classification = "REMOVED" if after.get("card_id") is None else "MOVED"
        elif before.get("overall") is not None and after.get("overall") is not None:
            classification = (
                "UPGRADED"
                if after["overall"] > before["overall"]
                else "DOWNGRADED"
                if after["overall"] < before["overall"]
                else "UNCHANGED"
            )
        else:
            classification = "UNCHANGED"
        changes.append(
            {"slot_id": slot, "classification": classification, "before": before, "after": after}
        )
    return {"changes": changes, "absent_visible_slots_mean_removed": False}


def replacement_delta(current: dict | None, candidate: dict, role_attributes: list[str]) -> dict:
    if current is None:
        return {"classification": "INSUFFICIENT_DATA", "missing": ["current_player"]}
    differences = {}
    for attribute in role_attributes:
        left = current.get("ratings", {}).get(attribute)
        right = candidate.get("ratings", {}).get(attribute)
        differences[attribute] = None if left is None or right is None else right - left
    known = [value for value in differences.values() if value is not None]
    if len(known) != len(role_attributes):
        classification = "INSUFFICIENT_DATA"
    elif all(value >= 0 for value in known) and any(value > 0 for value in known):
        classification = "CLEAR_UPGRADE"
    elif all(value <= 0 for value in known) and any(value < 0 for value in known):
        classification = "DOWNGRADE"
    elif any(value > 0 for value in known) and any(value < 0 for value in known):
        classification = "ROLE_TRADEOFF"
    else:
        classification = "SIDEGRADE"
    return {
        "classification": classification,
        "role_rating_deltas": differences,
        "ovr_used_as_decision": False,
    }


def _known_assets(cards: list[dict], op6: dict) -> list[dict]:
    duce_card = next(
        card for card in cards if card["player_name"] == "Duce Robinson" and card["overall"] == 88
    )
    return [
        {
            "player": "Duce Robinson",
            "card_id": duce_card["external_card_id"],
            "version": "88 LTD",
            "overall": 88,
            "position": "WR",
            "bnd": True,
            "normal_slot": None,
            "specialist_status": "CANDIDATE",
            "theme_fit": "INCOMPATIBLE_NORMAL_STARTER",
            "last_confirmed": "OP-X-007_PACKET",
            "source": "USER_CONFIRMED_OP_X_006_007",
            "currentness": "CURRENT_CONFIRMED",
            "confidence": "HIGH",
        },
        {
            "player": "Junior Seau",
            "card_id": "JUNIOR_SEAU_EVO_PROJECT",
            "version": "81_START_EVO_TO_86",
            "overall": 86,
            "position": "MLB/MIKE",
            "bnd": "UNKNOWN",
            "normal_slot": "UNKNOWN",
            "specialist_status": "USER_CONTROLLED_MIKE_PROJECT",
            "theme_fit": "UNKNOWN",
            "last_confirmed": "OP-X-007_PACKET",
            "source": "USER_CONFIRMED_OP_X_004_007",
            "currentness": "CURRENT_CONFIRMED",
            "confidence": "HIGH_FOR_PROJECT_STATE",
        },
    ]


def _quality_rows(slots: list[dict], assets: list[dict]) -> list[dict]:
    assigned = {
        asset["normal_slot"]: asset
        for asset in assets
        if asset["normal_slot"] not in (None, "UNKNOWN")
    }
    return [
        {
            "slot_id": slot["slot_id"],
            "player": assigned.get(slot["slot_id"]),
            "raw_card_quality": "UNKNOWN",
            "role_fit": "UNKNOWN",
            "foundation_quality": "UNKNOWN",
            "athletic_floor": "UNKNOWN",
            "technical_floor": "UNKNOWN",
            "ability_access": "UNKNOWN",
            "theme_fit": "UNKNOWN",
            "specialist_utility": "UNKNOWN",
            "development_upside": "UNKNOWN",
            "longevity": "UNKNOWN",
            "replacement_pressure": "UNKNOWN",
            "confidence": "UNKNOWN",
        }
        for slot in slots
        if slot["object_type"] == "ROSTER_SLOT"
    ]


def build_op_x_007(root: Path) -> dict:
    cards = _cards(root)
    op6 = _load(root / "data/research/cfb27_op_x_006/mandatory_validation.json")
    assets = _known_assets(cards, op6)
    slots = roster_slots()
    quality = _quality_rows(slots, assets)
    confidence = [
        {
            "slot_id": row["slot_id"],
            "known_player": False,
            "known_version": False,
            "known_ovr": False,
            "known_theme_fit": False,
            "known_bnd": False,
            "known_upgrade_state": False,
            "known_specialist_role": False,
            "last_confirmed": None,
            "classification": "UNKNOWN",
        }
        for row in quality
    ]
    twin = {
        "twin_id": "TEAM_DIGITAL_TWIN_V1",
        "partial_records_legal": True,
        "layers": [
            "TEAM",
            "ROSTER",
            "DEPTH_CHART",
            "SPECIALISTS",
            "THEME_TEAM",
            "CHEMISTRY",
            "SCHEME",
            "FORMATIONS",
            "PLAY_STYLE",
            "PLAYER_CARDS",
            "UPGRADE_STATES",
            "BND_STATUS",
            "MARKET_STATUS",
            "RESOURCE_STATE",
            "PROTECTED_ASSETS",
            "DEVELOPMENT_PROJECTS",
            "WATCHLIST",
            "DECISION_HISTORY",
        ],
        "team": {
            "identity": [
                "RUN_FIRST",
                "CLOCK_CONTROL",
                "OPTION_TURNOVER_RISK_DISFAVORED",
                "4-2-5",
                "6-1",
                "TWO_EDGE_FREQUENT",
            ],
            "source": "USER_CONFIRMED_EXISTING_POLICY",
            "confidence": "HIGH",
        },
        "roster": assets,
        "slots": slots,
        "theme_team": {
            "current_theme": "UNKNOWN",
            "threshold": "UNKNOWN",
            "count": "UNKNOWN",
            "required_count": "UNKNOWN",
            "bonuses": "UNKNOWN",
        },
        "resource_state": {"coins": "UNKNOWN", "training": "UNKNOWN"},
        "protected_assets": PROTECTED,
    }
    delta_schema = {
        "classifications": [
            "ADDED",
            "REMOVED",
            "MOVED",
            "UPGRADED",
            "DOWNGRADED",
            "UNCHANGED",
            "AMBIGUOUS",
        ],
        "idempotent": True,
        "unreadable_policy": "AMBIGUOUS_NOT_GUESSED",
        "absent_slot_policy": "NOT_REMOVED_UNLESS_VISIBLE",
    }
    history = {
        "state_id": "TEAM_STATE_001",
        "timestamp": "OP-X-007_PACKET",
        "changes": [
            {"classification": "ADDED_CURRENT_EVIDENCE", "player": x["player"]} for x in assets
        ],
        "source": "USER_PACKET",
        "coins_resources": "UNKNOWN",
        "theme_configuration": "PARTIAL",
        "starting_lineup": "UNKNOWN",
        "specialists": ["Duce Robinson:CANDIDATE"],
        "development_projects": ["Junior Seau"],
    }
    theme = {
        "current_theme": "UNKNOWN",
        "current_threshold": "UNKNOWN",
        "current_count": "UNKNOWN",
        "required_count": "UNKNOWN",
        "player_contribution": "UNKNOWN",
        "off_theme_cost": "QUALITATIVE_KNOWN_FOR_DUCE_NORMAL_START",
        "available_flex_slots": "UNKNOWN",
        "unknown_bonuses": True,
        "questions": [
            "Can player start without breaking constraint?",
            "Can player use specialist slot?",
            "Who is displaced?",
        ],
        "duce_normal_start": "BLOCKED",
        "duce_specialist": "POTENTIALLY_USABLE_LEGALITY_UNKNOWN",
    }
    specialists = {
        "concepts": SPECIALIST_CONCEPTS,
        "legal_lineup_placements_claimed": False,
        "records": [
            {
                "player": "Duce Robinson",
                "status": "CANDIDATE",
                "normal_starter": "BLOCKED_THEME",
                "exact_placement": "UNKNOWN",
            }
        ],
    }
    roles = {
        "formula_weights_separate": True,
        "gameplay_importance_fabricated": False,
        "run_first": {
            "priority_groups": [
                "OL_PRIMARY_BLOCKING",
                "TE_BLOCKING_FOUNDATION",
                "HB_SUSTAINABILITY",
                "WR_BLOCKING_WHERE_OBSERVED",
            ]
        },
        "clock_control": {
            "priority_groups": [
                "FOUNDATION_COMPLETENESS",
                "BALL_SECURITY_WHERE_OBSERVED",
                "SHORT_INTERMEDIATE_EFFICIENCY",
            ]
        },
        "defense": {
            "EDGE1": "REQUIRED_CONCEPT",
            "EDGE2": "REQUIRED_CONCEPT",
            "MIKE": ["RUN_FOUNDATION", "COVERAGE_RESPONSIBILITY"],
            "interior": "RUN_DEFENSE_FOUNDATION",
        },
    }
    weakness = [
        {
            "slot_id": row["slot_id"],
            "classification": "UNKNOWN",
            "why": "No current-confirmed player assignment",
            "population_context_available": True,
            "roster_context_available": False,
        }
        for row in quality
    ]
    bottlenecks = [
        {
            "bottleneck": "CURRENT_LINEUP_VISIBILITY",
            "why": "No current slot assignments are confirmed",
            "available_solutions": ["OFFENSE_LINEUP_SCREEN", "DEFENSE_LINEUP_SCREEN"],
            "cost_data": "NOT_REQUIRED",
            "confidence": "HIGH",
        },
        {
            "bottleneck": "SPECIALIST_LEGALITY_FOR_DUCE",
            "why": "Specialist candidate is known but slot placement is not",
            "available_solutions": ["SPECIALISTS_SCREEN"],
            "cost_data": "NOT_REQUIRED",
            "confidence": "HIGH",
        },
    ]
    replacement = {
        "classifications": [
            "CLEAR_UPGRADE",
            "CONDITIONAL_UPGRADE",
            "SIDEGRADE",
            "ROLE_TRADEOFF",
            "DOWNGRADE",
            "INSUFFICIENT_DATA",
        ],
        "ovr_only_decision": False,
        "components": [
            "role ratings",
            "athletic",
            "technical",
            "ability",
            "theme",
            "BND/tradable",
            "development",
            "longevity",
            "market",
            "liquidity",
        ],
        "current_pairs": [],
    }
    marginal = {
        "structural_ranking": "BLOCKED_BY_UNKNOWN_LINEUP",
        "economic_ranking": "BLOCKED_BY_UNKNOWN_PRICES",
        "independent_outputs": True,
        "example_values_used": False,
    }
    coin = {
        "inputs": [
            "coin balance",
            "roster",
            "candidates",
            "prices",
            "quicksell",
            "BND",
            "theme",
            "development cost",
            "pressure",
            "longevity",
        ],
        "actions": [
            "BUY_NOW",
            "WATCH",
            "WAIT",
            "UPGRADE_CURRENT",
            "USE_BND",
            "SAVE_COINS",
            "NO_ACTION",
        ],
        "coin_balance_required_to_build": False,
        "budget_independent_frontier": [],
    }
    budget = {
        "tiers": ["UNDER_25K", "UNDER_50K", "UNDER_100K", "UNDER_250K", "UNDER_500K", "PREMIUM"],
        "populated": [],
        "reason": "No candidate cost observations linked to current roster needs",
        "synthetic_prices": False,
    }
    projects = [
        {
            "player": "Junior Seau",
            "start_version": 81,
            "current_version": 86,
            "target": 86,
            "path": "LURKER",
            "rolls_used": 4,
            "rolls_remaining": 0,
            "foundation_quality": "WEAKER_BROAD_FOUNDATION_THAN_84_PREMADE",
            "specialization": "ATHLETIC_MAX_SPEED_MIKE",
            "allocation_risk": "OBSERVED_HIGH",
            "resource_spend": "UNKNOWN",
            "stop_condition": [
                "target unreachable",
                "cost exceeds finished alternative",
                "replacement pressure",
                "better base",
            ],
            "next_decision": "STOP_CURRENT_81_TO_86_CYCLE_AND_COMPARE_FUTURE_ALTERNATIVES",
            "confidence": "EXPLORATORY_FOR_DISTRIBUTION_VALIDATED_FOR_OBSERVED_STATE",
        }
    ]
    stop_loss = {
        "criteria": [
            "excessive foundation repair",
            "target unrealistic",
            "cost exceeds finished alternative",
            "too few opportunities",
            "missed critical role attributes",
            "better base available",
            "replacement pressure",
        ],
        "seau": {
            "starting_decision_quality": "UNKNOWN_COUNTERFACTUAL",
            "roll_quality": "MIXED_ROLE_VALUE",
            "current_card_quality": "HIGH_ATHLETIC_SPECIALIZATION",
            "future_investment_quality": "REQUIRES_NEW_TARGET_OR_VERSION",
            "project_failure_declared": False,
        },
    }
    protected = [
        {
            "slot": slot,
            "replace_active_role_allowed": True,
            "discard_card_allowed": False,
            "preserve_for_reroll": True,
            "replacement_semantics": [
                "REPLACE_ACTIVE_ROLE",
                "KEEP_CARD",
                "MOVE_TO_DEPTH",
                "PRESERVE_FOR_REROLL",
                "USE_AS_DEVELOPMENT_ASSET",
            ],
        }
        for slot in PROTECTED
    ]
    bnd = [
        {
            "player": "Duce Robinson",
            "liquidity": "ZERO/BND",
            "normal_start": "BLOCKED_THEME",
            "specialist": "CANDIDATE",
            "depth": "POSSIBLE",
            "quicksell": "UNKNOWN",
            "sell": "PROHIBITED",
            "recommended": "KEEP_AND_RESOLVE_SPECIALIST_PLACEMENT",
        }
    ]
    flex = {
        "free_slot_assumed": False,
        "candidates": [
            "elite starter",
            "specialist",
            "rare archetype",
            "critical position",
            "BND asset",
            "temporary bridge",
        ],
        "decision": "BLOCKED_BY_UNKNOWN_THEME_COUNT_AND_FLEX",
        "objective": "GREATEST_NET_TEAM_BENEFIT_NOT_OVR",
    }
    redundancy = {
        "detections": [],
        "status": "BLOCKED_BY_UNKNOWN_LINEUP",
        "depth_automatically_bad": False,
    }
    identity = {
        name: {"status": "INTENDED_IDENTITY", "roster_support": "UNKNOWN"}
        for name in [
            "RUN_FIRST",
            "CLOCK_CONTROL",
            "DEFENSIVE_FRONT_PRESSURE",
            "TWO_EDGE_DEPLOYMENT",
            "4-2-5_SUPPORT",
            "6-1_SUPPORT",
            "THEME_TEAM_INTEGRITY",
            "SPECIALIST_FLEXIBILITY",
            "DEVELOPMENT_PIPELINE",
            "MARKET_FLEXIBILITY",
        ]
    }
    top = {
        "top_structural_need": {
            "value": "CURRENT_LINEUP_VISIBILITY",
            "why": "Needed to compare slots",
            "confidence": "HIGH",
        },
        "top_affordable_need": {
            "value": "UNKNOWN",
            "why": "No linked costs",
            "confidence": "BLOCKED",
        },
        "top_development_need": {
            "value": "RESOLVE_NEXT_SEAU_DECISION",
            "why": "Current project reached target",
            "confidence": "HIGH",
        },
        "top_market_watch": {
            "value": "UNKNOWN",
            "why": "Roster need not linked",
            "confidence": "BLOCKED",
        },
        "top_bnd_opportunity": {
            "value": "DUCE_SPECIALIST_PLACEMENT",
            "why": "High raw-quality zero-liquidity asset",
            "confidence": "HIGH",
        },
        "top_specialist_opportunity": {
            "value": "DUCE_ROBINSON",
            "why": "Known off-theme BND candidate",
            "confidence": "HIGH",
        },
        "top_position_leave_alone": {
            "value": "PROTECTED_FS1_MIKE1_MIKE2",
            "why": "Preserve cards for reroll even if active role changes",
            "confidence": "HIGH",
        },
    }
    no_move = {
        "conditions": [
            "sidegrade",
            "excessive price",
            "low pressure",
            "unusual role fit",
            "theme cost",
            "unfavorable validated timing",
            "better release supported",
            "insufficient evidence",
        ],
        "current": [
            {
                "scope": "UNCONFIRMED_ROSTER_BUYS",
                "action": "NO_ACTION",
                "why": "Insufficient current lineup and cost evidence",
            }
        ],
        "market_timing_invented": False,
    }
    capital = {
        "dead_coins": [],
        "underused_bnd": ["Duce Robinson: placement unresolved"],
        "overinvested_depth": [],
        "unfinished_development": [],
        "redundant_assets": [],
        "low_liquidity": ["Duce Robinson:BND"],
        "absence_means_no_evidence_not_zero": True,
    }
    ledger = {
        "schema": [
            "date",
            "team_state",
            "recommendation",
            "alternatives",
            "reason",
            "confidence",
            "expected_benefit",
            "cost",
            "actual_user_decision",
            "later_outcome",
        ],
        "entries": [
            {
                "date": "OP-X-007",
                "team_state": "TEAM_STATE_001",
                "recommendation": "RESOLVE_DUCE_SPECIALIST_PLACEMENT",
                "alternatives": ["DEPTH", "QUIET_HOLD"],
                "reason": "High-quality BND cannot normal-start under known theme constraint",
                "confidence": "HIGH_FOR_CONSTRAINT",
                "expected_benefit": "Recover BND roster utility",
                "cost": "UNKNOWN/NO_ACQUISITION",
                "actual_user_decision": "UNKNOWN",
                "later_outcome": "UNKNOWN",
            }
        ],
    }
    requests = [
        {
            "rank": 1,
            "input": "OFFENSE_LINEUP_SCREEN",
            "information_value": "VERY_HIGH",
            "unlocks": ["run-first OL/TE/HB weakness", "normal starters"],
        },
        {
            "rank": 2,
            "input": "DEFENSE_LINEUP_SCREEN",
            "information_value": "VERY_HIGH",
            "unlocks": ["EDGE1/EDGE2", "MIKE", "4-2-5/6-1 foundation"],
        },
        {
            "rank": 3,
            "input": "SPECIALISTS_SCREEN",
            "information_value": "VERY_HIGH",
            "unlocks": ["Duce legal placement", "subpackages"],
        },
        {
            "rank": 4,
            "input": "THEME_CHEMISTRY_SCREEN",
            "information_value": "HIGH",
            "unlocks": ["theme count", "flex", "bonuses"],
        },
        {
            "rank": 5,
            "input": "COINS_TRAINING_SCREEN",
            "information_value": "MEDIUM",
            "unlocks": ["budget frontier", "resource allocation"],
        },
        {
            "rank": 6,
            "input": "ACTIVE_EVO_SCREENS",
            "information_value": "MEDIUM",
            "unlocks": ["development queue", "rerolls"],
        },
    ]
    api = {
        "endpoints": [
            "current_team",
            "slot_status",
            "player_role",
            "weakness_map",
            "replacement_options",
            "development_projects",
            "bnd_assets",
            "protected_assets",
            "theme_constraints",
            "action_queue",
            "coin_priority",
            "missing_data",
            "decision_history",
        ],
        "format": "DETERMINISTIC_JSON",
        "partial_state_supported": True,
    }
    command = {
        "team_identity": identity,
        "current_lineup": [],
        "specialists": specialists["records"],
        "protected_assets": protected,
        "bnd_assets": bnd,
        "development_projects": projects,
        "weakest_positions": [],
        "strongest_positions": [],
        "replacement_pressure": "UNKNOWN",
        "top_moneyball_options": "POPULATION_AVAILABLE_ROSTER_FIT_UNKNOWN",
        "top_upgrade_options": [],
        "market_watch": [],
        "coin_priority": "SAVE/NO_ACTION_UNTIL_NEEDS_AND_COSTS_LINKED",
        "no_move_positions": PROTECTED,
        "missing_high_value_data": requests,
        "next_gm_actions": [
            "CAPTURE_OFFENSE_LINEUP",
            "CAPTURE_DEFENSE_LINEUP",
            "RESOLVE_DUCE_SPECIALIST_PLACEMENT",
        ],
    }
    secondary_names = [
        "same_player_ladder",
        "theme_moneyball",
        "specialist_moneyball",
        "bnd_ranking",
        "development_compare",
        "finished_alternative",
        "release_ceiling",
        "replacement_heatmap",
        "position_scarcity",
        "market_liquidity",
        "ltd_compatibility",
        "training_allocation",
        "reroll_allocation",
        "ability_overlay",
        "archetype_diversity",
        "speed_floor",
        "blockshed_run_defense",
        "ol_primary_strength",
        "route_coverage_matchup",
        "screenshot_regression",
    ]
    secondary = {
        name: {"status": "FRAMEWORK_READY", "personalized_output": "BLOCKED_WHERE_ROSTER_UNKNOWN"}
        for name in secondary_names
    }
    source_paths = [
        root / "data/external/cfb_fan_population_state.json",
        root / "data/research/cfb27_op_x_006/decision_engine_v1.json",
        root / "data/research/cfb27_op_x_005/dynamic_upgrade_event_master_v1.json",
    ]
    return {
        "freeze": {
            "source_commit": "25dc0cc",
            "input_sha256": {
                str(p.relative_to(root)).replace("\\", "/"): _sha(p) for p in source_paths
            },
        },
        "team_digital_twin_v1": twin,
        "roster_slot_model": slots,
        "current_roster_ingestion": assets,
        "screenshot_delta_ingestion": delta_schema,
        "roster_history": [history],
        "theme_team_constraint_engine": theme,
        "specialist_slot_engine": specialists,
        "role_requirement_profiles": roles,
        "slot_quality_model": quality,
        "team_weakness_map": weakness,
        "bottleneck_detection": bottlenecks,
        "replacement_delta_engine": replacement,
        "marginal_roster_improvement": marginal,
        "coin_allocation_engine": coin,
        "budget_frontier": budget,
        "development_project_queue": projects,
        "upgrade_stop_loss": stop_loss,
        "protected_asset_logic": protected,
        "bnd_utilization_engine": bnd,
        "theme_flex_value": flex,
        "redundancy_detector": redundancy,
        "team_identity_scorecard": identity,
        "top_team_improvements": top,
        "no_move_recommendation": no_move,
        "roster_efficiency_dead_capital": capital,
        "gm_decision_ledger": ledger,
        "current_state_snapshot_request": requests,
        "current_roster_confidence_map": confidence,
        "digital_twin_api": api,
        "gm_command_center_v1": command,
        "mandatory_validation": {
            "duce": bnd[0],
            "seau": {**projects[0], **stop_loss["seau"]},
            "protected": protected,
            "run_first": roles["run_first"],
            "two_edge": {"EDGE1": roles["defense"]["EDGE1"], "EDGE2": roles["defense"]["EDGE2"]},
        },
        "secondary_gates": secondary,
        "validation": {
            "fabricated_roster": False,
            "guessed_versions": False,
            "assumed_coins": False,
            "fabricated_chemistry": False,
            "assumed_theme_count": False,
            "fake_specialist_legality": False,
            "synthetic_prices": False,
            "gameplay_fabrication": False,
            "protected_asset_violations": False,
            "historical_as_current_leakage": False,
            "canonical_changes": False,
        },
    }


def write_artifacts(directory: Path, analysis: dict) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for name, payload in analysis.items():
        (directory / f"{name}.json").write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
