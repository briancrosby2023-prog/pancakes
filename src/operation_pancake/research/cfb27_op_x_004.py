"""OP-X-004 upgrade-candidate foundation and specialization intelligence."""

from __future__ import annotations

import hashlib
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path

from operation_pancake.research.cfb27_op_x_001 import _cards
from operation_pancake.research.cfb27_phase6_10 import _card_position

MIKE_ATTRIBUTES = (
    "SPD",
    "ACC",
    "AGI",
    "COD",
    "AWR",
    "STR",
    "JMP",
    "PRC",
    "TGH",
    "FMV",
    "PMV",
    "TAK",
    "POW",
    "PUR",
    "BSH",
    "IBL",
    "MCV",
    "ZCV",
    "PRS",
    "CTH",
    "CIT",
    "SPC",
)
ROLE_CATEGORIES = {
    "ATHLETIC": ("SPD", "ACC", "AGI", "COD", "JMP"),
    "PHYSICAL": ("STR", "TGH", "POW"),
    "TECHNICAL": ("TAK", "PUR", "BSH", "IBL", "FMV", "PMV"),
    "COVERAGE": ("MCV", "ZCV", "PRS", "CTH", "CIT", "SPC"),
    "PROCESSING": ("AWR", "PRC"),
}
PREMADE = {
    84: {
        "SPD": 82,
        "ACC": 82,
        "AGI": 76,
        "COD": 80,
        "AWR": 77,
        "STR": 82,
        "JMP": 80,
        "PRC": 77,
        "TGH": 84,
        "FMV": 77,
        "PMV": 77,
        "TAK": 87,
        "POW": 82,
        "PUR": 82,
        "BSH": 83,
        "IBL": 77,
        "MCV": 81,
        "ZCV": 84,
        "PRS": 78,
        "CTH": 73,
        "CIT": 70,
        "SPC": 70,
    },
    86: {
        "SPD": 84,
        "ACC": 84,
        "AGI": 78,
        "COD": 82,
        "AWR": 79,
        "STR": 84,
        "JMP": 82,
        "PRC": 79,
        "TGH": 86,
        "FMV": 79,
        "PMV": 79,
        "TAK": 89,
        "POW": 84,
        "PUR": 84,
        "BSH": 85,
        "IBL": 79,
        "MCV": 83,
        "ZCV": 86,
        "PRS": 80,
        "CTH": 75,
        "CIT": 72,
        "SPC": 72,
    },
    87: {
        "SPD": 85,
        "ACC": 85,
        "AGI": 79,
        "COD": 83,
        "AWR": 80,
        "STR": 85,
        "JMP": 83,
        "PRC": 80,
        "TGH": 87,
        "FMV": 80,
        "PMV": 80,
        "TAK": 90,
        "POW": 85,
        "PUR": 85,
        "BSH": 86,
        "IBL": 80,
        "MCV": 84,
        "ZCV": 87,
        "PRS": 81,
        "CTH": 76,
        "CIT": 73,
        "SPC": 73,
    },
}
EVO_86 = {
    "SPD": 89,
    "ACC": 88,
    "TAK": 88,
    "MCV": 78,
    "ZCV": 81,
    "PUR": 84,
    "PRS": 82,
    "CTH": 84,
    "POW": 83,
    "AGI": 79,
    "STR": 84,
    "BSH": 82,
    "AWR": 77,
    "IBL": 74,
    "PRC": 76,
    "JMP": 77,
    "COD": 79,
}
EVO_EVENTS = [
    {"ending_ovr": 83, "deltas": {"SPD": 7, "STR": 5, "CTH": 6}},
    {"ending_ovr": 84, "deltas": {"ACC": 3, "POW": 4}},
    {"ending_ovr": 85, "deltas": {"PRS": 7, "ACC": 3, "SPD": 3, "BSH": 2, "AWR": 3}},
    {"ending_ovr": 86, "deltas": {"PUR": 2, "CTH": 8, "PRC": 2, "COD": 2, "AGI": 2}},
]
PRIMARY_POOL = {"ACC", "ZCV", "TAK", "MCV", "SPD", "PUR", "PRS", "CTH"}
SECONDARY_POOL = {"POW", "AGI", "STR", "BSH", "AWR", "IBL", "PRC", "JMP", "COD"}


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _mean(values):
    values = list(values)
    return round(statistics.mean(values), 4) if values else None


def seau_81() -> dict:
    cumulative = Counter()
    for event in EVO_EVENTS:
        cumulative.update(event["deltas"])
    return {attribute: value - cumulative[attribute] for attribute, value in EVO_86.items()}


def seau_evidence() -> dict:
    start = seau_81()
    states = [
        {
            "player": "Junior Seau",
            "position": "MIKE",
            "overall": 81,
            "archetype": "Lurker",
            "program": "EVO START",
            "ratings": start,
            "upgrade_type": "EVO",
            "confidence": "VALIDATED_DERIVED_ARITHMETIC",
            "missing_values": sorted(set(MIKE_ATTRIBUTES) - set(start)),
        },
        *[
            {
                "player": "Junior Seau",
                "position": "MIKE",
                "overall": ovr,
                "archetype": "Lurker",
                "program": "Sunday Spotlight: Retro" + (" LTD" if ovr == 87 else ""),
                "ratings": ratings,
                "upgrade_type": "PREMADE_CARD_PROGRESSION",
                "confidence": "VALIDATED_USER_PRIMARY",
                "missing_values": [],
            }
            for ovr, ratings in PREMADE.items()
        ],
        {
            "player": "Junior Seau",
            "position": "MIKE",
            "overall": 86,
            "archetype": "Lurker",
            "program": "EVO",
            "ratings": EVO_86,
            "upgrade_type": "EVO",
            "confidence": "VALIDATED_USER_PRIMARY",
            "missing_values": sorted(set(MIKE_ATTRIBUTES) - set(EVO_86)),
        },
    ]
    return {
        "states": states,
        "evo_events": [
            {
                **event,
                "upgrade_type": "EVO",
                "development_path": "LURKER",
                "source": "USER_PRIMARY",
                "confidence": "VALIDATED",
            }
            for event in EVO_EVENTS
        ],
        "development_pool": {
            "primary": sorted(PRIMARY_POOL),
            "secondary": sorted(SECONDARY_POOL),
            "selection_probabilities": "UNKNOWN",
            "general_cap": 91,
            "spd_cap": 99,
        },
        "premade_and_evo_merged": False,
    }


def progression_master(root: Path) -> dict:
    chains = _load(root / "data/research/progression_audit/confirmed_progression_chains.json")
    inventory = _load(root / "data/research/progression_audit/progression_inventory.json")
    transitions = inventory["progression_candidates"]
    states = inventory["canonical_cards"]
    seau = seau_evidence()
    pilot = _load(root / "data/research/cfb_fan_controlled_pilot/pilot_report.json")
    pilot_targets = [
        {
            "player": player,
            "observed_ovr_states": overalls,
            "classification": "PARTIAL_DISCOVERY_NO_VALIDATED_VECTORS",
            "source": "CFB_FAN_CONTROLLED_PILOT",
            "missing_values": ["DISPLAYED_RATINGS", "DEVELOPMENT_PATH", "UPGRADE_COST"],
        }
        for player, overalls in sorted(pilot["progression_target_discovery"].items())
    ]
    return {
        "chains": chains,
        "chain_count": len(chains) + 2 + len(pilot_targets),
        "canonical_states": states,
        "seau_states": seau["states"],
        "transitions": transitions,
        "seau_evo_events": seau["evo_events"],
        "pilot_progression_targets": pilot_targets,
        "supporting_historical_artifacts": [
            "data/research/saturday_center_analysis/saturday_reset_linkages.json",
            "data/research/reset_context_audit/reset_sparse_transition_inventory.json",
            "data/research/reset_context_audit/reset_reconstructed_vectors.json",
            "data/research/qb_provenance_audit/qb_confirmed_progression_constraints.json",
        ],
        "counts": {
            "states": len(states) + len(seau["states"]),
            "validated": sum(
                row.get("classification") == "CONFIRMED_PROGRESSION" for row in transitions
            )
            + len(seau["states"])
            + len(EVO_EVENTS),
            "historical": sum(chain["chain_id"].startswith("SAT-") for chain in chains),
            "partial": sum(
                row.get("classification") in {"UNRESOLVED", "PROBABLE_PROGRESSION"}
                for row in transitions
            )
            + len(pilot_targets),
            "missing": sum(bool(row.get("missing_values")) for row in seau["states"]),
        },
        "no_synthetic_vectors": True,
    }


def _percentile(value: int, values: list[int]) -> float | None:
    return round(100 * sum(other <= value for other in values) / len(values), 2) if values else None


def above_ovr(cards: list[dict]) -> list[dict]:
    rows = []
    groups = defaultdict(list)
    for card in cards:
        groups[(_card_position(card), card["archetype"], card["overall"])].append(card)
    for card in cards:
        position = _card_position(card)
        peers = [
            c for c in cards if _card_position(c) == position and c["overall"] == card["overall"]
        ]
        arch_peers = groups[(position, card["archetype"], card["overall"])]
        higher = [
            c for c in cards if _card_position(c) == position and c["overall"] > card["overall"]
        ]
        attrs = {}
        for attribute, value in card["displayed_ratings"].items():
            peer_values = [
                c["displayed_ratings"][attribute]
                for c in peers
                if attribute in c["displayed_ratings"]
            ]
            arch_values = [
                c["displayed_ratings"][attribute]
                for c in arch_peers
                if attribute in c["displayed_ratings"]
            ]
            higher_values = [
                c["displayed_ratings"][attribute]
                for c in higher
                if attribute in c["displayed_ratings"]
            ]
            attrs[attribute] = {
                "position_ovr_residual": round(value - statistics.mean(peer_values), 3)
                if peer_values
                else None,
                "archetype_ovr_residual": round(value - statistics.mean(arch_values), 3)
                if arch_values
                else None,
                "percentile_within_ovr": _percentile(value, peer_values),
                "percentile_within_archetype_ovr": _percentile(value, arch_values),
                "meets_higher_ovr_median": bool(
                    higher_values and value >= statistics.median(higher_values)
                ),
            }
        rows.append(
            {
                "card_id": card["external_card_id"],
                "player": card["player_name"],
                "position": position,
                "overall": card["overall"],
                "archetype": card["archetype"],
                "attributes": attrs,
                "hidden_ovr_claimed": False,
            }
        )
    return rows


def foundation(ratings: dict, target: dict) -> dict:
    categories = {}
    for category, attributes in ROLE_CATEGORIES.items():
        shared = [
            attribute for attribute in attributes if attribute in ratings and attribute in target
        ]
        categories[category] = {
            "attributes": shared,
            "completeness": round(
                statistics.mean(min(ratings[a] / target[a], 1) for a in shared), 4
            )
            if shared
            else None,
            "deficit": sum(max(0, target[a] - ratings[a]) for a in shared),
        }
    shared = [a for a in target if a in ratings]
    return {
        "categories": categories,
        "role_foundation": round(
            statistics.mean(min(ratings[a] / target[a], 1) for a in shared), 4
        ),
        "strengths": [a for a in shared if ratings[a] >= target[a]],
        "weaknesses": [a for a in shared if ratings[a] < target[a]],
        "target": "PREMADE_86_LURKER_REFERENCE",
    }


def seau_foundations() -> dict:
    return {
        "81_EVO_START": foundation(seau_81(), PREMADE[86]),
        "84_PREMADE": foundation(PREMADE[84], PREMADE[86]),
        "86_PREMADE": foundation(PREMADE[86], PREMADE[86]),
        "87_LTD": foundation(PREMADE[87], PREMADE[86]),
        "86_EVO": foundation(EVO_86, PREMADE[86]),
    }


def deficit(ratings: dict, target: dict) -> dict:
    values = {a: max(0, target[a] - ratings[a]) for a in target if a in ratings}
    return {
        "attributes": values,
        "total": sum(values.values()),
        "already_exceeds_target": [a for a in target if a in ratings and ratings[a] > target[a]],
        "unknown": sorted(set(target) - set(ratings)),
        "unknown_as_zero": False,
    }


def opportunity_quality() -> list[dict]:
    rows = []
    for event in EVO_EVENTS:
        for attribute, delta in event["deltas"].items():
            if attribute in {"SPD", "ACC"}:
                classification = "HIGH_VALUE_SPECIALIZATION"
            elif attribute == "CTH":
                classification = "WASTED_FOR_TARGET_ROLE"
            elif attribute in {"BSH", "AWR", "PRC", "COD", "AGI", "STR", "POW", "PUR"}:
                classification = "HIGH_VALUE_FOUNDATION_REPAIR"
            else:
                classification = "UNKNOWN"
            rows.append(
                {
                    "ending_ovr": event["ending_ovr"],
                    "attribute": attribute,
                    "delta": delta,
                    "pool": "PRIMARY" if attribute in PRIMARY_POOL else "SECONDARY",
                    "classification": classification,
                    "target_role": "MAXIMUM_SPEED_MIKE",
                    "threshold_interaction": "NOT_EVALUATED_WITHOUT_STATE_VECTOR",
                    "cap_interaction": "SPD_CAP_99"
                    if attribute == "SPD"
                    else "GENERAL_VISIBLE_CAP_91",
                    "resource_cost": None,
                    "uncertainty": "ROLE_PRIORITY_NOT_GAMEPLAY_WEIGHT",
                }
            )
    return rows


def concentration(deltas: dict) -> dict:
    total = sum(deltas.values())
    shares = sorted((value / total for value in deltas.values()), reverse=True)
    hhi = sum(share**2 for share in shares)
    classification = (
        "EXTREME_SPECIALIZATION"
        if hhi >= 0.25
        else "SPECIALIZED_DEVELOPMENT"
        if hhi >= 0.12
        else "MIXED_DEVELOPMENT"
        if hhi >= 0.07
        else "BROAD_DEVELOPMENT"
    )
    return {
        "attributes_changed": len(deltas),
        "total_points": total,
        "hhi": round(hhi, 4),
        "top_3_share": round(sum(shares[:3]), 4),
        "largest_gain": max(deltas.values()),
        "classification": classification,
    }


def seau_validation() -> dict:
    start = seau_81()
    quality = opportunity_quality()
    cumulative = Counter()
    for event in EVO_EVENTS:
        cumulative.update(event["deltas"])
    actual_deficit = deficit(EVO_86, PREMADE[86])
    premade_delta = {a: PREMADE[86][a] - PREMADE[84][a] for a in PREMADE[84]}
    return {
        "classification": "INSUFFICIENT_EVIDENCE",
        "confidence": "MODERATE",
        "why": (
            "81 produced validated extreme athletic specialization, while 84 purchases a "
            "substantially broader foundation; no validated 84-EVO outcome distribution "
            "or resource-cost history proves which final role value dominates."
        ),
        "start_81": {
            "ratings": start,
            "foundation": foundation(start, PREMADE[86]),
            "deficit": deficit(start, PREMADE[86]),
            "remaining_opportunities": 4,
            "acquisition_cost_observation": 15500,
        },
        "start_84": {
            "ratings": PREMADE[84],
            "foundation": foundation(PREMADE[84], PREMADE[86]),
            "deficit": deficit(PREMADE[84], PREMADE[86]),
            "counterfactual_opportunities_to_86": 2,
            "acquisition_cost_observation": 50000,
        },
        "actual_81_to_86": {
            "final": EVO_86,
            "cumulative_deltas": dict(cumulative),
            "specialization_points": sum(
                row["delta"]
                for row in quality
                if row["classification"] == "HIGH_VALUE_SPECIALIZATION"
            ),
            "foundation_repair_points": sum(
                row["delta"]
                for row in quality
                if row["classification"] == "HIGH_VALUE_FOUNDATION_REPAIR"
            ),
            "wasted_for_target_role_points": sum(
                row["delta"] for row in quality if row["classification"] == "WASTED_FOR_TARGET_ROLE"
            ),
            "remaining_deficit_vs_premade_86": actual_deficit,
        },
        "counterfactual_84_range": {
            "exact_final_ratings": None,
            "speed_floor_if_no_speed_selection": {"SPD": 82, "ACC": 82},
            "observed-event-grounded_ceiling_per_two_opportunities": {"SPD": 92, "ACC": 88},
            "probabilities": None,
            "sufficient_for_89_88": "POSSIBLE_BUT_NOT_ESTABLISHED",
            "synthetic_vector": False,
        },
        "premade_86": {"ratings": PREMADE[86], "acquisition_cost_observation": 166000},
        "ltd_87": {"ratings": PREMADE[87], "cost": None},
        "resource_difference_81_to_84": 34500,
        "cost_justification": "UNKNOWN_WITHOUT_TIMESTAMP_AND_UPGRADE_RESOURCE_COSTS",
        "opportunity_paradox": "SUPPORTED_AS_PLAUSIBLE_NOT_PROVEN_OPTIMUM",
        "premade_concentration": concentration(premade_delta),
        "evo_concentration": concentration(dict(cumulative)),
    }


def projection_and_engine() -> dict:
    validation = seau_validation()
    return {
        "projected_final_role_profile": {
            "81_ACTUAL": {"status": "OBSERVED", "ratings": EVO_86},
            "84_COUNTERFACTUAL": {
                "status": "MODELED_RANGE",
                "ratings": None,
                "speed_range": {"SPD": [82, 92], "ACC": [82, 88]},
                "technical_floor": "PREMADE_84_FOUNDATION",
                "confidence": "LOW",
            },
        },
        "expected_final_value_range": "NOT_COLLAPSED_TO_OPAQUE_SCORE",
        "optimal_starting_ovr": {
            "best_starting_ovr": None,
            "classification": "INSUFFICIENT_EVIDENCE",
            "alternative_starts": [81, 84, 86, 87],
            "why": validation["why"],
            "structurally_can_recommend_higher": True,
        },
        "starting_card_path": {
            "dimensions": [
                "STARTING_CARD",
                "STARTING_OVR",
                "DEVELOPMENT_PATH",
                "UPGRADE_OUTCOMES",
                "FINAL_ROLE",
            ],
            "MIKE": {
                "LURKER": "PARTIAL_OBSERVED",
                "SIGNAL_CALLER": "PATH_MECHANICS_UNKNOWN",
                "THUMPER": "PATH_MECHANICS_UNKNOWN",
            },
            "forced_path_mapping": False,
        },
    }


def prospective(cards: list[dict], foundations: list[dict]) -> list[dict]:
    by_id = {row["card_id"]: row for row in foundations}
    rows = []
    for card in cards:
        profile = by_id[card["external_card_id"]]
        above = [a for a, v in profile["attributes"].items() if v["meets_higher_ovr_median"]]
        classification = "GOOD_CARD_NOW" if len(above) >= 5 else "INSUFFICIENT_UPGRADE_INFORMATION"
        rows.append(
            {
                "player": card["player_name"],
                "starting_card": card["external_card_id"],
                "starting_ovr": card["overall"],
                "development_path": None,
                "current_role_value": "DESCRIPTIVE_FOUNDATION_ONLY",
                "foundation_completeness": None,
                "foundation_strengths": above,
                "foundation_weaknesses": [],
                "above_ovr_attributes": above,
                "starting_deficit": None,
                "specialization_headroom": "UNKNOWN_WITHOUT_PATH_CAPS",
                "foundation_repair_burden": "UNKNOWN_WITHOUT_TARGET",
                "remaining_opportunities": None,
                "expected_useful_opportunities": None,
                "allocation_risk": "UNKNOWN",
                "waste_risk": "UNKNOWN",
                "projected_final_profile": None,
                "best_starting_ovr": None,
                "best_starting_path": None,
                "alternative_starts": [],
                "resource_cost": None,
                "upgrade_confidence": "LOW",
                "recommendation": classification,
                "why": "Population foundation signal available; upgrade mechanics unavailable.",
                "failure_risks": [
                    "INSUFFICIENT_CONTROL",
                    "WRONG_ATTRIBUTE_POOL",
                    "UPGRADE_ALLOCATION_RISK",
                ],
                "evidence": ["CFB27_FROZEN_POPULATION"],
            }
        )
    return sorted(rows, key=lambda row: (-len(row["above_ovr_attributes"]), row["starting_card"]))


def historical_sample() -> dict:
    return {
        "method": "ORDINARY_PUBLIC_HTML_PAGE_1",
        "retrieval_date": "2026-08-13",
        "CFB26": [
            {
                "card_id": "26-620026419",
                "player": "Tiki Barber",
                "overall": 99,
                "position": "HB",
                "archetype": "East/West Playmaker",
                "program": "Graduation",
                "ratings": {"SPD": 99, "CAR": 96, "COD": 98, "TRK": 89, "BTK": 97},
            },
            {
                "card_id": "26-620020791",
                "player": "Mekhi Mason",
                "overall": 99,
                "position": "MIKE",
                "archetype": "Thumper",
                "program": "Graduation",
                "ratings": {"SPD": 98, "ACC": 98, "TAK": 99, "POW": 96, "ZCV": 93},
            },
            {
                "card_id": "26-630026532",
                "player": "Heath Miller",
                "overall": 99,
                "position": "TE",
                "archetype": "Gritty Possession",
                "program": "Ultimate Rewind",
                "ratings": {"SPD": 97, "CTH": 99, "SRR": 99, "MRR": 98, "RBK": 93},
            },
        ],
        "CFB25": [
            {
                "card_id": "25-58025822",
                "player": "Jace Amaro",
                "overall": 99,
                "position": "TE",
                "archetype": "Vertical Threat",
                "program": "Graduation",
                "ratings": {"SPD": 97, "CTH": 97, "SRR": 92, "MRR": 95, "RBK": 90},
            },
            {
                "card_id": "25-58025943",
                "player": "Paul Posluszny",
                "overall": 99,
                "position": "MLB",
                "archetype": "Field General",
                "program": "Graduation",
                "ratings": {"SPD": 96, "ACC": 97, "TAK": 99, "POW": 90, "ZCV": 95},
            },
            {
                "card_id": "25-58023358",
                "player": "Ben Scott",
                "overall": 99,
                "position": "C",
                "archetype": "Power",
                "program": "Graduation",
                "ratings": {"STR": 99, "PBK": 95, "RBK": 99, "RBP": 99, "RBF": 99},
            },
        ],
        "pagination": {"CFB26_pages": 676, "CFB25_pages": 693, "cards_per_page": 15},
        "blocker": (
            "No public bulk export; exhaustive ordinary pagination requires 1,369 "
            "requests and rate-limited resumable acquisition beyond this sprint."
        ),
        "access_bypass": False,
    }


def secondary(root: Path, cards: list[dict], above: list[dict]) -> dict:
    center = [row for row in above if row["position"] == "C"]
    te = [row for row in above if row["position"] == "TE"]
    market = [
        {"player": "Junior Seau", "overall": 81, "display_price": 15500},
        {"player": "Junior Seau", "overall": 84, "display_price": 50000},
        {"player": "Junior Seau", "overall": 86, "display_price": 166000},
    ]
    return {
        "historical_acquisition": historical_sample(),
        "market_collection": {
            "observations": market,
            "semantics": "USER_SUPPLIED_APPROXIMATE_TIMESTAMP_UNSPECIFIED_DISPLAY_PRICE",
            "sale_claimed": False,
        },
        "center_retrospective": sorted(
            center,
            key=lambda r: -sum(v["meets_higher_ovr_median"] for v in r["attributes"].values()),
        )[:10],
        "te_retrospective": sorted(
            te, key=lambda r: -sum(v["meets_higher_ovr_median"] for v in r["attributes"].values())
        )[:10],
        "resource_economics": {
            "observations": market,
            "upgrade_resource_costs": None,
            "universal_market_value_claimed": False,
        },
        "upgrade_concentration": {
            "premade_84_86": seau_validation()["premade_concentration"],
            "evo_81_86": seau_validation()["evo_concentration"],
        },
    }


def failure_taxonomy() -> list[dict]:
    names = [
        "TOO_LOW_STARTING_OVR",
        "TOO_LARGE_STARTING_DEFICIT",
        "TOO_HIGH_STARTING_OVR",
        "INSUFFICIENT_SPECIALIZATION_HEADROOM",
        "TOO_MANY_LOW_VALUE_OPPORTUNITIES",
        "RNG_DEPENDENCE",
        "UPGRADE_ALLOCATION_RISK",
        "WRONG_ATTRIBUTE_POOL",
        "CAP_LIMITATION",
        "ARCHETYPE_MISMATCH",
        "PATH_MISMATCH",
        "THRESHOLD_MISS",
        "REDUNDANT_UPGRADES",
        "HIGH_RESOURCE_COST",
        "FINAL_BUILD_BELOW_MARKET_ALTERNATIVE",
        "INSUFFICIENT_CONTROL",
        "FOUNDATION_REPAIR_OVERLOAD",
    ]
    seau = {
        "TOO_LOW_STARTING_OVR",
        "TOO_LARGE_STARTING_DEFICIT",
        "TOO_MANY_LOW_VALUE_OPPORTUNITIES",
        "RNG_DEPENDENCE",
        "UPGRADE_ALLOCATION_RISK",
        "FOUNDATION_REPAIR_OVERLOAD",
        "INSUFFICIENT_CONTROL",
    }
    return [
        {
            "failure_mode": name,
            "seau_relevance": "PLAUSIBLE" if name in seau else "NOT_ESTABLISHED",
            "validated_failure": False,
        }
        for name in names
    ]


def build_op_x_004(root: Path) -> dict:
    cards = _cards(root)
    above = above_ovr(cards)
    seau = seau_validation()
    projection = projection_and_engine()
    inputs = [
        root / "data/external/cfb_fan_population_state.json",
        root / "data/research/progression_audit/progression_inventory.json",
        root / "data/research/cfb27_op_x_003/freeze.json",
    ]
    return {
        "freeze": {
            "source_commit": "894665b",
            "input_sha256": {
                p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in inputs
            },
        },
        "upgrade_progression_master_v1": progression_master(root),
        "seau_primary_evidence": seau_evidence(),
        "above_ovr_foundation_profile": above,
        "foundation_completeness": seau_foundations(),
        "starting_deficit_vector": {
            "81": deficit(seau_81(), PREMADE[86]),
            "84": deficit(PREMADE[84], PREMADE[86]),
            "86_EVO": deficit(EVO_86, PREMADE[86]),
            "87": deficit(PREMADE[87], PREMADE[86]),
        },
        "upgrade_opportunity_value": opportunity_quality(),
        "specialization_headroom": {
            "81": {"SPD": 20, "ACC": 9},
            "84": {"SPD": 17, "ACC": 9},
            "caps_source": "USER_PRIMARY_VISIBLE_INTERFACE",
            "selection_probabilities": None,
            "headroom_is_probability": False,
        },
        "foundation_repair_burden": {
            "81": deficit(seau_81(), PREMADE[86])["total"],
            "84": deficit(PREMADE[84], PREMADE[86])["total"],
            "86_EVO": deficit(EVO_86, PREMADE[86])["total"],
        },
        "upgrade_allocation_risk": {
            "observed_total_points": sum(sum(e["deltas"].values()) for e in EVO_EVENTS),
            "speed_specialization_points": 16,
            "cth_low_target_value_points": 14,
            "allocation_probabilities": None,
            "classification": "HIGH_OBSERVED_VARIANCE_IN_ROLE_RELEVANCE",
        },
        "seau_81_vs_84": seau,
        "broad_foundation_custom_specialization": {
            "classification": "SUPPORTED_FOR_SEAU_ONLY; INSUFFICIENT_BEYOND_SEAU",
            "premade": seau["premade_concentration"],
            "evo": seau["evo_concentration"],
        },
        "expected_final_build_model": projection["projected_final_role_profile"],
        "optimal_starting_ovr": projection["optimal_starting_ovr"],
        "starting_card_path": projection["starting_card_path"],
        "prospective_upgrade_scout": prospective(cards, above),
        "upgrade_failure_taxonomy": failure_taxonomy(),
        "pc_upgrade_decision_output": prospective(cards, above),
        "secondary_gates": secondary(root, cards, above),
        "validation": {
            "guessed_values": False,
            "synthetic_vectors": False,
            "forced_seau_result": False,
            "unknown_zero_conversion": False,
            "forced_mappings": False,
            "unsupported_gameplay_claims": False,
            "market_fabrication": False,
            "access_bypass": False,
            "canonical_changes": False,
        },
    }


def write_artifacts(output: Path, analysis: dict) -> None:
    output.mkdir(parents=True, exist_ok=True)
    for name, value in analysis.items():
        (output / f"{name}.json").write_text(
            json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
