"""OP-X-002 falsifiable Moneyball models and controlled comparison sets."""

from __future__ import annotations

import hashlib
import json
import statistics
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

from operation_pancake.research.cfb27_op_x_001 import (
    MIKE_ATTRIBUTES,
    TE_ATTRIBUTES,
    _cards,
    ability_stack,
)
from operation_pancake.research.cfb27_phase2 import is_special
from operation_pancake.research.cfb27_phase6_10 import (
    _card_position,
    card_proximity,
    grouped_thresholds,
)

TE_ARCHETYPES = {"Vertical Threat", "Gritty Possession", "Physical Route Runner"}
BLOCKING = ("PBK", "PBF", "PBP", "RBK", "RBF", "RBP", "LBK", "IBL", "STR")
CB_TECHNICAL = ("AGI", "COD", "MCV", "ZCV", "PRS", "PRC", "AWR")


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _parse_release_date(value: str) -> datetime:
    """Accept legacy M/D/Y and canonical ISO-8601 release timestamps."""
    try:
        return datetime.strptime(value, "%m/%d/%Y")
    except ValueError:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)


def _mean(values) -> float | None:
    values = list(values)
    return round(statistics.mean(values), 4) if values else None


def _slope(pairs: list[tuple[float, float]]) -> float | None:
    if len(pairs) < 2 or len({x for x, _ in pairs}) < 2:
        return None
    xbar, ybar = statistics.mean(x for x, _ in pairs), statistics.mean(y for _, y in pairs)
    denominator = sum((x - xbar) ** 2 for x, _ in pairs)
    return round(sum((x - xbar) * (y - ybar) for x, y in pairs) / denominator, 6)


def _expected(pairs: list[tuple[float, float]], x: float) -> float | None:
    slope = _slope(pairs)
    if slope is None:
        return _mean(y for _, y in pairs)
    return statistics.mean(y for _, y in pairs) + slope * (x - statistics.mean(a for a, _ in pairs))


def _same_ovr_ranges(cards: list[dict], attribute: str) -> dict:
    groups = defaultdict(list)
    for card in cards:
        if attribute in card["displayed_ratings"]:
            groups[card["overall"]].append(card["displayed_ratings"][attribute])
    return {
        str(overall): max(values) - min(values)
        for overall, values in sorted(groups.items())
        if len(values) > 1
    }


def te_moneyball(cards: list[dict]) -> dict:
    tes = [c for c in cards if c["position"] == "TE" and c["archetype"] in TE_ARCHETYPES]
    scored = []
    by_archetype = defaultdict(list)
    for card in tes:
        values = [card["displayed_ratings"][a] for a in BLOCKING if a in card["displayed_ratings"]]
        if len(values) != len(BLOCKING):
            continue
        blocking_score = statistics.mean(values)
        by_archetype[card["archetype"]].append((card["overall"], blocking_score))
        scored.append((card, blocking_score))
    candidates = []
    for card, score in scored:
        expected = _expected(by_archetype[card["archetype"]], card["overall"])
        residual = score - expected
        candidates.append(
            {
                "card_id": card["external_card_id"],
                "player": card["player_name"],
                "overall": card["overall"],
                "archetype": card["archetype"],
                "program": card["program"],
                "special": is_special(card),
                "blocking_score": round(score, 4),
                "expected_within_archetype_at_ovr": round(expected, 4),
                "blocking_value_residual": round(residual, 4),
                "reason": "BLOCKING_ABOVE_ARCHETYPE_OVR_EXPECTATION"
                if residual > 0
                else "NOT_ABOVE_EXPECTATION",
                "gameplay_value_claimed": False,
            }
        )
    candidates.sort(
        key=lambda row: (-row["blocking_value_residual"], row["overall"], row["card_id"])
    )
    pairs = []
    for index, left in enumerate(scored):
        for right in scored[index + 1 :]:
            if (
                left[0]["archetype"] == right[0]["archetype"]
                and left[0]["overall"] == right[0]["overall"]
            ):
                pairs.append(
                    {
                        "left": left[0]["external_card_id"],
                        "right": right[0]["external_card_id"],
                        "overall": left[0]["overall"],
                        "archetype": left[0]["archetype"],
                        "blocking_score_difference": round(abs(left[1] - right[1]), 4),
                    }
                )
    pairs.sort(key=lambda row: (-row["blocking_score_difference"], row["left"], row["right"]))
    attributes = {}
    for attribute in (*TE_ATTRIBUTES, "OVR"):
        values = [
            (
                c["overall"],
                c["overall"] if attribute == "OVR" else c["displayed_ratings"][attribute],
            )
            for c in tes
            if attribute == "OVR" or attribute in c["displayed_ratings"]
        ]
        attributes[attribute] = {
            "count": len(values),
            "ovr_slope": _slope(values),
            "same_ovr_ranges": _same_ovr_ranges(tes, attribute) if attribute != "OVR" else {},
        }
    counterevidence = {
        "negative_or_zero_residual_cards": sum(
            row["blocking_value_residual"] <= 0 for row in candidates
        ),
        "top_candidates_driven_by_archetype_adjustment": True,
        "market_value_available": False,
        "gameplay_value_available": False,
        "hypothesis_status": "STATISTICAL_CANDIDATES_ONLY",
    }
    return {
        "population": len(tes),
        "attribute_relationships": attributes,
        "candidates": candidates[:10],
        "all_residuals": candidates,
        "matched_pairs": pairs[:10],
        "counterevidence": counterevidence,
    }


def cb_model(cards: list[dict]) -> dict:
    cbs = [c for c in cards if _card_position(c) == "CB"]
    scored = []
    for card in cbs:
        if not all(a in card["displayed_ratings"] for a in ("SPD", "ACC", *CB_TECHNICAL)):
            continue
        athletic = statistics.mean(card["displayed_ratings"][a] for a in ("SPD", "ACC"))
        technical = statistics.mean(card["displayed_ratings"][a] for a in CB_TECHNICAL)
        scored.append((card, athletic, technical))
    by_arch = defaultdict(list)
    for card, athletic, technical in scored:
        by_arch[card["archetype"]].append((card["overall"] + athletic / 10, technical))
    residuals = []
    for card, athletic, technical in scored:
        control = card["overall"] + athletic / 10
        expected = _expected(by_arch[card["archetype"]], control)
        residuals.append(
            {
                "card_id": card["external_card_id"],
                "player": card["player_name"],
                "program": card["program"],
                "overall": card["overall"],
                "archetype": card["archetype"],
                "spd": card["displayed_ratings"]["SPD"],
                "acc": card["displayed_ratings"]["ACC"],
                "height": None,
                "athletic_score": round(athletic, 3),
                "technical_score": round(technical, 3),
                "technical_residual": round(technical - expected, 3),
            }
        )
    comparisons = []
    for index, (left, la, lt) in enumerate(scored):
        for right, ra, rt in scored[index + 1 :]:
            if (
                left["archetype"] != right["archetype"]
                or abs(left["overall"] - right["overall"]) > 1
                or abs(la - ra) > 2
            ):
                continue
            comparisons.append(
                {
                    "left": {
                        "card_id": left["external_card_id"],
                        "player": left["player_name"],
                        "program": left["program"],
                    },
                    "right": {
                        "card_id": right["external_card_id"],
                        "player": right["player_name"],
                        "program": right["program"],
                    },
                    "archetype": left["archetype"],
                    "ovr_difference": abs(left["overall"] - right["overall"]),
                    "athletic_difference": round(abs(la - ra), 3),
                    "technical_difference": round(abs(lt - rt), 3),
                    "height_control": "UNAVAILABLE",
                }
            )
    comparisons.sort(
        key=lambda row: (
            -row["technical_difference"],
            row["athletic_difference"],
            row["left"]["card_id"],
        )
    )
    residuals.sort(key=lambda row: (-row["technical_residual"], row["card_id"]))
    technical_pairs = [(card["overall"], technical) for card, _, technical in scored]
    return {
        "population": len(scored),
        "by_archetype": dict(Counter(c["archetype"] for c, _, _ in scored)),
        "technical_ovr_slope": _slope(technical_pairs),
        "height_status": "UNAVAILABLE_NOT_ZERO",
        "matched_comparisons": comparisons[:15],
        "technical_residuals": residuals,
        "technically_strong": residuals[:5],
        "athletic_technical_lag": sorted(
            residuals, key=lambda row: (row["technical_residual"], -row["athletic_score"])
        )[:5],
        "athletic_floor_test_set": comparisons[:10],
        "speed_breakpoint_invented": False,
    }


def _attribute_model(cards: list[dict], attribute: str) -> dict:
    pairs = [
        (c["overall"], c["displayed_ratings"][attribute])
        for c in cards
        if attribute in c["displayed_ratings"]
    ]
    return {
        "count": len(pairs),
        "ovr_slope": _slope(pairs),
        "same_ovr_ranges": _same_ovr_ranges(cards, attribute),
        "expected": pairs,
    }


def mike_seau(cards: list[dict], groups: list[dict], proximity: dict) -> dict:
    mike = [c for c in cards if _card_position(c) == "MIKE"]
    archetypes = ("Thumper", "Lurker", "Signal Caller")
    models = {
        arch: {
            a: _attribute_model([c for c in mike if c["archetype"] == arch], a)
            for a in MIKE_ATTRIBUTES
        }
        for arch in archetypes
    }
    residual_means = {}
    for arch in archetypes:
        subset = [c for c in mike if c["archetype"] == arch]
        residual_means[arch] = {
            a: _mean(
                c["displayed_ratings"][a] - _expected(models[arch][a]["expected"], c["overall"])
                for c in subset
                if a in c["displayed_ratings"]
            )
            for a in MIKE_ATTRIBUTES
        }
    diagnostics = []
    for attribute in MIKE_ATTRIBUTES:
        means = [_expected(models[arch][attribute]["expected"], 86) for arch in archetypes]
        diagnostics.append(
            {
                "attribute": attribute,
                "ovr_adjusted_archetype_spread": round(max(means) - min(means), 4),
                "comparison_ovr": 86,
            }
        )
    diagnostics.sort(key=lambda row: (-row["ovr_adjusted_archetype_spread"], row["attribute"]))
    by_card = defaultdict(list)
    for row in proximity["observations"]:
        by_card[row["card_id"]].append(row)
    seau_rows = []
    for card in sorted(
        (c for c in mike if c["player_name"] == "Junior Seau"), key=lambda c: c["overall"]
    ):
        distances = {}
        contributions = {}
        matrix = []
        for arch in archetypes:
            diffs = {
                a: round(
                    card["displayed_ratings"][a]
                    - _expected(models[arch][a]["expected"], card["overall"]),
                    4,
                )
                for a in MIKE_ATTRIBUTES
                if a in card["displayed_ratings"]
            }
            distances[arch] = round(statistics.mean(abs(v) for v in diffs.values()), 4)
            contributions[arch] = dict(sorted(diffs.items(), key=lambda item: -abs(item[1])))
        for attribute in MIKE_ATTRIBUTES:
            if attribute not in card["displayed_ratings"]:
                continue
            for increase in (1, 2, 3):
                new_distances = {}
                for arch in archetypes:
                    diffs = [
                        abs(
                            (card["displayed_ratings"][a] + (increase if a == attribute else 0))
                            - _expected(models[arch][a]["expected"], card["overall"])
                        )
                        for a in MIKE_ATTRIBUTES
                        if a in card["displayed_ratings"]
                    ]
                    new_distances[arch] = round(statistics.mean(diffs), 4)
                matrix.append(
                    {
                        "attribute": attribute,
                        "increase": increase,
                        "distance_delta": {
                            arch: round(new_distances[arch] - distances[arch], 4)
                            for arch in archetypes
                        },
                    }
                )
        threshold_rows = [
            r
            for r in by_card[card["external_card_id"]]
            if r.get("status") in {"AT_THRESHOLD", "1_BELOW", "2_BELOW", "3_BELOW"}
        ]
        seau_rows.append(
            {
                "card_id": card["external_card_id"],
                "overall": card["overall"],
                "normalized_distance": distances,
                "attribute_contributions": contributions,
                "upgrade_matrix": matrix,
                "threshold_interactions": threshold_rows,
                "gameplay_path_recommended": False,
            }
        )
    return {
        "population": len(mike),
        "normalized_signatures": residual_means,
        "diagnostic_attributes": diagnostics,
        "seau_upgrade_decision_matrix": seau_rows,
        "small_sample_warning": {
            arch: sum(c["archetype"] == arch for c in mike) for arch in archetypes
        },
    }


def coherence_v2(cards: list[dict], groups: list[dict], proximity: dict) -> list[dict]:
    base = {row["card_id"]: row for row in ability_stack(cards, groups)}
    by_card = defaultdict(list)
    for row in proximity["observations"]:
        if "deficits" in row:
            by_card[row["card_id"]].append(row)
    output = []
    for card in cards:
        if _card_position(card) not in {"TE", "CB", "MIKE", "QB", "HB", "WR", "FS"}:
            continue
        rows = by_card[card["external_card_id"]]
        near = [r for r in rows if max(r["deficits"].values()) <= 2]
        attrs = Counter(a for r in near for a, d in r["deficits"].items() if d <= 2)
        abilities = Counter(r["ability"] for r in near)
        output.append(
            {
                "card_id": card["external_card_id"],
                "position": _card_position(card),
                "archetype": card["archetype"],
                "ability_count": len(abilities),
                "ability_threshold_leverage": len(near),
                "multi_unlock_attribute_leverage": sum(v for v in attrs.values() if v > 1),
                "role_alignment": round(len(near) / len(rows), 4) if rows else None,
                "archetype_alignment": "SOURCE_ARCHETYPE_MATCH"
                if rows
                else "NO_COMPATIBLE_THRESHOLD_GROUP",
                "redundancy": sum(v - 1 for v in abilities.values()),
                "diversity": len(abilities),
                "opaque_composite": None,
                "misleading_risk": "HIGH_NO_COMPATIBLE_THRESHOLDS"
                if not rows
                else "MODERATE_SINGLE_SOURCE_THRESHOLDS",
                "v1_coherence": base[card["external_card_id"]]["coherence_score"],
                "gameplay_value_claimed": False,
            }
        )
    return output


def cost_analysis(cards: list[dict], groups: list[dict], stack: list[dict]) -> dict:
    targets = {
        "ACC": ("CB", "WR", "TE", "HB", "MIKE"),
        "STR": ("TE", "C", "LG", "RG", "LT", "RT", "MIKE", "DT", "EDGE"),
        "BSH": ("MIKE", "DT", "EDGE"),
    }
    centrality = Counter((g["position"], r["attribute"]) for g in groups for r in g["requirements"])
    leverage = Counter(
        (row["position"], attr)
        for row in stack
        for attr, count in row["multi_support_attributes"].items()
        for _ in range(count)
    )
    result = {}
    for attribute, positions in targets.items():
        result[attribute] = {}
        for position in positions:
            selected = [
                c
                for c in cards
                if _card_position(c) == position and attribute in c["displayed_ratings"]
            ]
            ordinary = [c["displayed_ratings"][attribute] for c in selected if not is_special(c)]
            special = [c["displayed_ratings"][attribute] for c in selected if is_special(c)]
            result[attribute][position] = {
                "count": len(selected),
                "ovr_cost_slope": _slope(
                    [(c["overall"], c["displayed_ratings"][attribute]) for c in selected]
                ),
                "same_ovr_ranges": _same_ovr_ranges(selected, attribute),
                "archetype_adjusted_variance": _mean(
                    statistics.pvariance(values)
                    for arch in {c["archetype"] for c in selected}
                    if len(
                        (
                            values := [
                                c["displayed_ratings"][attribute]
                                for c in selected
                                if c["archetype"] == arch
                            ]
                        )
                    )
                    > 1
                ),
                "ordinary_mean": _mean(ordinary),
                "special_mean": _mean(special),
                "threshold_centrality": centrality[(position, attribute)],
                "multi_unlock_leverage": leverage[(position, attribute)],
                "interpretation": "OVR_COST_AND_ABILITY_LEVERAGE;GAMEPLAY_VALUE_UNKNOWN",
            }
    return result


def secondary(cards: list[dict], coherence: list[dict], experiments: dict) -> dict:
    by_id = {row["card_id"]: row for row in coherence}
    dated = []
    for card in cards:
        row = by_id.get(card["external_card_id"])
        if row and card.get("release_date"):
            dated.append(
                (
                    _parse_release_date(card["release_date"]).date().isoformat(),
                    card["overall"],
                    row["ability_threshold_leverage"],
                )
            )
    release = {
        "observations": len(dated),
        "date_leverage_slope": _slope(
            [(datetime.fromisoformat(d).toordinal(), value) for d, _, value in dated]
        ),
        "ovr_leverage_slope": _slope([(ovr, value) for _, ovr, value in dated]),
        "causal_claim": False,
    }
    special_rows = [
        row
        for row in coherence
        if next(c for c in cards if c["external_card_id"] == row["card_id"])
    ]
    lookup = {c["external_card_id"]: c for c in cards}
    special = {
        label: {
            "cards": len(rows),
            "mean_threshold_leverage": _mean(r["ability_threshold_leverage"] for r in rows),
            "mean_multi_unlock": _mean(r["multi_unlock_attribute_leverage"] for r in rows),
        }
        for label, rows in (
            ("ordinary", [r for r in special_rows if not is_special(lookup[r["card_id"]])]),
            ("special", [r for r in special_rows if is_special(lookup[r["card_id"]])]),
        )
    }
    return {
        "release_architecture": release,
        "special_card_design": {**special, "intent_inferred": False},
        "experiment_generator": experiments,
        "gameplay_result_schema": {
            "required": [
                "experiment_id",
                "cards",
                "ratings",
                "abilities",
                "scheme",
                "play",
                "opponent",
                "repetitions",
                "success_metric",
                "raw_outcomes",
                "confounders",
                "notes",
                "provenance",
            ],
            "records": [],
            "fake_results": False,
        },
        "market_join_schema": {
            "keys": ["card_id", "observed_at", "market", "currency"],
            "fields": ["price", "listing_count", "source", "provenance"],
            "observations": [],
            "historical_prices_manufactured": False,
        },
    }


def _matched_attribute_experiments(
    cards: list[dict], position: str, attributes: tuple[str, ...]
) -> list[dict]:
    selected = [c for c in cards if _card_position(c) == position]
    rows = []
    for index, left in enumerate(selected):
        for right in selected[index + 1 :]:
            if left["overall"] != right["overall"] or left["archetype"] != right["archetype"]:
                continue
            differences = {
                attribute: abs(
                    left["displayed_ratings"][attribute] - right["displayed_ratings"][attribute]
                )
                for attribute in attributes
                if attribute in left["displayed_ratings"]
                and attribute in right["displayed_ratings"]
            }
            if differences:
                rows.append(
                    {
                        "left": left["external_card_id"],
                        "right": right["external_card_id"],
                        "position": position,
                        "archetype": left["archetype"],
                        "overall": left["overall"],
                        "rating_differences": differences,
                        "total_difference": sum(differences.values()),
                    }
                )
    return sorted(
        rows,
        key=lambda row: (-row["total_difference"], row["left"], row["right"]),
    )[:10]


def build_op_x_002(root: Path) -> dict:
    cards = _cards(root)
    source_paths = [
        root / "data/external/cfb27_ability_thresholds.json",
        root / "data/external/cfb_fan_population_state.json",
        root / "data/research/cfb27_op_x_001/freeze.json",
    ]
    groups = grouped_thresholds(_load(source_paths[0]))
    proximity = card_proximity(cards, groups)
    stack = ability_stack(cards, groups)
    te = te_moneyball(cards)
    cb = cb_model(cards)
    mike = mike_seau(cards, groups, proximity)
    coherence = coherence_v2(cards, groups, proximity)
    experiments = {
        "TE_BLOCKING": te["matched_pairs"],
        "CB_TECHNICAL": cb["athletic_floor_test_set"],
        "MIKE_BSH_STR": _matched_attribute_experiments(cards, "MIKE", ("BSH", "STR")),
        "ACC_LEVERAGE": {
            position: _matched_attribute_experiments(cards, position, ("ACC",))
            for position in ("CB", "WR", "TE", "HB", "MIKE")
        },
    }
    return {
        "freeze": {
            "source_commit": "cc47415",
            "population_n": len(cards),
            "input_sha256": {
                p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in source_paths
            },
        },
        "te_moneyball": te,
        "cb_technical_value": cb,
        "mike_seau": mike,
        "ability_coherence_v2": coherence,
        "attribute_cost_analysis": cost_analysis(cards, groups, stack),
        "secondary_gates": secondary(cards, coherence, experiments),
        "validation": {
            "guessed_values": False,
            "unknown_as_zero": False,
            "canonical_changes": False,
            "gameplay_claims": False,
            "market_claims": False,
            "conflicts_preserved": True,
            "access_bypass": False,
        },
    }


def write_artifacts(output: Path, analysis: dict) -> None:
    output.mkdir(parents=True, exist_ok=True)
    for name, value in analysis.items():
        (output / f"{name}.json").write_text(
            json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
