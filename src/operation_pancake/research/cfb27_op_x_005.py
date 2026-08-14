"""OP-X-005 Dynamic Upgrade event and opportunity-value intelligence."""

from __future__ import annotations

import hashlib
import json
import re
import statistics
from collections import Counter, defaultdict
from pathlib import Path

from operation_pancake.research.cfb27_op_x_001 import _cards
from operation_pancake.research.cfb27_op_x_004 import (
    EVO_EVENTS,
    PREMADE,
    PRIMARY_POOL,
    SECONDARY_POOL,
    seau_81,
)


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _mean(values):
    values = list(values)
    return round(statistics.mean(values), 4) if values else None


CARD_PATTERN = re.compile(
    r'<a[^>]+href="(?P<href>/players/[^\"]+/2[56]-[^\"]+/)"[^>]*>'
    r"(?P<body>.*?)</a>",
    re.DOTALL,
)


def parse_historical_listing(html: str) -> list[dict]:
    rows = []
    for match in CARD_PATTERN.finditer(html):
        text = " ".join(re.sub(r"<[^>]+>", " ", match.group("body")).split())
        overall = re.search(r"OVR\s+(\d+)", text)
        if overall:
            rows.append(
                {
                    "source_url": "https://cfb.fan" + match.group("href"),
                    "card_id": match.group("href").strip("/").split("/")[-1],
                    "overall": int(overall.group(1)),
                    "visible_text": text,
                    "ratings_scope": "LISTING_SUMMARY_ONLY",
                }
            )
    return rows


def _quantiles(values: list[int]) -> dict:
    ordered = sorted(values)
    if len(ordered) < 4:
        return {
            "status": "INSUFFICIENT_SAMPLE",
            "minimum": min(ordered),
            "median": statistics.median(ordered),
            "mean": _mean(ordered),
            "maximum": max(ordered),
        }
    quartiles = statistics.quantiles(ordered, n=4, method="inclusive")
    return {
        "minimum": min(ordered),
        "q1": quartiles[0],
        "median": statistics.median(ordered),
        "mean": _mean(ordered),
        "q3": quartiles[2],
        "maximum": max(ordered),
    }


def event_master(root: Path) -> list[dict]:
    rows = []
    current = seau_81().copy()
    for number, event in enumerate(EVO_EVENTS, 1):
        for attribute, delta in event["deltas"].items():
            pre = current.get(attribute)
            post = pre + delta if pre is not None else None
            rows.append(
                {
                    "player": "Junior Seau",
                    "card": "81_START_EVO",
                    "starting_ovr": 81 if number == 1 else EVO_EVENTS[number - 2]["ending_ovr"],
                    "ending_ovr": event["ending_ovr"],
                    "position": "MIKE",
                    "archetype": "Lurker",
                    "path": "LURKER",
                    "upgrade_event": number,
                    "attribute": attribute,
                    "attribute_class": "DYNAMIC_UPGRADE",
                    "pre_upgrade_value": pre,
                    "post_upgrade_value": post,
                    "delta": delta,
                    "cap": 99 if attribute == "SPD" else 91,
                    "pool": "PRIMARY" if attribute in PRIMARY_POOL else "SECONDARY",
                    "reroll_number": None,
                    "cost": None,
                    "source": "USER_PRIMARY_OP_X_004",
                    "confidence": "VALIDATED",
                }
            )
            if post is not None:
                current[attribute] = post
    for start, end in ((84, 86), (86, 87)):
        for attribute, post in PREMADE[end].items():
            rows.append(
                {
                    "player": "Junior Seau",
                    "card": f"PREMADE_{start}_{end}",
                    "starting_ovr": start,
                    "ending_ovr": end,
                    "position": "MIKE",
                    "archetype": "Lurker",
                    "path": None,
                    "upgrade_event": f"PREMADE_{start}_{end}",
                    "attribute": attribute,
                    "attribute_class": "PREMADE_CARD_PROGRESSION",
                    "pre_upgrade_value": PREMADE[start][attribute],
                    "post_upgrade_value": post,
                    "delta": post - PREMADE[start][attribute],
                    "cap": None,
                    "pool": None,
                    "reroll_number": None,
                    "cost": None,
                    "source": "USER_PRIMARY_OP_X_004",
                    "confidence": "VALIDATED",
                }
            )
    for source_name, system in (
        ("confirmed_transition_deltas.json", "OTHER/UNKNOWN"),
        ("../reset_context_audit/reset_sparse_transition_inventory.json", "SATURDAY_RESET"),
    ):
        path = root / "data/research/progression_audit" / source_name
        for transition in _load(path):
            for attribute, delta in transition["attribute_deltas"].items():
                if not delta:
                    continue
                rows.append(
                    {
                        "player": transition["player"],
                        "card": transition["transition_id"],
                        "starting_ovr": transition["start_ovr"],
                        "ending_ovr": transition["end_ovr"],
                        "position": transition["position"],
                        "archetype": transition.get("archetype"),
                        "path": None,
                        "upgrade_event": transition["transition_id"],
                        "attribute": attribute,
                        "attribute_class": system,
                        "pre_upgrade_value": None,
                        "post_upgrade_value": None,
                        "delta": delta,
                        "cap": None,
                        "pool": None,
                        "reroll_number": None,
                        "cost": None,
                        "source": transition["source_id"],
                        "confidence": transition["classification"],
                    }
                )
    return rows


def dynamic_shapes(rows: list[dict]) -> list[dict]:
    events = defaultdict(list)
    for row in rows:
        if row["attribute_class"] == "DYNAMIC_UPGRADE":
            events[row["upgrade_event"]].append(row)
    output = []
    for event, items in sorted(events.items()):
        deltas = sorted((row["delta"] for row in items), reverse=True)
        total = sum(deltas)
        shares = [delta / total for delta in deltas]
        output.append(
            {
                "event": event,
                "transition": f"{items[0]['starting_ovr']}->{items[0]['ending_ovr']}",
                "position": "MIKE",
                "path": "LURKER",
                "starting_ovr": items[0]["starting_ovr"],
                "attribute_count": len(items),
                "total_points": total,
                "largest_delta": deltas[0],
                "second_largest_delta": deltas[1] if len(deltas) > 1 else None,
                "top_three_share": round(sum(shares[:3]), 4),
                "concentration_hhi": round(sum(share**2 for share in shares), 4),
                "primary_points": sum(row["delta"] for row in items if row["pool"] == "PRIMARY"),
                "secondary_points": sum(
                    row["delta"] for row in items if row["pool"] == "SECONDARY"
                ),
                "sample_warning": "ONE_OBSERVED_EVENT_PER_TRANSITION",
            }
        )
    return output


def selection_frequency(rows: list[dict]) -> dict:
    dynamic = [row for row in rows if row["attribute_class"] == "DYNAMIC_UPGRADE"]
    events = len({row["upgrade_event"] for row in dynamic})
    selected = Counter(row["attribute"] for row in dynamic)
    points = Counter()
    for row in dynamic:
        points[row["attribute"]] += row["delta"]
    records = []
    for pool_name, pool in (("PRIMARY", PRIMARY_POOL), ("SECONDARY", SECONDARY_POOL)):
        for attribute in sorted(pool):
            records.append(
                {
                    "attribute": attribute,
                    "pool": pool_name,
                    "events_observed": events,
                    "selected_events": selected[attribute],
                    "observed_selection_frequency": round(selected[attribute] / events, 4),
                    "total_points": points[attribute],
                    "mean_delta_when_selected": round(points[attribute] / selected[attribute], 4)
                    if selected[attribute]
                    else None,
                    "probability_claimed": False,
                }
            )
    return {
        "path": "LURKER",
        "events": events,
        "records": records,
        "near_cap_events": 0,
        "sample_warning": "FOUR EVENTS_ONE_PLAYER_ONE_PATH",
    }


def delta_distributions(rows: list[dict]) -> dict:
    dynamic = [row for row in rows if row["attribute_class"] == "DYNAMIC_UPGRADE"]
    by_attribute = defaultdict(list)
    by_pool = defaultdict(list)
    for row in dynamic:
        by_attribute[row["attribute"]].append(row["delta"])
        by_pool[row["pool"]].append(row["delta"])
    return {
        "by_attribute": {key: _quantiles(value) for key, value in sorted(by_attribute.items())},
        "by_pool": {key: _quantiles(value) for key, value in sorted(by_pool.items())},
        "large_jumps": [row for row in dynamic if row["delta"] >= 5],
        "causal_classification": "ATTRIBUTE_PATH_OVR_RANDOM_EFFECTS_UNRESOLVED",
    }


def primary_secondary(rows: list[dict]) -> dict:
    dynamic = [row for row in rows if row["attribute_class"] == "DYNAMIC_UPGRADE"]
    events = 4
    result = {}
    for name, pool in (("PRIMARY", PRIMARY_POOL), ("SECONDARY", SECONDARY_POOL)):
        selected = [row for row in dynamic if row["pool"] == name]
        result[name] = {
            "pool_attributes": len(pool),
            "selections": len(selected),
            "per_attribute_event_selection_rate": round(len(selected) / (len(pool) * events), 4),
            "points": sum(row["delta"] for row in selected),
            "mean_delta": _mean(row["delta"] for row in selected),
            "large_delta_frequency": round(
                sum(row["delta"] >= 5 for row in selected) / len(selected), 4
            ),
            "near_cap_selections": 0,
        }
    return {
        "classification": "PRIMARY_ADVANTAGE_PARTIAL",
        "comparison": result,
        "why": (
            "Primary has higher observed selection rate and mean delta, but only "
            "four events from one Lurker card are available."
        ),
        "probability_assumed": False,
    }


def cap_model(rows: list[dict]) -> dict:
    dynamic = [row for row in rows if row["attribute_class"] == "DYNAMIC_UPGRADE"]
    return {
        "known_cap_rows": len(dynamic),
        "near_cap_before_selection": sum(
            row["pre_upgrade_value"] is not None and row["cap"] - row["pre_upgrade_value"] <= 3
            for row in dynamic
        ),
        "truncated_deltas": sum(row["post_upgrade_value"] == row["cap"] for row in dynamic),
        "capped_attribute_nonselection_test": "NOT_IDENTIFIABLE_FROM_SELECTED_ATTRIBUTES_ONLY",
        "redistribution_test": "INSUFFICIENT_EVIDENCE",
        "mechanics_inferred": False,
    }


def ovr_step(shapes: list[dict]) -> dict:
    return {
        row["transition"]: {
            key: row[key]
            for key in ("attribute_count", "total_points", "largest_delta", "concentration_hhi")
        }
        for row in shapes
    } | {
        "classification": "NO_SYSTEMATIC_STEP_EFFECT_ESTABLISHED",
        "reason": "One Dynamic observation per transition",
    }


def reroll_framework() -> dict:
    return {
        "observed_rerolls": 0,
        "initial_rolls": [],
        "rerolls": [],
        "best_retained": [],
        "expected_value": None,
        "required_inputs": [
            "initial_roll",
            "reroll_result",
            "retained_result",
            "reroll_number",
            "resource_cost",
            "opportunity_cost",
            "path",
            "caps",
        ],
        "status": "DATA_BLOCKED",
        "fabricated_counts": False,
    }


def role_profiles() -> dict:
    return {
        "MIKE_MAX_SPEED": {
            "formula_value": {"SPD": "UNRESOLVED", "ACC": "UNRESOLVED"},
            "ability_value": {"source": "CFB27_SINGLE_STRUCTURED_THRESHOLDS", "collapsed": False},
            "rarity_value": {
                "SPD": "POPULATION_SCARCITY_COMPONENT",
                "ACC": "POPULATION_SCARCITY_COMPONENT",
            },
            "role_value": {
                "SPD": "PRIMARY_SPECIALIZATION",
                "ACC": "PRIMARY_SPECIALIZATION",
                "BSH": "FOUNDATION_CONSTRAINT",
                "MCV": "FOUNDATION_CONSTRAINT",
                "ZCV": "FOUNDATION_CONSTRAINT",
                "CTH": "LOW_TARGET_PRIORITY",
            },
            "gameplay_weighted_score": None,
        }
    }


def opportunity_ev(shapes: list[dict]) -> dict:
    total = [row["total_points"] for row in shapes]
    spec = [7, 3, 6, 0]
    repair = [5, 4, 5, 8]
    low = [6, 0, 0, 8]
    unknown = [0, 0, 7, 0]
    return {
        "scope": "SEAU_LURKER_81_TO_86_ONLY",
        "sample_size": 4,
        "total_point_ev": _mean(total),
        "specialization_ev": _mean(spec),
        "foundation_repair_ev": _mean(repair),
        "low_value_allocation_ev": _mean(low),
        "unknown_value_ev": _mean(unknown),
        "total_point_variance": round(statistics.pvariance(total), 4),
        "downside": min(total),
        "upside": max(total),
        "confidence": "EXPLORATORY",
        "stationarity_assumed": False,
        "by_transition": {
            row["transition"]: {
                "observed_total": row["total_points"],
                "range_not_distribution": True,
            }
            for row in shapes
        },
    }


def counterfactual_v2() -> dict:
    speed = [7, 0, 3, 0]
    acc = [0, 3, 3, 0]
    scenarios = []
    for left in range(4):
        for right in range(4):
            scenarios.append(
                {
                    "event_pair": [left + 1, right + 1],
                    "final_spd": 82 + speed[left] + speed[right],
                    "final_acc": 82 + acc[left] + acc[right],
                }
            )
    return {
        "classification": "INSUFFICIENT_EVIDENCE",
        "confidence": "EXPLORATORY",
        "empirical_resampling_scenarios": scenarios,
        "scenario_count": 16,
        "spd_89_or_more_fraction": round(sum(row["final_spd"] >= 89 for row in scenarios) / 16, 4),
        "acc_88_or_more_fraction": round(sum(row["final_acc"] >= 88 for row in scenarios) / 16, 4),
        "joint_89_88_fraction": round(
            sum(row["final_spd"] >= 89 and row["final_acc"] >= 88 for row in scenarios) / 16, 4
        ),
        "probability_claimed": False,
        "warning": (
            "Fractions describe resampling of four nonstationary observed events, "
            "not true roll probabilities."
        ),
        "technical_foundation": "PREMADE_84_OBSERVED",
        "synthetic_vector": False,
    }


def marginal_curve() -> list[dict]:
    values = [
        {"specialization": 7, "repair": 5, "low": 6, "unknown": 0},
        {"specialization": 3, "repair": 4, "low": 0, "unknown": 0},
        {"specialization": 6, "repair": 5, "low": 0, "unknown": 7},
        {"specialization": 0, "repair": 8, "low": 8, "unknown": 0},
    ]
    return [
        {
            "opportunity": index + 1,
            **row,
            "useful_observed": row["specialization"] + row["repair"],
            "diminishing_returns_claimed": False,
        }
        for index, row in enumerate(values)
    ]


def confidence_system() -> dict:
    return {
        "tiers": {
            "DO_NOT_MODEL": "missing pool or event identity",
            "EXPLORATORY": "1-4 events or one player/path",
            "USE_WITH_CAUTION": "5-19 events with pools/caps",
            "PRACTICAL": "20+ events, costs and path coverage",
            "HIGH_CONFIDENCE": "large replicated sample plus independent validation",
        },
        "current_dynamic_model": "EXPLORATORY",
        "factors": {
            "sample_size": 4,
            "path_coverage": 1,
            "known_caps": True,
            "known_pool": True,
            "known_costs": False,
            "independent_validation": False,
            "counterfactual_uncertainty": "HIGH",
        },
        "fact_presentation_guard": True,
    }


def generalization(root: Path) -> dict:
    master = _load(root / "data/research/cfb27_op_x_004/upgrade_progression_master_v1.json")
    return {
        "Seau": {"classification": "SUPPORTED", "premade": "BROAD", "dynamic": "SPECIALIZED"},
        "Joey_Harrington": {
            "classification": "PREMADE_OR_OTHER_BROAD_ONLY",
            "dynamic_comparison": False,
        },
        "Saturday_Reset": {"classification": "SEPARATE_SPARSE_SYSTEM", "dynamic_comparison": False},
        "Bo_Jackson": {"classification": "INSUFFICIENT_VECTORS"},
        "Chris_Peal": {"classification": "INSUFFICIENT_VECTORS"},
        "Peyton_Bowen": {"classification": "INSUFFICIENT_VECTORS"},
        "TE_chains": {"classification": "INSUFFICIENT_DYNAMIC_LABELS"},
        "master_chain_count": master["chain_count"],
        "cross_system_pooling": False,
    }


def secondary(root: Path, cards: list[dict]) -> dict:
    above = _load(root / "data/research/cfb27_op_x_004/above_ovr_foundation_profile.json")

    def ranking(position):
        rows = [row for row in above if row["position"] == position]
        return sorted(
            (
                {
                    "card_id": row["card_id"],
                    "player": row["player"],
                    "above_higher_ovr_attributes": sum(
                        value["meets_higher_ovr_median"] for value in row["attributes"].values()
                    ),
                }
                for row in rows
            ),
            key=lambda row: (-row["above_higher_ovr_attributes"], row["card_id"]),
        )[:10]

    scarcity = {}
    for position in sorted({card["position"] for card in cards}):
        subset = [card for card in cards if card["position"] == position]
        scarcity[position] = {
            attribute: {
                "median": statistics.median(values),
                "maximum": max(values),
                "top_decile_floor": sorted(values)[max(0, int(len(values) * 0.9) - 1)],
            }
            for attribute in sorted({key for card in subset for key in card["displayed_ratings"]})
            if (
                values := [
                    card["displayed_ratings"][attribute]
                    for card in subset
                    if attribute in card["displayed_ratings"]
                ]
            )
        }
    return {
        "center_primary_ranking": ranking("C"),
        "te_blocking_ranking": ranking("TE"),
        "mike_foundation_ranking": ranking("MIKE"),
        "attribute_scarcity": scarcity,
        "ability_threshold_scarcity": _load(
            root / "data/research/cfb27_ability_phase6_10/threshold_distributions.json"
        ),
        "same_player_premade_detection": _load(
            root / "data/research/cfb27_op_x_003/secondary_gates.json"
        )["same_player_lineage"],
        "release_foundation_quality": {
            "status": "DESCRIPTIVE_JOIN_AVAILABLE",
            "causal_claim": False,
        },
        "upgrade_price_watchlist": _load(
            root / "data/research/cfb27_op_x_004/secondary_gates.json"
        )["market_collection"],
        "dynamic_path_caps": {
            "LURKER": {"SPD": 99, "OTHER_VISIBLE": 91, "source": "USER_PRIMARY"},
            "SIGNAL_CALLER": "UNKNOWN",
            "THUMPER": "UNKNOWN",
        },
        "historical_madden_progression": {
            "status": "AGGREGATE_ARCHITECTURE_ONLY",
            "dynamic_equivalence": False,
        },
    }


def pc_v2(cards: list[dict], confidence: dict) -> list[dict]:
    rows = []
    for card in cards:
        is_seau = card["player_name"] == "Junior Seau"
        rows.append(
            {
                "player": card["player_name"],
                "card_id": card["external_card_id"],
                "best_starting_version": None,
                "best_development_path": "LURKER" if is_seau else None,
                "foundation_score_components": "SEE_OP_X_004" if is_seau else None,
                "expected_upgrade_value": 14.75 if is_seau else None,
                "specialization_upside": "OBSERVED_89_SPD_88_ACC" if is_seau else "UNKNOWN",
                "foundation_repair_burden": 33 if is_seau else None,
                "allocation_risk": "HIGH" if is_seau else "UNKNOWN",
                "cap_risk": "LOW_FOR_SPD_OBSERVED" if is_seau else "UNKNOWN",
                "reroll_value": None,
                "resource_cost": None,
                "finished_card_comparison": "PREMADE_86_AVAILABLE" if is_seau else None,
                "expected_final_range": "SEE_SEAU_COUNTERFACTUAL_V2" if is_seau else None,
                "confidence": confidence["current_dynamic_model"] if is_seau else "DO_NOT_MODEL",
                "why": "Four validated Lurker events"
                if is_seau
                else "No card-specific Dynamic Upgrade observations",
                "what_data_would_change_recommendation": [
                    "before/after roll",
                    "path pool",
                    "caps",
                    "reroll",
                    "cost",
                ],
            }
        )
    return rows


def build_op_x_005(root: Path) -> dict:
    cards = _cards(root)
    rows = event_master(root)
    shapes = dynamic_shapes(rows)
    confidence = confidence_system()
    inputs = [
        root / "data/research/cfb27_op_x_004/seau_primary_evidence.json",
        root / "data/research/cfb27_op_x_004/upgrade_progression_master_v1.json",
        root / "data/external/cfb_fan_population_state.json",
    ]
    return {
        "freeze": {
            "source_commit": "c6d3ff6",
            "input_sha256": {
                p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in inputs
            },
        },
        "dynamic_upgrade_event_master_v1": rows,
        "event_shape_distribution": shapes,
        "attribute_selection_frequency": selection_frequency(rows),
        "delta_magnitude_distribution": delta_distributions(rows),
        "cap_interaction_model": cap_model(rows),
        "primary_vs_secondary": primary_secondary(rows),
        "ovr_step_effect": ovr_step(shapes),
        "reroll_value": reroll_framework(),
        "role_priority_profiles": role_profiles(),
        "expected_opportunity_value": opportunity_ev(shapes),
        "seau_counterfactual_v2": counterfactual_v2(),
        "marginal_upgrade_opportunity_curve": marginal_curve(),
        "optimal_starting_ovr_v2": {
            "classification": "INSUFFICIENT_EVIDENCE",
            "foundation_84_advantage": True,
            "opportunity_ev": opportunity_ev(shapes),
            "allocation_risk": "HIGH",
            "cap_interaction": "UNRESOLVED",
            "costs": "PARTIAL",
            "finished_alternative": "PREMADE_86",
            "recommendation_confidence": "EXPLORATORY",
        },
        "historical_progression_generalization": generalization(root),
        "historical_acquisition_engine": {
            "script": "scripts/acquire_cfb_historical.py",
            "safe_route": "ORDINARY_PUBLIC_HTML_PAGINATION",
            "CFB25_pages": 693,
            "CFB26_pages": 676,
            "default_max_pages": 1,
            "minimum_delay_seconds": 2,
            "full_population_acquired": False,
        },
        "cross_year_upgrade_architecture": {
            "status": "STATIC_SUMMARY_SAMPLE_ONLY",
            "dynamic_mechanics_inferred": False,
        },
        "market_observation_expansion": {
            "existing_real_public_observations": 8,
            "user_approximate_seau_observations": 3,
            "total": 11,
            "new_sales_claimed": False,
        },
        "upgrade_data_collection_priority": {
            "ranked_fields": [
                "before_ratings_screenshot",
                "path_and_primary_secondary_pool",
                "roll_result",
                "reroll_result",
                "resource_cost",
                "cap_state",
                "retained_result",
                "card_and_starting_ovr",
            ],
            "schema": {
                "experiment_id": "required",
                "card_id": "required",
                "starting_ovr": "required",
                "path": "required",
                "before_ratings": "required",
                "pool_labels": "required",
                "result_deltas": "required",
                "caps": "nullable",
                "reroll_number": "nullable",
                "cost": "nullable",
                "source": "required",
            },
        },
        "upgrade_recommendation_confidence": confidence,
        "pc_development_intelligence_v2": pc_v2(cards, confidence),
        "secondary_gates": secondary(root, cards),
        "validation": {
            "guessed": False,
            "synthetic_rolls": False,
            "uniform_rng_assumed": False,
            "primary_secondary_probability_assumed": False,
            "gameplay_claims": False,
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
