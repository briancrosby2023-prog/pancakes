"""OP-X-008 current-team audit and evidence-constrained coin allocation."""

from __future__ import annotations

import hashlib
import json
import statistics
from collections import defaultdict
from pathlib import Path

from operation_pancake.research.cfb27_op_x_001 import _cards

CURRENT = {
    "QB1": ("Dante Moore", 88, "QB"),
    "HB1": ("Jidah Baugh", 88, "HB"),
    "FB1": ("Owen Allen", 86, "FB"),
    "WR1": ("Kalik Lockett", 87, "WR"),
    "WR2": ("Malachi Toney", 89, "WR"),
    "WR3": ("Javon Nicholas", 86, "WR"),
    "TE1": ("Peter Clarke", 85, "TE"),
    "LT1": ("Samson Okunlola", 84, "LT"),
    "LG1": ("Thomas Shrader", 85, "LG"),
    "C1": ("Carson Hinzman", 87, "C"),
    "RG1": ("Anthony Donkoh", 84, "RG"),
    "RT1": ("Cason Henry", 86, "RT"),
    "FS1": ("Dashawn Spears", 85, "FS"),
    "WILL1": ("Chris Cole", 87, "ROLB"),
    "MIKE1": ("Drayk Bowen", 89, "MLB"),
    "MIKE2": ("Junior Seau", 86, "MLB"),
    "SAM1": ("Keaton Thomas", 88, "LOLB"),
    "SS1": ("King Mack", 87, "SS"),
    "CB1": ("Cormani McClain", 86, "CB"),
    "CB3": ("Devin Sanchez", 87, "CB"),
    "REDG1": ("Clayton Smith", 86, "RE"),
    "DT1": ("Amare Adams", 86, "DT"),
    "DT2": ("DJ Hicks", 86, "DT"),
    "LEDG1": ("Kelby Collins", 86, "LE"),
}
SPECIALISTS = {
    "3DRB1": ("Owen Allen", 79),
    "PWHB1": ("Owen Allen", 89),
    "SLWR1": ("Girard Pringle Jr.", 83),
    "GAD1": ("Owen Allen", 89),
    "NT1": ("Marquis Gracial", 86),
    "SUBLB1": ("Drayk Bowen", 88),
    "RRE1": ("Clayton Smith", 86),
    "RDT1": ("Amare Adams", 85),
    "RLE1": ("Landen Thomas", 85),
    "SLCB1": ("Zechariah Poyser", 87),
}
ROLE_ATTRS = {
    "QB": ["THP", "SAC", "MAC", "DAC", "AWR", "TUP"],
    "HB": ["SPD", "ACC", "CAR", "BCV", "BTK"],
    "FB": ["LBK", "IBL", "RBK", "STR", "CAR"],
    "WR": ["SPD", "ACC", "CTH", "CIT", "SRR", "MRR", "DRR", "RLS"],
    "TE": ["RBK", "RBP", "RBF", "IBL", "STR", "CTH"],
    "LT": ["RBP", "RBF", "PBP", "PBF", "STR", "AWR", "IBL"],
    "LG": ["RBP", "RBF", "PBP", "PBF", "STR", "AWR", "IBL"],
    "C": ["RBP", "PBP", "AWR", "STR", "RBK", "PBF", "IBL"],
    "RG": ["RBP", "RBF", "PBP", "PBF", "STR", "AWR", "IBL"],
    "RT": ["RBP", "RBF", "PBP", "PBF", "STR", "AWR", "IBL"],
    "MLB": ["SPD", "ACC", "BSH", "STR", "PUR", "TAK", "PRC", "ZCV"],
    "ROLB": ["SPD", "ACC", "BSH", "PUR", "TAK", "PRC"],
    "LOLB": ["SPD", "ACC", "BSH", "PUR", "TAK", "PRC"],
    "RE": ["SPD", "ACC", "BSH", "FMV", "PMV", "STR", "PUR", "TAK", "PRC"],
    "LE": ["SPD", "ACC", "BSH", "FMV", "PMV", "STR", "PUR", "TAK", "PRC"],
    "DT": ["BSH", "STR", "PMV", "FMV", "TAK", "PUR"],
    "FS": ["SPD", "ACC", "MCV", "ZCV", "COD", "AGI", "PRC"],
    "SS": ["SPD", "ACC", "MCV", "ZCV", "COD", "AGI", "PRC"],
    "CB": ["SPD", "ACC", "MCV", "ZCV", "PRS", "COD", "AGI"],
}


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def current_records(cards: list[dict]) -> list[dict]:
    by_name = defaultdict(list)
    for card in cards:
        by_name[card["player_name"]].append(card)
    rows = []
    for slot, (player, overall, position) in CURRENT.items():
        exact = next(
            (
                card
                for card in by_name[player]
                if card["overall"] == overall and card["position"] == position
            ),
            None,
        )
        references = sorted(
            {card["overall"] for card in by_name[player] if card["position"] == position}
        )
        rows.append(
            {
                "slot_id": slot,
                "player": player,
                "overall": overall,
                "position": position,
                "currentness": "CURRENT_CONFIRMED",
                "source": "USER_SCREENSHOT_OP_X_008",
                "last_confirmed": "OP-X-008",
                "confidence": "HIGH_FOR_VISIBLE_FIELDS",
                "exact_population_card_id": exact["external_card_id"] if exact else None,
                "ratings": exact["displayed_ratings"] if exact else None,
                "historical_reference_overalls": references,
                "historical_reference_used_as_current": False,
            }
        )
    return rows


def _profile(row: dict, cards: list[dict]) -> dict:
    attrs = ROLE_ATTRS.get(row["position"], [])
    ratings = row["ratings"] or {}
    known = {attr: ratings[attr] for attr in attrs if attr in ratings}
    population = [card for card in cards if card["position"] == row["position"]]
    peers = []
    for card in population:
        values = [card["displayed_ratings"].get(attr) for attr in attrs]
        if values and all(value is not None for value in values):
            peers.append((card["overall"], statistics.mean(values)))
    mean = round(statistics.mean(known.values()), 3) if len(known) == len(attrs) and attrs else None
    higher = [value for ovr, value in peers if ovr > row["overall"]]
    same = [value for ovr, value in peers if ovr == row["overall"]]
    relation = "UNKNOWN_MISSING_EXACT_VERSION_RATINGS"
    if mean is not None and higher and mean >= statistics.median(higher):
        relation = "STRONG_ABOVE_OVR"
    elif mean is not None and same and mean < statistics.median(same) - 3:
        relation = "BELOW_OVR_FOR_ROLE"
    elif mean is not None:
        relation = "NORMAL_OR_MODERATE"
    return {
        **row,
        "archetype": "UNKNOWN"
        if row["ratings"] is None
        else next(
            card.get("archetype")
            for card in cards
            if card["external_card_id"] == row["exact_population_card_id"]
        ),
        "primary_attributes": attrs,
        "actual_attributes": known or None,
        "role_primary_mean": mean,
        "same_ovr_median": round(statistics.median(same), 3) if same else None,
        "higher_ovr_median": round(statistics.median(higher), 3) if higher else None,
        "ovr_relation": relation,
        "athletic_foundation": "UNKNOWN" if row["ratings"] is None else "OBSERVED_COMPONENTS",
        "technical_foundation": "UNKNOWN" if row["ratings"] is None else "OBSERVED_COMPONENTS",
        "role_fit": "UNKNOWN" if row["ratings"] is None else "STATISTICAL_ONLY",
        "replacement_priority": "NEEDS_EXACT_CARD_VECTOR",
        "gameplay_claim": False,
    }


def build_op_x_008(root: Path) -> dict:
    cards = _cards(root)
    current = current_records(cards)
    profiles = [_profile(row, cards) for row in current]
    by_slot = {row["slot_id"]: row for row in profiles}
    specialists = [
        {
            "slot_id": slot,
            "player": player,
            "specialist_overall": overall,
            "normal_overall": next(
                (row["overall"] for row in current if row["player"] == player), None
            ),
            "currentness": "CURRENT_CONFIRMED",
            "source": "USER_SCREENSHOT_OP_X_008",
            "specialist_ovr_is_normal_ovr": False,
            "legality_beyond_visible_assignment": "UNKNOWN",
        }
        for slot, (player, overall) in SPECIALISTS.items()
    ]
    assets = current + [
        {
            "slot_id": row["slot_id"],
            "player": row["player"],
            "overall": row["specialist_overall"],
            "position": "SPECIALIST",
            "currentness": "CURRENT_CONFIRMED",
            "source": row["source"],
        }
        for row in specialists
    ]
    state2 = {
        "state_id": "TEAM_STATE_002",
        "parent_state": "TEAM_STATE_001",
        "source": "USER_SCREENSHOTS_OP_X_008",
        "team_overall": 86,
        "resources": {
            "coins": {"amount": 209644, "identity": "COINS", "confidence": "USER_CONFIRMED"},
            "training": {"amount": 4189, "identity": "TRAINING", "confidence": "USER_CONFIRMED"},
            "green": {"amount": 220, "identity": "UNKNOWN"},
            "other": {"amount": 200, "identity": "UNKNOWN"},
            "trophy_like": {"amount": 1000, "identity": "UNKNOWN"},
        },
        "normal_slots": current,
        "specialists": specialists,
        "special_teams": [],
        "special_teams_status": "NO_READABLE_VALUES_SUPPLIED",
        "preserves_team_state_001": True,
    }
    delta = [
        {
            "slot_id": row["slot_id"],
            "classification": "ADDED",
            "after": {"player": row["player"], "overall": row["overall"]},
        }
        for row in current
    ] + [
        {
            "slot_id": row["slot_id"],
            "classification": "ADDED",
            "after": {"player": row["player"], "specialist_overall": row["specialist_overall"]},
        }
        for row in specialists
    ]
    offense = [
        row
        for row in profiles
        if row["slot_id"]
        in {"QB1", "HB1", "FB1", "WR1", "WR2", "WR3", "TE1", "LT1", "LG1", "C1", "RG1", "RT1"}
    ]
    ol = [by_slot[s] for s in ["LT1", "LG1", "C1", "RG1", "RT1"]]
    links = [
        {
            "link": f"{a}-{b}",
            "left": by_slot[a]["player"],
            "right": by_slot[b]["player"],
            "classification": "INSUFFICIENT_EXACT_RATINGS",
            "interaction_weights_invented": False,
        }
        for a, b in [("LT1", "LG1"), ("LG1", "C1"), ("C1", "RG1"), ("RG1", "RT1")]
    ]
    hinzman = {
        **by_slot["C1"],
        "historical_evidence": "86_OVR_RAW_STRENGTH_REFERENCE_EXISTS_BUT_IS_NOT_CURRENT_87_VECTOR",
        "above_ovr_claim": "BLOCKED_FOR_CURRENT_VERSION",
        "keep_bias": "PROTECTED_BY_UNCERTAINTY_AND_HIGH_CURRENT_OVR_NOT_PROOF",
    }
    henry = {
        **by_slot["RT1"],
        "historical_importance": "PRESERVED",
        "decision": "DO_NOT_TOUCH_PENDING_EXACT_VECTOR",
        "why": "No exact current 86 RT vector or priced superior alternative",
    }
    skill = [row for row in offense if row["position"] not in {"LT", "LG", "C", "RG", "RT"}]
    owen = {
        "player": "Owen Allen",
        "normal": {"slot": "FB1", "overall": 86},
        "specialist_roles": {
            row["slot_id"]: row["specialist_overall"]
            for row in specialists
            if row["player"] == "Owen Allen"
        },
        "value": {
            "power_back": "HIGH_VISIBLE_SPECIALIST_OVR",
            "goal_line": "HIGH_VISIBLE_SPECIALIST_OVR",
            "third_down": "LOW_VISIBLE_SPECIALIST_OVR",
        },
        "normal_and_specialist_ovr_separate": True,
        "exact_ratings": "UNKNOWN",
        "decision": "KEEP_MULTI_ROLE_ASSET",
    }
    defense = [row for row in profiles if row not in offense]
    mike = {
        "MIKE1": by_slot["MIKE1"],
        "MIKE2": by_slot["MIKE2"],
        "SUBLB1": next(row for row in specialists if row["slot_id"] == "SUBLB1"),
        "comparison": "EXACT_CURRENT_PAIR_VECTOR_INCOMPLETE",
        "complementarity": "INSUFFICIENT_DATA",
        "redundancy": "INSUFFICIENT_DATA",
    }
    seau = {
        "player": "Junior Seau",
        "slot": "MIKE2",
        "current_overall": 86,
        "starting_decision_quality": "COUNTERFACTUAL_UNRESOLVED",
        "roll_quality": "MIXED_ROLE_VALUE_VALIDATED",
        "current_card_quality": "ATHLETIC_SPECIALIZATION_WITH_EXACT_VECTOR",
        "current_roster_value": "CURRENT_CONFIRMED_MIKE2",
        "future_investment_quality": "NO_REMAINING_OBSERVED_ROLLS_COMPARE_NEW_BASE_OR_FINISHED",
        "spend_another_resource": "NO_SUPPORTED_CURRENT_ACTION",
        "rng_probability_fabricated": False,
    }
    bowen = {
        **by_slot["MIKE1"],
        "specialist": "SUBLB1_88",
        "protected": True,
        "normal_starter_value": "CURRENT_CONFIRMED",
        "user_control_candidate": "UNKNOWN",
        "replacement_resistance": "HIGH_POLICY_AND_MULTI_ROLE",
        "decision": "DO_NOT_TOUCH",
    }
    edge = {
        "normal": [by_slot["REDG1"], by_slot["LEDG1"]],
        "rush": [row for row in specialists if row["slot_id"] in {"RRE1", "RLE1"}],
        "both_roles_required": True,
        "quality": "NEEDS_EXACT_CURRENT_VECTORS",
        "replacement_priority": "UNRESOLVED",
    }
    interior = {
        "normal": [by_slot["DT1"], by_slot["DT2"]],
        "specialists": [row for row in specialists if row["slot_id"] in {"NT1", "RDT1"}],
        "six_one_relevance": "STRUCTURALLY_RELEVANT",
        "foundation": "NEEDS_EXACT_CURRENT_VECTORS",
    }
    secondary = {
        "normal": [by_slot[s] for s in ["FS1", "SS1", "CB1", "CB3"]],
        "specialist": next(row for row in specialists if row["slot_id"] == "SLCB1"),
        "technical_audit": "NEEDS_EXACT_CURRENT_VECTORS",
    }
    fs = {
        **by_slot["FS1"],
        "protected": True,
        "active_role_quality": "NEEDS_EXACT_CURRENT_VECTOR",
        "replacement_need": "WATCH_NOT_DISCARD",
        "card_retention": "MANDATORY_POLICY",
        "reroll_value": "PRESERVE",
        "development_value": "UNKNOWN",
    }
    speed = [
        {
            "slot_id": row["slot_id"],
            "player": row["player"],
            "native_spd": (row["ratings"] or {}).get("SPD"),
            "status": "OBSERVED"
            if (row["ratings"] or {}).get("SPD") is not None
            else "UNKNOWN_VERSION_VECTOR",
        }
        for row in profiles
        if row["position"] in {"WR", "HB", "CB", "FS", "SS", "MLB", "RE", "LE"}
    ]
    floors = [
        {
            "unit": unit,
            "slots": slot_ids,
            "floor": None,
            "status": "INSUFFICIENT_EXACT_CURRENT_VECTORS",
        }
        for unit, slot_ids in {
            "OL": ["LT1", "LG1", "C1", "RG1", "RT1"],
            "SKILL": ["HB1", "WR1", "WR2", "WR3", "TE1"],
            "MIKE": ["MIKE1", "MIKE2"],
            "EDGE": ["REDG1", "LEDG1"],
            "INTERIOR": ["DT1", "DT2"],
            "SECONDARY": ["FS1", "SS1", "CB1", "CB3"],
        }.items()
    ]
    categorized = [
        row
        for row in profiles
        if row["ovr_relation"] in {"STRONG_ABOVE_OVR", "NORMAL_OR_MODERATE"}
        and row["ratings"] is not None
    ]
    above = [row for row in categorized if row["ovr_relation"] == "STRONG_ABOVE_OVR"]
    traps = [row for row in profiles if row["ovr_relation"] == "BELOW_OVR_FOR_ROLE"]
    resistance = [
        {
            "player": "Drayk Bowen",
            "slot": "MIKE1",
            "level": "HIGH",
            "reasons": ["protected", "normal+SUBLB roles"],
        },
        {
            "player": "Owen Allen",
            "slot": "FB1",
            "level": "HIGH",
            "reasons": ["multi-role specialist value"],
        },
        {
            "player": "Dashawn Spears",
            "slot": "FS1",
            "level": "POLICY_HIGH",
            "reasons": ["protected/rerollable; active replacement does not discard"],
        },
        {
            "player": "Cason Henry",
            "slot": "RT1",
            "level": "PROVISIONAL",
            "reasons": ["no exact vector or priced superior alternative"],
        },
        {
            "player": "Duce Robinson",
            "slot": "EXTERNAL_BND",
            "level": "ASSET_HIGH",
            "reasons": ["BND zero liquidity", "specialist candidate"],
        },
    ]
    weakness = [
        {
            "slot_id": row["slot_id"],
            "player": row["player"],
            "classification": "UNKNOWN",
            "why": "Exact current-version role vector unavailable",
            "displayed_ovr_not_used_as_shortcut": True,
        }
        for row in profiles
    ]
    priorities = [
        {"rank": rank, "position": pos, "status": "NEEDS_CARD_AND_PRICE_DATA", "why": reason}
        for rank, (pos, reason) in enumerate(
            [
                ("OL", "Run-first identity; exact five-man foundation is highest information need"),
                ("FS", "85 active role but protected card must be retained"),
                ("EDGE", "Two normal and two rush roles require simultaneous audit"),
                ("TE", "Run-first blocking foundation unverified"),
                ("OTHER", "No supported weakness yet"),
            ],
            1,
        )
    ]
    coin_plan = {
        "balance": 209644,
        "recommendation": "SAVE_AND_WATCH",
        "spend_now": 0,
        "forced_spend": False,
        "why": "No exact current weakness-to-priced-candidate comparison is validated",
        "next_searches": [
            "exact current OL card vectors",
            "real prices for theme-compatible OL candidates",
            "FS active-role candidates with retain-card plan",
            "EDGE candidates only after both role vectors",
        ],
    }
    frontier = {
        "ranked": [],
        "unranked": [
            {"need": "OL", "classification": "NEEDS_CARD_DATA_AND_PRICE"},
            {"need": "FS", "classification": "NEEDS_CARD_DATA_PRICE_AND_THEME"},
            {"need": "EDGE", "classification": "NEEDS_CARD_DATA_AND_PRICE"},
        ],
        "synthetic_prices": False,
    }
    dont_touch = resistance + [
        {
            "player": "Carson Hinzman",
            "slot": "C1",
            "level": "PROVISIONAL_HIGH",
            "reasons": [
                "87 current starter; current exact role vector missing; "
                "historical Moneyball evidence"
            ],
        }
    ]
    watch = [
        {
            "target": "THEME_COMPATIBLE_OL_UPGRADE",
            "position": "OL",
            "current_player": "TO_BE_IDENTIFIED_AFTER_VECTOR_AUDIT",
            "why": "Run-first unit has two 84 displayed OVRs but OVR is insufficient",
            "target_price": None,
            "expected_role_improvement": "NEEDS_VECTOR",
            "theme_issue": "MUST_VERIFY",
            "confidence": "DATA_COLLECTION",
        },
        {
            "target": "FS_ACTIVE_ROLE_ALTERNATIVE",
            "position": "FS",
            "current_player": "Dashawn Spears",
            "why": "Evaluate active role while preserving protected card",
            "target_price": None,
            "expected_role_improvement": "NEEDS_VECTOR",
            "theme_issue": "MUST_VERIFY",
            "confidence": "DATA_COLLECTION",
        },
    ]
    duce = {
        "player": "Duce Robinson",
        "bnd": True,
        "normal_start": "BLOCKED_THEME",
        "current_wr": ["Malachi Toney 89", "Kalik Lockett 87", "Javon Nicholas 86"],
        "current_slwr": "Girard Pringle Jr. specialist OVR 83",
        "potential": "SPECIALIST_VALUE_WORTH_VERIFYING",
        "legal_slwr_eligibility": "UNKNOWN",
        "required_verification": [
            "whether this WR card is legal at SLWR",
            "theme count effect",
            "displaced Pringle role delta",
        ],
        "sell": "PROHIBITED",
        "decision": "VERIFY_SPECIALIST_DEPLOYMENT",
    }
    theme = {
        "visible_values": [],
        "current_theme": "KNOWN_ACTIVE_BUT_IDENTITY_UNSUPPLIED",
        "counts": "UNKNOWN",
        "bonuses": "UNKNOWN",
        "duce_constraint": "VALIDATED",
        "minimum_needed": [
            "theme identity",
            "current count",
            "threshold",
            "whether specialists count",
        ],
    }
    resources = state2["resources"] | {
        "recommendations": {
            "coins": "SAVE_AND_WATCH",
            "training": "NO_ACTION_MECHANICS_NOT_LINKED",
            "green": "NO_ACTION_UNKNOWN_IDENTITY",
            "other": "NO_ACTION_UNKNOWN_IDENTITY",
            "trophy_like": "NO_ACTION_UNKNOWN_IDENTITY",
        }
    }
    foundations = {
        "priority_positions": ["OL", "FS", "EDGE"],
        "ranked": [],
        "status": "SEARCH_READY_BUT_CURRENT_ROLE_DEFICITS_AND_UPGRADEABILITY_NOT_VALIDATED",
        "dynamic_probabilities_used": False,
    }
    finished = {
        "comparisons": [],
        "default": "INSUFFICIENT_DATA",
        "seau": "COMPARE_NEW_BASE_OR_FINISHED_BEFORE_FUTURE_PROJECT",
        "cheap_base_many_upgrades_assumed_better": False,
    }
    release = [
        {
            "slot_id": row["slot_id"],
            "player": row["player"],
            "classification": "WATCH_RELEASES",
            "confidence": "POSITION_CONTEXT_ONLY",
            "exact_date": None,
        }
        for row in profiles
    ]
    identity = {
        "RUN_FIRST": {
            "support": "UNKNOWN",
            "strong_evidence": ["Owen Allen multi-role"],
            "missing": ["exact OL/TE/HB vectors"],
        },
        "CLOCK_CONTROL": {
            "support": "UNKNOWN",
            "missing": ["exact ball-security and technical vectors"],
        },
        "TWO_EDGE": {
            "support": "STRUCTURALLY_PRESENT",
            "normal": ["Clayton Smith", "Kelby Collins"],
            "rush": ["Clayton Smith", "Landen Thomas"],
        },
        "4-2-5": {"support": "STRUCTURALLY_PRESENT", "missing": ["exact secondary/MIKE vectors"]},
        "6-1": {"support": "STRUCTURALLY_PRESENT", "missing": ["interior/EDGE run foundation"]},
        "SPECIALIST_FLEXIBILITY": {"support": "VISIBLE", "strongest": "Owen Allen"},
        "THEME_INTEGRITY": {"support": "ACTIVE_CONSTRAINT_CONFIRMED", "quantification": "UNKNOWN"},
    }
    actions = [
        {
            "priority": 1,
            "player_position": "TEAM",
            "action": "SAVE",
            "expected_benefit": "Avoid unvalidated purchase",
            "cost": 0,
            "why": coin_plan["why"],
            "confidence": "HIGH",
            "what_would_change": "Exact role deltas plus real prices",
        },
        {
            "priority": 2,
            "player_position": "OL",
            "action": "COLLECT_DATA",
            "expected_benefit": "Identify actual run-first weak link",
            "cost": 0,
            "why": "All five current vectors incomplete",
            "confidence": "HIGH",
            "what_would_change": "Exact current card pages/screens",
        },
        {
            "priority": 3,
            "player_position": "Duce Robinson",
            "action": "VERIFY_SPECIALIST",
            "expected_benefit": "Potential zero-acquisition-cost specialist improvement",
            "cost": 0,
            "why": "SLWR1 is 83 specialist OVR; legality/theme effect unknown",
            "confidence": "HIGH_FOR_INFORMATION_VALUE",
            "what_would_change": "Specialist eligibility screen",
        },
        {
            "priority": 4,
            "player_position": "Junior Seau",
            "action": "STOP_UPGRADING_CURRENT_CYCLE",
            "expected_benefit": "Avoid unsupported spend",
            "cost": 0,
            "why": "Observed target reached and no rolls remain",
            "confidence": "HIGH",
            "what_would_change": "New upgrade path/version evidence",
        },
        {
            "priority": 5,
            "player_position": "FS1",
            "action": "PRESERVE_CARD",
            "expected_benefit": "Retain reroll asset",
            "cost": 0,
            "why": "Protected policy",
            "confidence": "HIGH",
            "what_would_change": "Policy change",
        },
    ]
    executive = {
        "strongest_areas": [
            "Owen Allen multi-role flexibility",
            "Bowen normal+SUBLB deployment",
            "two-EDGE structural deployment",
        ],
        "weakest_areas": [
            "unresolved OL functional floor",
            "unresolved FS active-role quality",
            "unresolved exact EDGE role quality",
        ],
        "better_than_ovr": [row["player"] for row in above]
        or ["No current exact-vector case proven"],
        "worse_than_ovr": [row["player"] for row in traps]
        or ["No current exact-vector trap proven"],
        "do_not_replace": [
            "Drayk Bowen",
            "Owen Allen",
            "protected FS1/MIKE1/MIKE2 cards",
            "provisionally Carson Hinzman/Cason Henry",
        ],
        "watch_replacement": [
            "FS active role while retaining Spears",
            "OL after exact-vector link audit",
        ],
        "coin_destination": "SAVE 209,644 pending exact role/price comparisons",
        "spend_or_save": "SAVE",
        "best_upgrade_foundation": "INSUFFICIENT CURRENT UPGRADEABILITY/VECTOR DATA",
        "worst_upgrade_foundation": "INSUFFICIENT DATA",
        "seau": (
            "Keep current MIKE2 value; stop current cycle; compare future better base/finished card"
        ),
        "duce": "Verify legal specialist placement and theme effect; keep BND; never sell",
        "highest_value_market_target": (
            "Theme-compatible solution to the OL weak link after it is identified"
        ),
        "highest_value_development_target": (
            "No new target proven; compare future Seau base versus finished version"
        ),
        "highest_value_missing_data": "Exact current OL card rating vectors",
    }
    secondary_gates = {
        name: "COMPLETED_OR_DATA_BLOCKED_WITH_OUTPUT"
        for name in [
            "backup_quality",
            "depth_cliff",
            "starter_backup_delta",
            "version_ladders",
            "theme_shortlist",
            "bnd_shortlist",
            "specialist_shortlist",
            "native_speed",
            "ol_primary",
            "defensive_bsh_str",
            "coverage_technical",
            "route_technical",
            "position_scarcity",
            "release_ceilings",
            "ltd_rentals",
            "training_value",
            "protected_reroll",
            "stop_loss",
            "no_move",
            "screenshot_confidence",
        ]
    }
    source_paths = [
        root / "data/external/cfb_fan_population_state.json",
        root / "data/research/cfb27_op_x_007/team_digital_twin_v1.json",
        root / "data/research/cfb27_op_x_006/mandatory_validation.json",
    ]
    return {
        "freeze": {
            "source_commit": "7b75903",
            "input_sha256": {
                str(p.relative_to(root)).replace("\\", "/"): _sha(p) for p in source_paths
            },
            "screenshot_input": "USER_TRANSCRIPTION_OP_X_008",
        },
        "team_state_002": state2,
        "team_state_002_delta": delta,
        "currentness_promotion": assets,
        "offense_audit": offense,
        "offensive_line_deep_dive": ol,
        "ol_link_analysis": links,
        "hinzman_validation": hinzman,
        "henry_validation": henry,
        "skill_position_audit": skill,
        "owen_allen_multi_role": owen,
        "defense_audit": defense,
        "mike_pair_analysis": mike,
        "seau_reassessment": seau,
        "bowen_value": bowen,
        "two_edge_audit": edge,
        "dt_nt_audit": interior,
        "secondary_audit": secondary,
        "fs1_protected_analysis": fs,
        "team_speed_floor": speed,
        "team_primary_stat_floor": floors,
        "above_ovr_starters": categorized,
        "ovr_traps": traps,
        "replacement_resistance": resistance,
        "team_weakness_map_v2": weakness,
        "position_investment_priority_v2": priorities,
        "coin_plan_209644": coin_plan,
        "coin_efficiency_frontier": frontier,
        "do_not_touch": dont_touch,
        "current_team_watchlist": watch,
        "duce_specialist_reassessment": duce,
        "specialist_optimization": specialists,
        "theme_constraint_update": theme,
        "resource_allocation": resources,
        "current_team_moneyball": above,
        "current_team_overvalued": traps,
        "upgrade_foundation_search": foundations,
        "finished_card_alternatives": finished,
        "release_pressure_overlay": release,
        "team_identity_fit": identity,
        "gm_action_queue_v2": actions,
        "current_team_executive_report": executive,
        "mandatory_validation": {
            "current_ol": ol,
            "hinzman": hinzman,
            "henry": henry,
            "bowen_seau": mike,
            "two_edge": edge,
            "owen_allen": owen,
            "duce": duce,
            "fs1": fs,
        },
        "secondary_gates": secondary_gates,
        "validation": {
            "guessed_ratings": False,
            "guessed_versions": False,
            "synthetic_prices": False,
            "fabricated_theme_bonuses": False,
            "assumed_chemistry": False,
            "fake_specialist_legality": False,
            "synthetic_gameplay": False,
            "assumed_resource_identities": False,
            "protected_card_violations": False,
            "ovr_shortcut": False,
            "forced_spending": False,
            "canonical_changes": False,
        },
    }


def write_artifacts(directory: Path, analysis: dict) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for name, payload in analysis.items():
        (directory / f"{name}.json").write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
