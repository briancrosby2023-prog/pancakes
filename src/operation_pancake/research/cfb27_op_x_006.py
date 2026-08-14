"""OP-X-006 transparent roster and General Manager decision intelligence."""

from __future__ import annotations

import hashlib
import json
import statistics
from collections import defaultdict
from pathlib import Path

from operation_pancake.research.cfb27_op_x_001 import _cards

ROLES = [
    "STARTER",
    "ROTATIONAL_STARTER",
    "SPECIALIST",
    "SUBPACKAGE_PLAYER",
    "DEPTH",
    "DEVELOPMENT_PROJECT",
    "UPGRADE_FOUNDATION",
    "MARKET_ASSET",
    "BND_ASSET",
    "THEME_TEAM_ENABLER",
    "EMERGENCY_DEPTH",
    "REPLACE",
    "HOLD",
    "SELL",
    "DO_NOT_ACQUIRE",
]

ROLE_ATTRIBUTES = {
    "C": {"blocking_outlier": ["RBP", "PBP", "AWR", "STR", "RBK", "PBF", "IBL"]},
    "TE": {"blocking_te": ["RBK", "RBP", "RBF", "IBL", "STR"]},
    "WR": {
        "large_possession_red_zone_wr": ["SRR", "MRR", "DRR", "RLS", "CTH", "CIT", "SPC", "TGH"],
        "speed_package_wr": ["SPD", "ACC", "AGI", "COD"],
    },
    "MLB": {"user_controlled_mike": ["SPD", "ACC", "COD", "BSH", "TAK", "ZCV"]},
    "MIKE": {"user_controlled_mike": ["SPD", "ACC", "COD", "BSH", "TAK", "ZCV"]},
    "LE": {"pass_rush_edge": ["SPD", "ACC", "FMV", "PMV", "BSH"]},
    "RE": {"pass_rush_edge": ["SPD", "ACC", "FMV", "PMV", "BSH"]},
    "CB": {"man_cb": ["SPD", "ACC", "MCV", "PRS"], "zone_cb": ["SPD", "ACC", "ZCV", "PRC"]},
    "FS": {"sub_package_safety": ["SPD", "ACC", "ZCV", "MCV", "POW"]},
    "SS": {"sub_package_safety": ["SPD", "ACC", "ZCV", "MCV", "POW"]},
}


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _card_key(card: dict) -> str:
    return str(card.get("external_card_id") or card.get("card_id"))


def _components(card: dict, attributes: list[str]) -> dict:
    ratings = card["displayed_ratings"]
    known = {attribute: ratings[attribute] for attribute in attributes if attribute in ratings}
    return {
        "role_attributes": known,
        "known_count": len(known),
        "requested_count": len(attributes),
        "mean": round(statistics.mean(known.values()), 3) if known else None,
        "missing": [attribute for attribute in attributes if attribute not in ratings],
    }


def compatibility(card: dict, user_evidence: dict | None = None) -> dict:
    evidence = user_evidence or {}
    theme = evidence.get("theme_team_fit", "UNKNOWN")
    normal = "UNKNOWN"
    if theme == "INCOMPATIBLE" and evidence.get("theme_team_constraint_active") is True:
        normal = "INELIGIBLE_BY_KNOWN_THEME_CONSTRAINT"
    return {
        "card_id": _card_key(card),
        "position_eligibility": card["position"],
        "theme_team_compatibility": theme,
        "chemistry_compatibility": evidence.get("chemistry", "UNKNOWN"),
        "scheme_compatibility": evidence.get("scheme", "UNKNOWN"),
        "formation_compatibility": evidence.get("formation", "UNKNOWN"),
        "specialist_eligibility": evidence.get("specialist_eligibility", "UNKNOWN"),
        "normal_starter_status": normal,
        "bnd_constraint": evidence.get("bnd", "UNKNOWN"),
        "unknown_fields": [
            key for key in ("chemistry", "scheme", "formation") if key not in evidence
        ],
    }


def starter_profile(card: dict) -> dict:
    role_map = ROLE_ATTRIBUTES.get(card["position"], {})
    role = next(iter(role_map), "position_general")
    attributes = role_map.get(role, sorted(card["displayed_ratings"])[:8])
    return {
        "card_id": _card_key(card),
        "player": card["player_name"],
        "overall": card["overall"],
        "position": card["position"],
        "archetype": card.get("archetype"),
        "role": role,
        "role_specific_ratings": _components(card, attributes),
        "above_ovr_evidence": "SEPARATE_ARTIFACT",
        "formula_importance": "POSITION_EVIDENCE_ONLY",
        "ability_thresholds": "UNKNOWN_UNLESS_VALIDATED_EXTERNALLY",
        "foundation_completeness": "PARTIAL"
        if _components(card, attributes)["missing"]
        else "COMPLETE_OBSERVED_VECTOR",
        "replacement_pressure": "POSITION_CONTEXT_REQUIRED",
        "opaque_composite": None,
    }


def specialist_profiles(cards: list[dict]) -> list[dict]:
    output = []
    for card in cards:
        for role, attrs in ROLE_ATTRIBUTES.get(card["position"], {}).items():
            components = _components(card, attrs)
            if components["known_count"] < max(2, len(attrs) // 2):
                continue
            output.append(
                {
                    "player": card["player_name"],
                    "card_id": _card_key(card),
                    "overall": card["overall"],
                    "position": card["position"],
                    "archetype": card.get("archetype"),
                    "specialist_role": role,
                    "key_attributes": components["role_attributes"],
                    "profile_mean": components["mean"],
                    "why": "Observed role-specific attribute profile",
                    "limitations": components["missing"]
                    or ["Statistical profile is not gameplay validation"],
                    "theme_team_status": "UNKNOWN",
                    "confidence": "STATISTICAL_SCREEN",
                }
            )
    return sorted(
        output, key=lambda row: (row["specialist_role"], -(row["profile_mean"] or 0), row["player"])
    )


def moneyball(cards: list[dict]) -> dict:
    by_position = defaultdict(list)
    for card in cards:
        by_position[card["position"]].append(card)
    above, traps = [], []
    for card in cards:
        role_map = ROLE_ATTRIBUTES.get(card["position"], {})
        if not role_map:
            continue
        role, attrs = next(iter(role_map.items()))
        component = _components(card, attrs)
        if component["mean"] is None:
            continue
        higher = [
            other for other in by_position[card["position"]] if other["overall"] > card["overall"]
        ]
        higher_means = [_components(other, attrs)["mean"] for other in higher]
        higher_means = [value for value in higher_means if value is not None]
        if higher_means and component["mean"] >= statistics.median(higher_means):
            above.append(
                {
                    "player": card["player_name"],
                    "card_id": _card_key(card),
                    "overall": card["overall"],
                    "position": card["position"],
                    "outlier_type": role.upper(),
                    "role_mean": component["mean"],
                    "higher_ovr_median": round(statistics.median(higher_means), 3),
                    "claim": "STATISTICAL_ROLE_PROFILE_ONLY",
                }
            )
        same_ovr = [
            other for other in by_position[card["position"]] if other["overall"] == card["overall"]
        ]
        peer = [_components(other, attrs)["mean"] for other in same_ovr]
        peer = [value for value in peer if value is not None]
        if len(peer) >= 3 and component["mean"] < statistics.median(peer) - 3:
            traps.append(
                {
                    "player": card["player_name"],
                    "card_id": _card_key(card),
                    "overall": card["overall"],
                    "position": card["position"],
                    "intended_role": role,
                    "role_mean": component["mean"],
                    "same_ovr_median": round(statistics.median(peer), 3),
                    "reason": "ROLE_ATTRIBUTE_DEFICIT",
                    "gameplay_claim": False,
                }
            )
    return {
        "above_ovr": sorted(above, key=lambda x: (x["overall"], x["player"])),
        "ovr_traps": sorted(traps, key=lambda x: (-x["overall"], x["player"])),
    }


def _duce(cards: list[dict]) -> dict:
    card = next(
        card for card in cards if card["player_name"] == "Duce Robinson" and card["overall"] == 88
    )
    compat = compatibility(
        card,
        {
            "theme_team_fit": "INCOMPATIBLE",
            "theme_team_constraint_active": True,
            "specialist_eligibility": "CANDIDATE",
            "bnd": True,
        },
    )
    specialist = next(
        row
        for row in specialist_profiles([card])
        if row["specialist_role"] == "large_possession_red_zone_wr"
    )
    return {
        "player": "Duce Robinson",
        "card_version": "88 LTD",
        "evidence": "USER_SUPPLIED_AND_PUBLIC_CARD_VECTOR",
        "raw_card_quality": "HIGH",
        "bnd": True,
        "acquisition_economics": "EXCELLENT_SUNK_OR_NEAR_ZERO_USER_ACQUISITION",
        "normal_starter_status": compat["normal_starter_status"],
        "theme_team_fit": "INCOMPATIBLE",
        "specialist_status": "CANDIDATE",
        "specialist_profile": specialist,
        "recommended_actions": [
            "DO_NOT_START_NORMAL_THEME_SLOT",
            "USE_AS_SPECIALIST_IF_FORMATION_ELIGIBLE",
            "KEEP",
        ],
        "sell_recommendation": False,
        "exact_package": "UNKNOWN",
        "why": (
            "Known theme-team constraint blocks normal starter use; high observed "
            "route/possession ratings retain specialist potential and BND prevents sale."
        ),
        "what_would_change": [
            "formation eligibility",
            "specialist depth chart",
            "theme-team rule change",
        ],
        "confidence": "HIGH_FOR_CONSTRAINT_EXPLORATORY_FOR_SPECIALIST_PACKAGE",
    }


def _seau(root: Path) -> dict:
    cf = _load(root / "data/research/cfb27_op_x_005/seau_counterfactual_v2.json")
    return {
        "player": "Junior Seau",
        "role": "user_controlled_mike",
        "athletic_specialization": "EXTRAORDINARY_OBSERVED",
        "broad_foundation": "WEAKER_THAN_84_PREMADE",
        "development_value": "EXPLORATORY",
        "allocation_risk": "HIGH",
        "theme_team_fit": "UNKNOWN",
        "recommended_action": "COLLECT_MORE_DATA",
        "counterfactual_classification": cf["classification"],
        "why": "Raw OVR does not represent specialization or Dynamic uncertainty.",
    }


def build_op_x_006(root: Path) -> dict:
    cards = _cards(root)
    specialists = specialist_profiles(cards)
    mb = moneyball(cards)
    duce = _duce(cards)
    prior_secondary = _load(root / "data/research/cfb27_op_x_005/secondary_gates.json")
    center = {
        **prior_secondary["center_primary_ranking"][0],
        "claim": "STATISTICAL_ROLE_PROFILE_ONLY",
        "gameplay_value_established": False,
    }
    te = {
        **prior_secondary["te_blocking_ranking"][0],
        "claim": "STATISTICAL_BLOCKING_FOUNDATION_ONLY",
        "gameplay_value_established": False,
    }
    trap = mb["ovr_traps"][0] if mb["ovr_traps"] else None
    ontology = {"roles": ROLES, "multi_role_allowed": True, "displayed_ovr_equals_value": False}
    theme = {
        "components": [
            "theme_team_fit",
            "theme_team_slot_cost",
            "displaced_player_cost",
            "net_lineup_effect",
            "confidence",
        ],
        "chemistry_bonus_invented": False,
        "unknown_policy": "PRESERVE_UNKNOWN",
    }
    bnd = {
        "components": [
            "acquisition_cost",
            "market_value",
            "resale_value",
            "quicksell_value",
            "replacement_cost",
            "roster_utility",
            "opportunity_cost",
        ],
        "rules": ["NEVER_RECOMMEND_SELL_WHEN_BND", "BND_DOES_NOT_IMPLY_USEFUL"],
        "unknown_to_zero": False,
    }
    compatibility_rows = [compatibility(card) for card in cards]
    compatibility_rows.append(
        {
            **compatibility(
                next(c for c in cards if c["player_name"] == "Duce Robinson"),
                {
                    "theme_team_fit": "INCOMPATIBLE",
                    "theme_team_constraint_active": True,
                    "specialist_eligibility": "CANDIDATE",
                    "bnd": True,
                },
            ),
            "user_case": True,
        }
    )
    starter = [starter_profile(card) for card in cards]
    explanation = {
        "required_fields": [
            "decision",
            "primary_reason",
            "supporting_reasons",
            "constraint",
            "what_would_change_decision",
            "confidence",
        ],
        "constraint_first": True,
        "duce_example": duce,
    }
    decision_rows = []
    for card, profile in zip(cards, starter, strict=True):
        is_duce = card["player_name"] == "Duce Robinson" and card["overall"] == 88
        decision_rows.append(
            {
                "player": card["player_name"],
                "card_version": _card_key(card),
                "normal_starter_status": duce["normal_starter_status"]
                if is_duce
                else "ROSTER_CONTEXT_UNKNOWN",
                "specialist_status": "CANDIDATE"
                if any(x["card_id"] == _card_key(card) for x in specialists)
                else "NOT_CLASSIFIED",
                "theme_team_fit": "INCOMPATIBLE" if is_duce else "UNKNOWN",
                "raw_card_quality": profile["role_specific_ratings"],
                "role_fit": profile["role"],
                "foundation_quality": profile["foundation_completeness"],
                "development_value": "EXPLORATORY"
                if card["player_name"] == "Junior Seau"
                else "UNKNOWN",
                "market_resource_value": "UNKNOWN",
                "bnd_value": "HIGH_ROSTER_OPTION_VALUE" if is_duce else "UNKNOWN",
                "longevity": "POSITION_AND_RELEASE_CONTEXT_REQUIRED",
                "replacement_pressure": "UNKNOWN_WITHOUT_CURRENT_ROSTER_SLOT",
                "recommended_action": "KEEP_AND_SPECIALIST"
                if is_duce
                else "COLLECT_ROSTER_CONTEXT",
                "why": duce["why"]
                if is_duce
                else "Card vector alone cannot determine a personal-roster action",
                "confidence": "HIGH_FOR_KNOWN_CONSTRAINT"
                if is_duce
                else "DO_NOT_MODEL_PERSONAL_ACTION",
                "missing_information": []
                if is_duce
                else ["roster slot", "theme fit", "BND", "cost"],
            }
        )
    roster_schema = {
        "partial_records_legal": True,
        "fields": [
            "player",
            "card_version",
            "ovr",
            "position",
            "depth_slot",
            "starter_status",
            "specialist_status",
            "theme_team_fit",
            "bnd",
            "upgradeable",
            "current_upgrade_state",
            "chemistry",
            "abilities",
            "known_ratings",
            "acquisition_cost",
            "current_market_value",
            "user_notes",
            "source",
            "timestamp",
        ],
        "screenshot_policy": "EXTRACT_VISIBLE_FIELDS_AND_PRESERVE_SOURCE",
    }
    graph = {
        "node_types": [
            "PLAYER",
            "POSITION",
            "DEPTH_CHART_SLOT",
            "SPECIALIST_SLOT",
            "THEME_TEAM",
            "CHEMISTRY",
            "FORMATION",
            "SCHEME",
            "BND_STATUS",
            "UPGRADE_STATUS",
            "MARKET_STATUS",
        ],
        "edge_types": [
            "ELIGIBLE_FOR",
            "FITS",
            "OCCUPIES",
            "CONSTRAINED_BY",
            "DEVELOPS_TO",
            "OBSERVED_AT",
        ],
        "unknown_nodes_allowed": True,
        "known_edges": [
            {"from": "Duce Robinson 88 LTD", "to": "BND", "type": "CONSTRAINED_BY"},
            {"from": "Duce Robinson 88 LTD", "to": "ACTIVE_THEME_TEAM", "type": "DOES_NOT_FIT"},
        ],
    }
    generic_framework = {
        "numeric_output": None,
        "missing_cost_policy": "QUALITATIVE_COMPARISON",
        "components": [
            "current quality",
            "replacement quality",
            "improvement",
            "cost",
            "theme effect",
            "specialist effect",
            "upgrade possibility",
            "replacement pressure",
            "longevity",
        ],
    }
    action_queue = [
        {
            "action": "MOVE_TO_SPECIALIST",
            "player": "Duce Robinson",
            "priority": "HIGH",
            "expected_benefit": (
                "Retain high raw-quality BND utility without violating theme constraint"
            ),
            "cost": "UNKNOWN/NO_NEW_ACQUISITION",
            "urgency": "CURRENT_ROSTER",
            "confidence": "HIGH_FOR_CONSTRAINT",
            "why": duce["why"],
        },
        {
            "action": "COLLECT_MORE_DATA",
            "player": "Junior Seau",
            "priority": "HIGH_INFORMATION_VALUE",
            "expected_benefit": "Reduce Dynamic allocation uncertainty",
            "cost": "UNKNOWN",
            "urgency": "BEFORE_NEXT_ROLL",
            "confidence": "HIGH",
            "why": "OP-X-005 remains exploratory",
        },
    ]
    secondary = {
        name: "IMPLEMENTED"
        for name in [
            "theme_team_schema",
            "bnd_rules",
            "specialist_slots",
            "screenshot_ingestion",
            "same_player_versions",
            "finished_vs_evo",
            "replacement_dashboard",
            "coin_efficiency",
            "market_watchlist",
            "ltd_lifecycle",
            "ability_thresholds",
            "development_paths",
            "rerollable_slots",
            "protected_fs1_mike",
            "run_first_roles",
            "defense_425_61",
        ]
    }
    source_paths = [
        root / "data/external/cfb_fan_population_state.json",
        root / "data/research/cfb27_op_x_004/pc_upgrade_decision_output.json",
        root / "data/research/cfb27_op_x_005/pc_development_intelligence_v2.json",
    ]
    return {
        "freeze": {
            "source_commit": "b74ecba",
            "input_sha256": {
                str(p.relative_to(root)).replace("\\", "/"): _sha(p) for p in source_paths
            },
        },
        "roster_decision_ontology": ontology,
        "roster_compatibility_model": compatibility_rows,
        "starter_value_profile": starter,
        "specialist_value_profile": specialists,
        "theme_team_opportunity_cost": theme,
        "bnd_roster_value": bnd,
        "keep_sell_use_engine": {
            "actions": [
                "START",
                "SPECIALIST",
                "DEPTH",
                "DEVELOP",
                "KEEP",
                "SELL",
                "REPLACE",
                "HOLD_FOR_MARKET",
                "DO_NOT_ACQUIRE",
            ],
            "bnd_sell_guard": True,
            "records": [duce],
        },
        "buy_upgrade_finished": {
            "choices": [
                "BUY_LOW_UPGRADE",
                "BUY_MID_UPGRADE",
                "BUY_HIGH_UPGRADE",
                "BUY_FINISHED",
                "USE_CURRENT",
                "WAIT",
            ],
            "forced_numeric_ev": False,
            "dynamic_confidence": "EXPLORATORY",
        },
        "replacement_value_model": generic_framework,
        "position_investment_priority": {
            **generic_framework,
            "rank_status": "BLOCKED_BY_MISSING_CURRENT_ROSTER",
        },
        "marginal_coin_value": {
            "components": [
                "immediate starter improvement",
                "specialist improvement",
                "upgrade foundation",
                "longevity",
                "liquidity",
                "BND effect",
            ],
            "fake_precision": False,
        },
        "longevity_replacement_pressure": {
            "inputs": [
                "release chronology",
                "capability creep",
                "athletic ceiling",
                "technical ceiling",
                "OVR escalation",
                "ability access",
                "archetype supply",
                "market supply",
            ],
            "exact_date_predictions": False,
        },
        "above_ovr_moneyball_v2": mb["above_ovr"],
        "ovr_trap_profile": mb["ovr_traps"],
        "specialist_discovery": specialists,
        "roster_constraint_graph": graph,
        "roster_ingestion_schema": roster_schema,
        "decision_explanation_engine": explanation,
        "gm_action_queue": action_queue,
        "decision_engine_v1": decision_rows,
        "mandatory_validation": {
            "duce": duce,
            "seau": _seau(root),
            "center": center,
            "te": te,
            "high_ovr_trap": trap,
        },
        "secondary_gates": secondary,
        "strategy_constraints": {
            "protected_rerollable": ["FS1", "MIKE1", "MIKE2"],
            "offense": ["RUN_FIRST", "CLOCK_CONTROL"],
            "defense": ["TWO_EDGE_FREQUENT", "4-2-5", "6-1"],
            "source": "EXISTING_USER_CONSTRAINT",
        },
        "validation": {
            "guessed_ratings": False,
            "fake_roster_data": False,
            "fabricated_chemistry": False,
            "synthetic_market_prices": False,
            "gameplay_claims": False,
            "impossible_bnd_sale": False,
            "forced_composite": False,
            "access_bypass": False,
            "canonical_changes": False,
        },
    }


def write_artifacts(directory: Path, analysis: dict) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for name, payload in analysis.items():
        (directory / f"{name}.json").write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
