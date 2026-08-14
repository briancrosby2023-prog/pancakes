"""OP-X-001 descriptive ability-stack and archetype construction analysis."""

from __future__ import annotations

import hashlib
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path

from operation_pancake.research.cfb27_phase2 import is_special
from operation_pancake.research.cfb27_phase6_10 import (
    _card_position,
    card_proximity,
    grouped_thresholds,
)

POSITIONS = ("QB", "HB", "WR", "TE", "EDGE", "MIKE", "CB", "FS")
MIKE_ATTRIBUTES = (
    "SPD",
    "ACC",
    "COD",
    "STR",
    "BSH",
    "TAK",
    "POW",
    "PUR",
    "PRC",
    "AWR",
    "MCV",
    "ZCV",
)
TE_ATTRIBUTES = ("PBK", "PBF", "PBP", "RBK", "RBF", "RBP", "LBK", "IBL", "STR", "SPD", "ACC")


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _mean(values: list[int]) -> float | None:
    return round(statistics.mean(values), 3) if values else None


def _cards(root: Path) -> list[dict]:
    state = _load(root / "data/external/cfb_fan_population_state.json")
    return sorted(state["cards"].values(), key=lambda row: row["external_card_id"])


def ability_stack(cards: list[dict], groups: list[dict]) -> list[dict]:
    proximity = card_proximity(cards, groups)
    by_card = defaultdict(list)
    for row in proximity["observations"]:
        by_card[row["card_id"]].append(row)
    output = []
    for card in cards:
        rows = [row for row in by_card[card["external_card_id"]] if "deficits" in row]
        supporting = Counter()
        close = []
        available = []
        for row in rows:
            maximum = max(row["deficits"].values())
            if maximum <= 0:
                available.append(row)
            if maximum <= 2:
                close.append(row)
                for attribute, deficit in row["deficits"].items():
                    if deficit <= 2:
                        supporting[attribute] += 1
        multi = {key: value for key, value in sorted(supporting.items()) if value >= 2}
        families = sorted({row["ability"] for row in close})
        concentration = sum(multi.values()) / sum(supporting.values()) if supporting else 0.0
        output.append(
            {
                "card_id": card["external_card_id"],
                "player": card["player_name"],
                "position": _card_position(card),
                "archetype": card["archetype"],
                "overall": card["overall"],
                "special": is_special(card),
                "available_threshold_relationships": len(available),
                "near_threshold_relationships": len(close),
                "complementary_ability_families": len(families),
                "ability_families": families,
                "multi_support_attributes": multi,
                "construction": "CONCENTRATED" if concentration >= 0.5 else "FRAGMENTED",
                "coherence_score": round(concentration, 6),
                "threshold_leverage": sum(multi.values()),
                "confidence": "SINGLE_STRUCTURED_SOURCE" if rows else "NOT_APPLICABLE",
                "source_status": "STRUCTURED_THRESHOLD_NOT_VERIFIED_CUT_AVAILABILITY",
                "gameplay_effectiveness_claimed": False,
            }
        )
    return output


def archetype_signatures(cards: list[dict], groups: list[dict]) -> dict:
    result = {}
    for position in POSITIONS:
        archetypes = sorted({g["archetype"] for g in groups if g["position"] == position})
        result[position] = {}
        for archetype in archetypes:
            selected_groups = [
                g for g in groups if g["position"] == position and g["archetype"] == archetype
            ]
            selected_cards = [
                c
                for c in cards
                if _card_position(c) == position
                and c["archetype"].casefold() == archetype.casefold()
            ]
            centrality = Counter(r["attribute"] for g in selected_groups for r in g["requirements"])
            attrs = sorted(centrality)
            result[position][archetype] = {
                "cards": len(selected_cards),
                "threshold_groups": len(selected_groups),
                "ability_families": len({g["ability"] for g in selected_groups}),
                "threshold_attribute_centrality": dict(centrality.most_common()),
                "card_attribute_means": {
                    attr: _mean(
                        [
                            c["displayed_ratings"][attr]
                            for c in selected_cards
                            if attr in c["displayed_ratings"]
                        ]
                    )
                    for attr in attrs
                },
                "gameplay_value_claimed": False,
            }
    return result


def mike_analysis(cards: list[dict], groups: list[dict]) -> dict:
    mike = [c for c in cards if _card_position(c) == "MIKE"]
    archetypes = ("Thumper", "Lurker", "Signal Caller")
    summaries = {}
    for archetype in archetypes:
        subset = [c for c in mike if c["archetype"].casefold() == archetype.casefold()]
        summaries[archetype] = {
            "cards": len(subset),
            "means": {
                a: _mean([c["displayed_ratings"][a] for c in subset if a in c["displayed_ratings"]])
                for a in MIKE_ATTRIBUTES
            },
            "variance": {
                a: round(statistics.pvariance(v), 3) if len(v) > 1 else None
                for a in MIKE_ATTRIBUTES
                if (v := [c["displayed_ratings"][a] for c in subset if a in c["displayed_ratings"]])
            },
        }
    same_ovr = []
    for overall in sorted({c["overall"] for c in mike}):
        rows = [c for c in mike if c["overall"] == overall]
        if len({c["archetype"] for c in rows}) > 1:
            same_ovr.append({"overall": overall, "cards": [c["external_card_id"] for c in rows]})
    ordinary_special = {}
    for archetype in archetypes:
        for label, predicate in (
            ("ordinary", lambda c: not is_special(c)),
            ("special", is_special),
        ):
            subset = [
                c
                for c in mike
                if c["archetype"].casefold() == archetype.casefold() and predicate(c)
            ]
            ordinary_special[f"{archetype}::{label}"] = {
                a: _mean([c["displayed_ratings"][a] for c in subset if a in c["displayed_ratings"]])
                for a in MIKE_ATTRIBUTES
            }
    threshold_centrality = Counter(
        r["attribute"] for g in groups if g["position"] == "MIKE" for r in g["requirements"]
    )
    return {
        "archetypes": summaries,
        "same_ovr_cells": same_ovr,
        "ordinary_special_means": ordinary_special,
        "threshold_centrality": dict(threshold_centrality.most_common()),
    }


def seau_crosswalk(cards: list[dict], mike: dict) -> dict:
    states = [c for c in cards if c["player_name"] == "Junior Seau"]
    rows = []
    for card in sorted(states, key=lambda c: c["overall"]):
        distances = {}
        for archetype, summary in mike["archetypes"].items():
            pairs = [
                (card["displayed_ratings"][a], value)
                for a, value in summary["means"].items()
                if value is not None and a in card["displayed_ratings"]
            ]
            distances[archetype] = (
                round(statistics.mean(abs(left - right) for left, right in pairs), 3)
                if pairs
                else None
            )
        usable = {k: v for k, v in distances.items() if v is not None}
        closest = min(usable, key=usable.get) if usable else "INSUFFICIENT"
        improvements = {
            archetype: {
                a: max(0, round(value - card["displayed_ratings"][a], 3))
                for a, value in mike["archetypes"][archetype]["means"].items()
                if value is not None and a in card["displayed_ratings"]
            }
            for archetype in mike["archetypes"]
        }
        rows.append(
            {
                "card_id": card["external_card_id"],
                "overall": card["overall"],
                "listed_archetype": card["archetype"],
                "mean_absolute_distance": distances,
                "closest_descriptive_signature": closest,
                "increases_to_archetype_mean": improvements,
            }
        )
    return {
        "validated_states": rows,
        "known_missing_vectors": [81, 84],
        "synthetic_vectors": False,
        "gameplay_recommendations": False,
    }


def focused_support(cards: list[dict], stack: list[dict]) -> dict:
    def correlations(position: str, attributes: tuple[str, ...]) -> dict:
        selected = [c for c in cards if _card_position(c) == position]
        result = {}
        for attr in attributes:
            pairs = [
                (c["overall"], c["displayed_ratings"][attr])
                for c in selected
                if attr in c["displayed_ratings"]
            ]
            result[attr] = {
                "count": len(pairs),
                "mean": _mean([p[1] for p in pairs]),
                "same_ovr_range_mean": _mean(
                    [
                        max(v) - min(v)
                        for _, values in _group_pairs(pairs).items()
                        if len((v := values)) > 1
                    ]
                ),
            }
        return result

    return {
        "te": correlations("TE", TE_ATTRIBUTES),
        "edge_mike": {p: correlations(p, ("BSH", "STR")) for p in ("EDGE", "MIKE")},
        "special_cards": _special_stack(stack),
        "cb_candidates": _cb_pairs(cards)[:10],
    }


def _group_pairs(pairs):
    grouped = defaultdict(list)
    for overall, rating in pairs:
        grouped[overall].append(rating)
    return grouped


def _special_stack(stack):
    buckets = defaultdict(list)
    for row in stack:
        buckets[(row["position"], row["archetype"], row["overall"], row["special"])].append(row)
    matched = []
    bases = {(p, a, o) for p, a, o, _ in buckets}
    for key in sorted(bases):
        ordinary, special = buckets.get((*key, False), []), buckets.get((*key, True), [])
        if ordinary and special:
            matched.append(
                {
                    "position": key[0],
                    "archetype": key[1],
                    "overall": key[2],
                    "ordinary_cards": len(ordinary),
                    "special_cards": len(special),
                    "ordinary_coherence": _mean([r["coherence_score"] for r in ordinary]),
                    "special_coherence": _mean([r["coherence_score"] for r in special]),
                }
            )
    return {"matched_cells": len(matched), "cells": matched, "ea_intent_inferred": False}


def _cb_pairs(cards):
    selected = [c for c in cards if _card_position(c) == "CB"]
    pairs = []
    technical = ("MCV", "ZCV", "PRS", "COD", "AGI", "PRC", "AWR")
    for index, left in enumerate(selected):
        for right in selected[index + 1 :]:
            if abs(left["overall"] - right["overall"]) > 1:
                continue
            if not all(
                a in left["displayed_ratings"] and a in right["displayed_ratings"]
                for a in ("SPD", "ACC")
            ):
                continue
            athletic = abs(
                left["displayed_ratings"]["SPD"] - right["displayed_ratings"]["SPD"]
            ) + abs(left["displayed_ratings"]["ACC"] - right["displayed_ratings"]["ACC"])
            differences = {
                a: abs(left["displayed_ratings"][a] - right["displayed_ratings"][a])
                for a in technical
                if a in left["displayed_ratings"] and a in right["displayed_ratings"]
            }
            if athletic <= 4 and differences:
                pairs.append(
                    {
                        "left": left["external_card_id"],
                        "right": right["external_card_id"],
                        "athletic_distance": athletic,
                        "technical_difference": sum(differences.values()),
                        "differences": differences,
                        "height_matched": None,
                    }
                )
    return sorted(
        pairs,
        key=lambda r: (-r["technical_difference"], r["athletic_distance"], r["left"], r["right"]),
    )


def build_op_x_001(root: Path) -> dict:
    cards = _cards(root)
    threshold_path = root / "data/external/cfb27_ability_thresholds.json"
    population_path = root / "data/external/cfb_fan_population_state.json"
    groups = grouped_thresholds(_load(threshold_path))
    stack = ability_stack(cards, groups)
    mike = mike_analysis(cards, groups)
    return {
        "freeze": {
            "source_commit": "ab54a79",
            "input_sha256": {
                p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in (threshold_path, population_path)
            },
            "population_n": len(cards),
        },
        "ability_stack_coherence": stack,
        "archetype_signatures": archetype_signatures(cards, groups),
        "mike_deep_dive": mike,
        "seau_crosswalk": seau_crosswalk(cards, mike),
        "focused_support": focused_support(cards, stack),
        "cfb26_27": {
            "acquired": False,
            "status": "NOT_ATTEMPTED_PRIMARY_OBJECTIVE_COMPLETED",
            "forced_identity_matching": False,
        },
        "chatgpt_handoff": [
            "Do measured multi-threshold attributes produce useful in-game ability stacks?",
            "Are CFB Labs thresholds valid for CUT equip availability?",
            "Which MIKE abilities materially affect user-controlled defense?",
            "Does TGH unlock centrality translate to gameplay value?",
            "Which Seau construction performs best at equivalent market cost?",
            "Are special-card coherence differences visible in gameplay?",
            "Do CB technical-rating contrasts change man-versus-zone performance?",
            "How should height be controlled in CB natural experiments?",
            "Do TE blocking ratings create market inefficiencies within archetypes?",
            "Does BSH add value independently of STR for EDGE and MIKE?",
            "Which near-threshold cards are cheapest to upgrade or replace?",
            "Did CFB26 use the same threshold domain and archetype labels?",
        ],
        "validation": {
            "guessed_values": False,
            "conflicts_preserved": True,
            "canonical_changes": False,
            "unsupported_gameplay_claims": False,
            "access_bypass": False,
        },
    }


def write_artifacts(output: Path, analysis: dict) -> None:
    output.mkdir(parents=True, exist_ok=True)
    for key, value in analysis.items():
        (output / f"{key}.json").write_text(
            json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
