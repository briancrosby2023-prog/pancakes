"""Phase-IV TE falsification, QB reconstruction, and decision-support analysis."""

from __future__ import annotations

import hashlib
import json
import random
import statistics
from collections import Counter, defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Any

from operation_pancake.research.cfb27_phase2 import _fit, is_special
from operation_pancake.research.cfb27_phase3 import _ridge_fit, _ridge_predict

SEED = 271828
NULL_DRAWS = 1000


def _score(row: dict[str, Any], weights: dict[str, float]) -> float:
    return sum(row[key] * value for key, value in weights.items()) / sum(weights.values())


def _normalized(weights: dict[str, float]) -> dict[str, float]:
    total = sum(weights.values())
    return {key: value / total for key, value in weights.items()}


def _blend(*parts: tuple[float, dict[str, float]]) -> dict[str, float]:
    output = defaultdict(float)
    for fraction, weights in parts:
        for key, value in _normalized(weights).items():
            output[key] += fraction * value
    return dict(output)


def _ordering(rows: list[dict[str, Any]], weights: dict[str, float]) -> dict[str, Any]:
    pairs, correct, failures, margins = 0, 0, [], []
    for index, left in enumerate(rows):
        for right in rows[index + 1 :]:
            if left["OVR"] == right["OVR"]:
                continue
            lower, upper = (left, right) if left["OVR"] < right["OVR"] else (right, left)
            margin = _score(upper, weights) - _score(lower, weights)
            pairs += 1
            correct += margin > 0
            margins.append(margin)
            if margin <= 0:
                failures.append(
                    {
                        "lower": lower["Card_ID"],
                        "upper": upper["Card_ID"],
                        "lower_ovr": lower["OVR"],
                        "upper_ovr": upper["OVR"],
                        "margin": round(margin, 8),
                    }
                )
    return {
        "correct": correct,
        "pairs": pairs,
        "accuracy": round(correct / pairs, 8) if pairs else None,
        "mean_margin": round(statistics.mean(margins), 8) if margins else None,
        "failures": failures,
    }


def _null_summary(values: list[float], historical: float) -> dict[str, Any]:
    mean = statistics.mean(values)
    deviation = statistics.pstdev(values)
    return {
        "draws": len(values),
        "mean_accuracy": round(mean, 8),
        "standard_deviation": round(deviation, 8),
        "minimum": round(min(values), 8),
        "maximum": round(max(values), 8),
        "tie_or_beat": sum(value >= historical for value in values),
        "tie_or_beat_rate": round(sum(value >= historical for value in values) / len(values), 8),
        "historical_percentile": round(
            100 * sum(value <= historical for value in values) / len(values), 4
        ),
        "standardized_effect": round((historical - mean) / deviation, 6) if deviation else None,
    }


def _fresh_te_ordering(rows: list[dict[str, Any]], attributes: list[str]) -> dict[str, Any]:
    transformed = [
        {
            "external_card_id": row["Card_ID"],
            "overall": row["OVR"],
            "displayed_ratings": {key: row[key] for key in attributes},
        }
        for row in rows
    ]
    predictions = []
    for index, holdout in enumerate(transformed):
        training = [row for number, row in enumerate(transformed) if number != index]
        model = _ridge_fit(training, attributes, penalty=10.0)
        predictions.append(_ridge_predict(model, holdout, attributes))
    pairs = [
        (left, right)
        for left in range(len(rows))
        for right in range(left + 1, len(rows))
        if rows[left]["OVR"] != rows[right]["OVR"]
    ]
    correct = sum(
        (predictions[left] - predictions[right]) * (rows[left]["OVR"] - rows[right]["OVR"]) > 0
        for left, right in pairs
    )
    return {
        "model": "LOOCV ridge lambda=10; every held-out score trained without that card",
        "correct": correct,
        "pairs": len(pairs),
        "accuracy": round(correct / len(pairs), 8),
    }


def _te_null(
    rows: list[dict[str, Any]],
    historical_weights: dict[str, float],
    all_attributes: list[str],
    blend_sources: dict[str, dict[str, float]] | None = None,
) -> dict[str, Any]:
    historical = _ordering(rows, historical_weights)
    equal = _ordering(rows, dict.fromkeys(historical_weights, 1.0))
    generic_attributes = [
        key
        for key in ("SPD", "ACC", "AWR", "CTH", "CIT", "SRR", "MRR", "DRR", "RBK", "PBK", "IBL")
        if key in all_attributes
    ]
    generic = _ordering(rows, dict.fromkeys(generic_attributes, 1.0))
    rng = random.Random(SEED + len(rows))
    values = list(historical_weights.values())
    random_accuracies, shuffled_accuracies, subset_accuracies, blend_accuracies = [], [], [], []
    subset_size = min(len(historical_weights), len(all_attributes))
    for _ in range(NULL_DRAWS):
        random_weights = {key: rng.uniform(0.1, 2.0) for key in historical_weights}
        random_accuracies.append(_ordering(rows, random_weights)["accuracy"])
        permuted = values[:]
        rng.shuffle(permuted)
        shuffled_accuracies.append(
            _ordering(rows, dict(zip(historical_weights, permuted, strict=True)))["accuracy"]
        )
        subset = rng.sample(all_attributes, subset_size)
        subset_accuracies.append(_ordering(rows, dict.fromkeys(subset, 1.0))["accuracy"])
        if blend_sources:
            fractions = [rng.random() for _ in blend_sources]
            total = sum(fractions)
            blend = _blend(
                *[
                    (fraction / total, weights)
                    for fraction, weights in zip(fractions, blend_sources.values(), strict=True)
                ]
            )
            blend_accuracies.append(_ordering(rows, blend)["accuracy"])
    local = []
    sign_failures = {}
    for key in historical_weights:
        candidate = dict(historical_weights)
        candidate[key] *= 1.1
        up = _ordering(rows, candidate)["accuracy"]
        candidate[key] = historical_weights[key] * 0.9
        down = _ordering(rows, candidate)["accuracy"]
        candidate[key] = -historical_weights[key]
        sign = _ordering(rows, candidate)["accuracy"]
        local.append(
            {
                "attribute": key,
                "historical_weight": historical_weights[key],
                "accuracy_plus_10pct": up,
                "accuracy_minus_10pct": down,
                "stable": up == historical["accuracy"] == down,
            }
        )
        sign_failures[key] = sign
    nearby = []
    for _ in range(NULL_DRAWS):
        weights = {key: value * rng.uniform(0.9, 1.1) for key, value in historical_weights.items()}
        nearby.append(_ordering(rows, weights)["accuracy"])
    return {
        "historical": historical,
        "equal": equal,
        "generic_football": generic,
        "random_positive": _null_summary(random_accuracies, historical["accuracy"]),
        "shuffled_historical": _null_summary(shuffled_accuracies, historical["accuracy"]),
        "random_subsets": _null_summary(subset_accuracies, historical["accuracy"]),
        "random_historical_blends": (
            _null_summary(blend_accuracies, historical["accuracy"]) if blend_accuracies else None
        ),
        "fresh_ridge": _fresh_te_ordering(rows, all_attributes),
        "identifiability": {
            "local_perturbations": local,
            "nearby_vectors_tying_historical": sum(
                value >= historical["accuracy"] for value in nearby
            ),
            "nearby_vectors_tested": len(nearby),
            "sign_reversal_accuracy": sign_failures,
        },
    }


def _classify_te(result: dict[str, Any]) -> dict[str, str]:
    random_rate = result["random_positive"]["tie_or_beat_rate"]
    shuffled_rate = result["shuffled_historical"]["tie_or_beat_rate"]
    if random_rate <= 0.01 and shuffled_rate <= 0.05:
        ranking = "RANKING_INHERITANCE_STRONG"
    elif random_rate <= 0.05:
        ranking = "RANKING_INHERITANCE_MODERATE"
    else:
        ranking = "NOT_EXCEPTIONAL"
    equivalent = result["identifiability"]["nearby_vectors_tying_historical"]
    numeric = "NUMERIC_INHERITANCE_STRONG" if equivalent <= 50 else "ARCHITECTURE_ONLY"
    return {"ranking": ranking, "numeric": numeric}


def _te_special(
    external: list[dict[str, Any]],
    canonical: list[dict[str, Any]],
    models: dict[str, dict[str, float]],
) -> dict[str, Any]:
    output = {}
    for archetype, weights in models.items():
        history = [row for row in canonical if row["Archetype"] == archetype]
        scores = [_score(row, weights) for row in history]
        slope, intercept = _fit(scores, [row["OVR"] for row in history])
        group = [
            row
            for row in external
            if row["position"] == "TE"
            and row.get("archetype") == archetype
            and all(key in row["displayed_ratings"] for key in weights)
        ]
        rows = []
        for row in group:
            adapted = row["displayed_ratings"]
            prediction = slope * _score(adapted, weights) + intercept
            rows.append(
                {
                    "card_id": row["external_card_id"],
                    "special": is_special(row),
                    "program": row["program"],
                    "ovr": row["overall"],
                    "residual": round(row["overall"] - prediction, 6),
                }
            )
        by_type = {}
        for special in (False, True):
            values = [row["residual"] for row in rows if row["special"] is special]
            by_type["special" if special else "ordinary"] = {
                "n": len(values),
                "mean_residual": round(statistics.mean(values), 6) if values else None,
            }
        output[archetype] = {"frozen_calibration": [slope, intercept], "rows": rows, **by_type}
    return output


def _te_cheap(external: list[dict[str, Any]]) -> list[dict[str, Any]]:
    tes = [row for row in external if row["position"] == "TE"]
    output = []
    for attribute in ("PBK", "PBF", "PBP", "LBK"):
        available = [row for row in tes if attribute in row["displayed_ratings"]]
        values = [row["displayed_ratings"][attribute] for row in available]
        ovrs = [row["overall"] for row in available]
        same = []
        for level in set(ovrs):
            cell = [
                row["displayed_ratings"][attribute] for row in available if row["overall"] == level
            ]
            if len(cell) >= 3:
                same.append(statistics.pvariance(cell))
        ordinary = [
            row["displayed_ratings"][attribute] - row["overall"]
            for row in available
            if not is_special(row)
        ]
        special = [
            row["displayed_ratings"][attribute] - row["overall"]
            for row in available
            if is_special(row)
        ]
        output.append(
            {
                "attribute": attribute,
                "n": len(available),
                "same_ovr_variance": round(statistics.mean(same), 6) if same else None,
                "ovr_correlation": round(statistics.correlation(values, ovrs), 6),
                "special_minus_ordinary_ovr_adjusted": round(
                    statistics.mean(special) - statistics.mean(ordinary), 6
                )
                if ordinary and special
                else None,
                "archetype_means": {
                    key: round(
                        statistics.mean(
                            row["displayed_ratings"][attribute]
                            for row in available
                            if row["archetype"] == key
                        ),
                        6,
                    )
                    for key in sorted({row["archetype"] for row in available})
                },
                "status": "EA_OVR_COST_RESEARCH_ONLY",
            }
        )
    return sorted(output, key=lambda row: (row["ovr_correlation"], -row["same_ovr_variance"]))


def _qb_hybrid(
    external: list[dict[str, Any]], qb_weights: dict[str, dict[str, float]]
) -> dict[str, Any]:
    rows = [
        row
        for row in external
        if row["position"] == "QB" and row.get("archetype") == "Backfield Creator"
    ]
    candidates = {
        "SCRAMBLER_FIELD_GENERAL_50_50": _blend(
            (0.5, qb_weights["Scrambler"]), (0.5, qb_weights["Field General"])
        ),
        "SCRAMBLER_FIELD_GENERAL_67_33": _blend(
            (0.67, qb_weights["Scrambler"]), (0.33, qb_weights["Field General"])
        ),
        "SCRAMBLER_STRONG_ARM_67_33": _blend(
            (0.67, qb_weights["Scrambler"]), (0.33, qb_weights["Strong Arm"])
        ),
    }

    def evaluate(weights: dict[str, float]) -> dict[str, Any]:
        usable = [row for row in rows if all(key in row["displayed_ratings"] for key in weights)]
        if len(usable) < 4 or len({row["overall"] for row in usable}) < 2:
            return {"n": len(usable), "status": "INSUFFICIENT"}
        scores = [
            sum(row["displayed_ratings"][key] * value for key, value in weights.items())
            / sum(weights.values())
            for row in usable
        ]
        observed, predicted = [], []
        for index, row in enumerate(usable):
            training = [
                (score, other["overall"])
                for number, (score, other) in enumerate(zip(scores, usable, strict=True))
                if number != index
            ]
            slope, intercept = _fit([score for score, _ in training], [ovr for _, ovr in training])
            observed.append(row["overall"])
            predicted.append(round(slope * scores[index] + intercept))
        errors = [abs(a - b) for a, b in zip(observed, predicted, strict=True)]
        pairs = [
            (i, j)
            for i in range(len(usable))
            for j in range(i + 1, len(usable))
            if observed[i] != observed[j]
        ]
        return {
            "n": len(usable),
            "exact": round(sum(error == 0 for error in errors) / len(errors), 6),
            "within_one": round(sum(error <= 1 for error in errors) / len(errors), 6),
            "mae": round(statistics.mean(errors), 6),
            "ordering": round(
                sum((scores[i] - scores[j]) * (observed[i] - observed[j]) > 0 for i, j in pairs)
                / len(pairs),
                6,
            )
            if pairs
            else None,
        }

    results = {name: evaluate(weights) for name, weights in candidates.items()}
    equal_attributes = sorted(set.intersection(*(set(row["displayed_ratings"]) for row in rows)))
    equal = evaluate(dict.fromkeys(equal_attributes, 1.0))
    rng = random.Random(SEED + 44)
    random_mae = []
    for _ in range(NULL_DRAWS):
        result = evaluate({key: rng.uniform(0.1, 2) for key in equal_attributes})
        if "mae" in result:
            random_mae.append(result["mae"])
    trinidad = next((row for row in rows if row["player_name"] == "Trinidad Chambliss"), None)
    percentiles = {}
    if trinidad:
        for attribute, value in trinidad["displayed_ratings"].items():
            peers = [
                row["displayed_ratings"][attribute]
                for row in rows
                if attribute in row["displayed_ratings"]
            ]
            percentiles[attribute] = round(
                100 * sum(peer <= value for peer in peers) / len(peers), 2
            )
    return {
        "population_n": len(rows),
        "pre_registered_candidates": list(candidates),
        "candidate_results": results,
        "equal": equal,
        "random_mae": {
            "draws": len(random_mae),
            "median": round(statistics.median(random_mae), 6) if random_mae else None,
        },
        "fresh_fit": "INSUFFICIENT_N_FOR_RELIABLE_15_ATTRIBUTE_FIT",
        "trinidad_chambliss": {
            "present": trinidad is not None,
            "attribute_percentiles_within_cut_backfield_creator": percentiles,
            "interpretation": "Extreme special profile; not allowed to select the archetype prior.",
        },
        "status": "RESEARCH_ONLY_UNDERPOWERED",
    }


def _moneyball_crosswalk(phase3: dict[str, Any]) -> dict[str, Any]:
    matched = {
        (row["position"], row["attribute"]): row["mean_special_delta"]
        for row in phase3["ordinary_vs_special_matched"]["attribute_deltas"]
    }
    rows = []
    for row in phase3["same_ovr_variance_and_cost"]["rows"]:
        if row["apparent_ovr_cost"] != "LOW":
            continue
        variance = row["mean_same_ovr_variance"] or 0
        population = row["n"]
        priority = variance**0.5 * min(population, 50) ** 0.5
        rows.append(
            {
                "position": row["position"],
                "attribute": row["attribute"],
                "apparent_ea_ovr_cost": row["apparent_ovr_cost"],
                "same_ovr_variance": row["mean_same_ovr_variance"],
                "archetype_dependence": "UNMEASURED",
                "special_card_effect": matched.get((row["position"], row["attribute"])),
                "ability_threshold_status": "UNRESEARCHED",
                "gameplay_evidence_status": "MISSING",
                "market_evidence_status": "MISSING",
                "confidence": "DESCRIPTIVE",
                "research_priority": round(priority, 6),
            }
        )
    rows.sort(key=lambda item: (-item["research_priority"], item["position"], item["attribute"]))
    return {"rows": rows, "top_targets": rows[:10], "gameplay_value_claimed": False}


def _release_intelligence(external: list[dict[str, Any]]) -> dict[str, Any]:
    dated = [row for row in external if row.get("release_date")]
    dates = [datetime.strptime(row["release_date"], "%m/%d/%Y").date() for row in dated]
    release_days = defaultdict(list)
    for row, released in zip(dated, dates, strict=True):
        release_days[released].append(row)
    weekday = {}
    for day in range(7):
        groups = [rows for released, rows in release_days.items() if released.weekday() == day]
        weekday[date(2026, 1, 5 + day).strftime("%A")] = {
            "release_days": len(groups),
            "cards": sum(map(len, groups)),
            "mean_cards_per_release_day": round(statistics.mean(map(len, groups)), 4)
            if groups
            else None,
            "mean_ceiling": round(
                statistics.mean(max(row["overall"] for row in rows) for rows in groups), 4
            )
            if groups
            else None,
        }
    latest = max(dates)
    replacement = {}
    for position in sorted({row["position"] for row in dated}):
        rows = sorted(
            [row for row in dated if row["position"] == position],
            key=lambda row: datetime.strptime(row["release_date"], "%m/%d/%Y").date(),
        )
        ceiling, changes = -1, []
        daily_ceiling = defaultdict(int)
        for row in rows:
            released = datetime.strptime(row["release_date"], "%m/%d/%Y").date()
            daily_ceiling[released] = max(daily_ceiling[released], row["overall"])
        for released, day_ceiling in sorted(daily_ceiling.items()):
            if day_ceiling > ceiling:
                changes.append(released)
                ceiling = day_ceiling
        intervals = [(right - left).days for left, right in zip(changes, changes[1:], strict=False)]
        days_since = (latest - changes[-1]).days
        median = statistics.median(intervals) if intervals else None
        if median is None:
            pressure = "NORMAL"
        elif days_since > median * 1.25:
            pressure = "ELEVATED"
        elif days_since < median * 0.5:
            pressure = "LOWER"
        else:
            pressure = "NORMAL"
        replacement[position] = {
            "current_ceiling": ceiling,
            "days_since_ceiling_change": days_since,
            "median_replacement_interval": median,
            "release_count": len(rows),
            "archetype_coverage": len({row["archetype"] for row in rows}),
            "program_coverage": len({row["program"] for row in rows}),
            "pressure": pressure,
        }
    return {
        "date_range": [min(dates).isoformat(), max(dates).isoformat()],
        "weekday_structure": weekday,
        "replacement_pressure": replacement,
        "forecast_readiness": "INSUFFICIENT",
    }


def _program_signatures(external: list[dict[str, Any]]) -> dict[str, Any]:
    baselines = defaultdict(lambda: defaultdict(list))
    for row in external:
        for attribute, value in row["displayed_ratings"].items():
            baselines[(row["position"], row["overall"])][attribute].append(value)
    output = {}
    for program in sorted({row["program"] for row in external}):
        rows = [row for row in external if row["program"] == program]
        if len(rows) < 5:
            continue
        deltas = defaultdict(list)
        for row in rows:
            cell = baselines[(row["position"], row["overall"])]
            for attribute, value in row["displayed_ratings"].items():
                if len(cell[attribute]) >= 2:
                    deltas[attribute].append(value - statistics.mean(cell[attribute]))
        ranked = sorted(
            (
                {
                    "attribute": attribute,
                    "matched_mean_delta": round(statistics.mean(values), 6),
                    "observations": len(values),
                }
                for attribute, values in deltas.items()
            ),
            key=lambda row: (-abs(row["matched_mean_delta"]), row["attribute"]),
        )
        output[program] = {
            "n": len(rows),
            "ovr_range": [min(row["overall"] for row in rows), max(row["overall"] for row in rows)],
            "position_mix": dict(sorted(Counter(row["position"] for row in rows).items())),
            "archetype_mix": dict(sorted(Counter(row["archetype"] for row in rows).items())),
            "largest_matched_attribute_deltas": ranked[:10],
            "causal_claim": False,
        }
    return output


def _design_signals(crosswalk: dict[str, Any]) -> list[dict[str, Any]]:
    signals = []
    for row in crosswalk["rows"]:
        effect = row["special_card_effect"]
        if effect is not None and effect >= 2:
            signals.append(
                {
                    "position": row["position"],
                    "attribute": row["attribute"],
                    "matched_special_delta": effect,
                    "same_ovr_variance": row["same_ovr_variance"],
                    "status": "EA_DESIGN_SIGNAL_CANDIDATE",
                    "gameplay_claim": False,
                }
            )
    return sorted(signals, key=lambda row: (-row["matched_special_delta"], row["position"]))


def build_phase4_analysis(
    canonical_te: list[dict[str, Any]],
    external: list[dict[str, Any]],
    te_weights: dict[str, dict[str, float]],
    qb_weights: dict[str, dict[str, float]],
    phase3: dict[str, Any],
    schema_sources: dict[str, Any],
    schema_continuity: list[dict[str, Any]],
    schema_search: dict[str, Any],
) -> dict[str, Any]:
    vt = dict(te_weights["Vertical Threat"])
    vt["LBK"], vt["IBL"] = vt.get("LBK", 0) + 2, vt.get("IBL", 0) + 3
    possession = te_weights["Possession"]
    prr = _blend((0.71, te_weights["Vertical Threat"]), (0.29, possession))
    models = {
        "Vertical Threat": vt,
        "Gritty Possession": possession,
        "Physical Route Runner": prr,
    }
    all_attributes = sorted(
        set.intersection(*(set(row) for row in canonical_te))
        - {
            "Card_ID",
            "Player",
            "OVR",
            "Program",
            "Archetype",
            "Jersey",
            "Source_ID",
            "Source_Page",
            "Validation_Status",
            "Notes",
            "FB_OOP",
            "WR_OOP",
        }
    )
    nulls = {}
    for archetype, weights in models.items():
        rows = [row for row in canonical_te if row["Archetype"] == archetype]
        blend_sources = te_weights if archetype == "Physical Route Runner" else None
        nulls[archetype] = _te_null(rows, weights, all_attributes, blend_sources)
        nulls[archetype]["classification"] = _classify_te(nulls[archetype])
    cheap = _te_cheap(external)
    crosswalk = _moneyball_crosswalk(phase3)
    release = _release_intelligence(external)
    continuity_score = [
        {
            "from": row["from"],
            "to": row["to"],
            "architecture_continuity_score": round(
                0.6 * row["name_jaccard"]
                + 0.4 * row["unchanged_asset_ids"] / max(1, row["shared_table_names"]),
                6,
            ),
            "interpretation": "descriptive architecture continuity; not code-reuse probability",
        }
        for row in schema_continuity
    ]
    ability_schema = {
        "evidence_type": "ABILITY_THRESHOLD",
        "fields": [
            "position",
            "archetype",
            "ability",
            "tier",
            "required_attribute",
            "required_rating",
            "ovr_requirement",
            "source",
            "confidence",
            "game_version",
        ],
        "records": [],
    }
    gameplay_schema = {
        "evidence_type": "GAMEPLAY_BREAKPOINT",
        "fields": [
            "position",
            "attribute",
            "threshold",
            "claimed_effect",
            "test_methodology",
            "sample",
            "source",
            "confidence",
            "replication_status",
        ],
        "records": [],
    }
    ovr_schema = {
        "evidence_type": "OVR_BOUNDARY",
        "supported_records": [],
        "historical_falsified_candidates": phase3["trigger_falsification"],
    }
    model_status = {
        "Center": {"architecture": "MODERATE", "ranking": "WEAK", "numeric": "REJECTED"},
        "TE": {
            archetype: {
                "architecture": "STRONG",
                "ranking": result["classification"]["ranking"],
                "numeric": result["classification"]["numeric"],
            }
            for archetype, result in nulls.items()
        },
        "QB": {
            "Dual Threat": {
                "architecture": "MODERATE",
                "ranking": "INDETERMINATE",
                "numeric": "INDETERMINATE",
            },
            "Pocket Passer": {
                "architecture": "MODERATE",
                "ranking": "INDETERMINATE",
                "numeric": "INDETERMINATE",
            },
            "Backfield Creator": {
                "architecture": "STRONG",
                "ranking": "WEAK",
                "numeric": "REJECTED_WEST_COAST_MAPPING",
            },
        },
    }
    return {
        "schema_version": 1,
        "phase": (
            "TE Inheritance Falsification, EA Schema Archaeology, QB Archetype "
            "Reconstruction, Moneyball Crosswalk & Release Intelligence — Phase IV"
        ),
        "population": {
            "total": len(external),
            "ordinary": sum(not is_special(row) for row in external),
            "special": sum(is_special(row) for row in external),
            "ovr_range": [
                min(row["overall"] for row in external),
                max(row["overall"] for row in external),
            ],
        },
        "te_historical_audit": {
            "Vertical Threat": {
                "model": "M19 VT +2 LBK +3 IBL",
                "population_n": 19,
                "objective": "all cross-OVR pair ordering",
                "holdout": "17/17 player-disjoint; hidden until freeze",
            },
            "Gritty Possession": {
                "model": "unmodified M19 Possession",
                "population_n": 16,
                "objective": "all cross-OVR pair ordering",
                "holdout": "82/83 independent pairs",
            },
            "Physical Route Runner": {
                "model": "71% M19 VT + 29% M19 Possession",
                "population_n": 32,
                "objective": "all cross-OVR pair ordering",
                "holdout": "304/304 holdout-involved unique-profile pairs",
            },
            "leakage": False,
            "source_provenance": (
                "Authenticated XML-derived EA Madden 19 table; not community-estimated weights."
            ),
        },
        "te_null_tests": nulls,
        "te_special_cards": _te_special(external, canonical_te, models),
        "te_ea_cheap_blocking": cheap,
        "ea_schema_sources": schema_sources,
        "schema_continuity": schema_continuity,
        "schema_architecture_scores": continuity_score,
        "schema_search": schema_search,
        "table_44_cross_check": {
            "exact_table_found": False,
            "similar_term_matches": sum(len(rows) for rows in schema_search.values()),
            "finding": (
                "No exact Ability_Progression_Tunable_Archetypes or Table_44 name in franchise "
                "schemas; schema naming makes an EA-extracted converted table plausible but "
                "unproven."
            ),
            "confidence": "MODERATE_NEGATIVE",
        },
        "base_roster_pilot": {"status": "SEPARATE_ACQUISITION_ARTIFACT_IF_AVAILABLE"},
        "qb_hybrid_test": _qb_hybrid(external, qb_weights),
        "moneyball_crosswalk": crosswalk,
        "ability_threshold_model": ability_schema,
        "gameplay_breakpoint_model": gameplay_schema,
        "ovr_boundary_model": ovr_schema,
        "release_intelligence": release,
        "program_signatures": _program_signatures(external),
        "ea_design_signals": _design_signals(crosswalk),
        "market_bridge": {
            "join_key": "external_card_id",
            "required_fields": [
                "observed_at",
                "price",
                "listing_count",
                "training",
                "quicksell",
                "market_source",
            ],
            "records": 0,
            "status": "SCHEMA_READY_DATA_ABSENT",
        },
        "prospective": {
            "Center": phase3["center_prospective_validation"],
            "QB": "NO_MODEL_MEETS_PREVALIDATION_STANDARD",
            "TE": {
                "frozen_models_preserved": True,
                "future_eligible": (
                    "card ID absent from Phase IV snapshot; score before model changes"
                ),
            },
        },
        "inheritance_status": model_status,
        "pc_evaluator": {
            "fields_added": [
                "architecture_inheritance",
                "ranking_inheritance",
                "numeric_weight_inheritance",
                "prospective_validation_state",
                "ea_cheap_candidates",
                "gameplay_evidence_status",
            ],
            "gui": False,
            "ordinary_special_warning": True,
        },
        "chatgpt_research_targets": [
            {
                "question": "Do controlled TE gameplay tests show value for PBK/PBF/PBP/LBK?",
                "reason": "High same-OVR variance and low apparent OVR cost.",
            },
            {
                "question": "Which TE blocking ratings unlock abilities by archetype?",
                "reason": "Ability evidence is currently empty and separate from OVR boundaries.",
            },
            {
                "question": (
                    "Can primary M20 developer material authenticate which TE weights were "
                    "slightly tweaked?"
                ),
                "reason": "Architecture continuity does not identify coefficients.",
            },
            {
                "question": "Can Table_44 be matched to a non-franchise EA schema or FTC table?",
                "reason": "No exact name exists in ten franchise schemas.",
            },
            {
                "question": (
                    "What explains CFB27 Player table asset-ID divergence despite rating-field "
                    "persistence?"
                ),
                "reason": "Madden uses 79; CFB27 uses 6494552.",
            },
            {
                "question": "Do competitive players value special-card TE pass blocking?",
                "reason": "EA construction may signal intended gameplay utility.",
            },
            {
                "question": (
                    "Which modern QB archetype experts consider closest to Backfield Creator?"
                ),
                "reason": "West Coast mapping is rejected and CUT n is small.",
            },
            {
                "question": "Why is Trinidad Chambliss constructed as an extreme mobile hybrid?",
                "reason": "He is not representative enough to choose formula architecture.",
            },
            {
                "question": "Does QB TRK affect contact outcomes in controlled tests?",
                "reason": "It is apparently cheap but may be irrelevant noise.",
            },
            {
                "question": (
                    "Can CFB27 base-roster Backfield Creator full vectors be exported legally?"
                ),
                "reason": "Thirteen-player population can anchor profile priors.",
            },
            {
                "question": "Which EA-cheap attributes have replicated gameplay breakpoints?",
                "reason": "No breakpoint records are currently validated.",
            },
            {
                "question": "Are special-card boosts aligned with known ability thresholds?",
                "reason": "Would distinguish design signal from cosmetic variance.",
            },
            {
                "question": "Which program construction styles recur across later releases?",
                "reason": "Only 44 days of chronology exist.",
            },
            {
                "question": "Can timestamped listings be joined to replacement events?",
                "reason": "Market bridge is ready but has zero observations.",
            },
            {
                "question": "Do elevated replacement-pressure positions receive upgrades next?",
                "reason": "Prospective test can validate descriptive pressure classification.",
            },
        ],
        "data_validation": {
            "guessed_values": False,
            "leakage": False,
            "special_ordinary_contamination": False,
            "access_bypass": False,
            "canonical_modified": False,
        },
    }


def write_phase4_artifacts(directory: str | Path, analysis: dict[str, Any]) -> None:
    root = Path(directory)
    root.mkdir(parents=True, exist_ok=True)
    mapping = {
        "phase4_summary.json": analysis,
        "te_historical_audit.json": analysis["te_historical_audit"],
        "te_null_distributions.json": analysis["te_null_tests"],
        "te_special_card_analysis.json": analysis["te_special_cards"],
        "te_ea_cheap_blocking.json": analysis["te_ea_cheap_blocking"],
        "schema_architecture_scores.json": analysis["schema_architecture_scores"],
        "table_44_cross_check.json": analysis["table_44_cross_check"],
        "qb_hybrid_test.json": analysis["qb_hybrid_test"],
        "moneyball_crosswalk.json": analysis["moneyball_crosswalk"],
        "ability_threshold_schema.json": analysis["ability_threshold_model"],
        "gameplay_breakpoint_schema.json": analysis["gameplay_breakpoint_model"],
        "ovr_boundary_schema.json": analysis["ovr_boundary_model"],
        "release_intelligence.json": analysis["release_intelligence"],
        "program_signatures.json": analysis["program_signatures"],
        "ea_design_signals.json": analysis["ea_design_signals"],
        "market_bridge.json": analysis["market_bridge"],
        "prospective_validation_ledgers.json": analysis["prospective"],
        "position_inheritance_status.json": analysis["inheritance_status"],
        "pc_evaluator_phase4.json": analysis["pc_evaluator"],
        "chatgpt_research_queue.json": analysis["chatgpt_research_targets"],
    }
    for name, payload in mapping.items():
        (root / name).write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )


def freeze_phase4(root: Path, cards: list[dict[str, Any]]) -> dict[str, Any]:
    ids = sorted(row["external_card_id"] for row in cards)
    files = [
        "data/canonical/canonical_v1.9.xlsx",
        "data/research/cfb27_inheritance_phase3/phase3_summary.json",
        "data/research/cfb27_inheritance_phase3/phase3_frozen_snapshot.json",
    ]
    return {
        "source_commit": "cd72120",
        "population_n": len(cards),
        "card_ids": ids,
        "population_sha256": hashlib.sha256(
            json.dumps(cards, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
        "input_hashes": {
            path: hashlib.sha256((root / path).read_bytes()).hexdigest() for path in files
        },
        "frozen_te_models_modified": False,
        "future_card_rule": "IDs absent here are prospective and cannot refit frozen models.",
    }
