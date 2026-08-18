#!/usr/bin/env python3
"""Execute OP-X-012E.14 cross-position component evidence experiments.

This is deliberately E.14-only. It builds the canonical Alpha population,
constructs cross-position matched contrasts under three prespecified calipers,
measures remaining-vector imbalance, runs position/archetype holdouts and
negative controls, retains strongest contradictions, and emits conservative
scientific verdicts. It does not execute E.15.
"""
from __future__ import annotations

import hashlib
import json
import math
import statistics
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path

from operation_pancake.research.cfb27_alpha_population import build_alpha_population

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/research/cfb27_e14/evidence_matrix.json"
DISCOVERY = ROOT / "data/research/cfb27_e14/execution_discovery.json"
FAMILIES = {
    "BSH": ({"FS", "SS"}, {"SAM", "MIKE", "WILL"}, {"LEDG", "REDG"}),
    "PRC": ({"FS", "SS"}, {"CB"}, {"SAM", "MIKE", "WILL"}),
    "SPD": ({"CB"}, {"FS", "SS"}, {"SAM", "MIKE", "WILL"}),
    "PMV": ({"MIKE"}, {"LEDG", "REDG"}, {"DT"}),
    "FMV": ({"MIKE"}, {"LEDG", "REDG"}, {"DT"}),
}
SPECS = {
    "strict": {"ovr": 0, "caliper": 0.50, "exact_arch": True},
    "moderate": {"ovr": 1, "caliper": 0.75, "exact_arch": False},
    "broad": {"ovr": 1, "caliper": 1.00, "exact_arch": False},
}
NEGATIVE = {
    "BSH": "JMP",
    "PRC": "CAR",
    "SPD": "TRK",
    "PMV": "CTH",
    "FMV": "CTH",
}


def eligible(card: dict) -> bool:
    ratings = card.get("displayed_ratings") or {}
    metadata = card.get("metadata") or {}
    return (
        card.get("extraction_status") == "COMPLETE"
        and isinstance(card.get("overall"), int)
        and card.get("position")
        and card.get("archetype")
        and len(ratings) >= 15
        and all(isinstance(value, int) and 0 <= value <= 99 for value in ratings.values())
        and not metadata.get("dynamic_state")
        and not metadata.get("projected_state")
    )


def fingerprint(cards: list[dict]) -> str:
    rows = [
        {
            "id": card["external_card_id"],
            "p": card["position"],
            "a": card["archetype"],
            "o": card["overall"],
            "r": dict(sorted(card["displayed_ratings"].items())),
        }
        for card in sorted(cards, key=lambda item: item["external_card_id"])
    ]
    payload = json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def mean(xs: list[float]) -> float | None:
    return sum(xs) / len(xs) if xs else None


def median(xs: list[float]) -> float | None:
    return statistics.median(xs) if xs else None


def q(xs: list[float], p: float) -> float | None:
    if not xs:
        return None
    ys = sorted(xs)
    index = (len(ys) - 1) * p
    lo = int(index)
    hi = min(lo + 1, len(ys) - 1)
    return ys[lo] + (ys[hi] - ys[lo]) * (index - lo)


def stats(xs: list[float]) -> dict:
    return {
        "n": len(xs),
        "mean": mean(xs),
        "median": median(xs),
        "q10": q(xs, 0.1),
        "q90": q(xs, 0.9),
    }


def scales(cards: list[dict], target: str) -> dict[str, tuple[float, float]]:
    vals: dict[str, list[float]] = defaultdict(list)
    for card in cards:
        for rating, value in card["displayed_ratings"].items():
            if rating != target:
                vals[rating].append(value)

    out = {}
    for rating, xs in vals.items():
        if len(xs) < 20:
            continue
        mu = sum(xs) / len(xs)
        sd = statistics.pstdev(xs)
        if sd > 0:
            out[rating] = (mu, sd)
    return out


def distance(
    a: dict,
    b: dict,
    target: str,
    z: dict[str, tuple[float, float]],
) -> tuple[float, int]:
    a_ratings = a["displayed_ratings"]
    b_ratings = b["displayed_ratings"]
    keys = [
        key
        for key in a_ratings.keys() & b_ratings.keys() & z.keys()
        if key != target
    ]
    if len(keys) < 8:
        return math.inf, len(keys)
    distances = [((a_ratings[key] - b_ratings[key]) / z[key][1]) ** 2 for key in keys]
    return math.sqrt(sum(distances) / len(distances)), len(keys)


def group_index(position: str, groups: tuple[set[str], ...]) -> int:
    return next(index for index, group in enumerate(groups) if position in group)


def candidate_pairs(
    lefts: list[dict],
    rights: list[dict],
    same_ovr: bool,
):
    if same_ovr:
        return combinations(lefts, 2)
    return (
        (a, b)
        for a in lefts
        for b in rights
        if a["external_card_id"] < b["external_card_id"]
    )


def candidates(
    cards: list[dict],
    target: str,
    groups: tuple[set[str], ...],
    spec: dict,
) -> list[dict]:
    z = scales(cards, target)
    rows = []
    by_ovr: dict[int, list[dict]] = defaultdict(list)
    for card in cards:
        by_ovr[card["overall"]].append(card)

    for ovr, lefts in by_ovr.items():
        same_ovr = spec["ovr"] == 0
        rights = lefts if same_ovr else lefts + by_ovr.get(ovr + 1, [])
        for a, b in candidate_pairs(lefts, rights, same_ovr):
            same_position = a["position"] == b["position"]
            same_group = group_index(a["position"], groups) == group_index(b["position"], groups)
            if same_position or same_group:
                continue

            ovr_delta = abs(a["overall"] - b["overall"])
            exact_arch_mismatch = spec["exact_arch"] and a["archetype"] != b["archetype"]
            if ovr_delta > spec["ovr"] or exact_arch_mismatch:
                continue

            pair_distance, dims = distance(a, b, target, z)
            if pair_distance <= spec["caliper"]:
                rows.append(
                    {
                        "a": a,
                        "b": b,
                        "distance": pair_distance,
                        "dims": dims,
                        "ovr_delta": b["overall"] - a["overall"],
                        "target_delta": (
                            b["displayed_ratings"][target] - a["displayed_ratings"][target]
                        ),
                    }
                )
    return rows


def greedy_unique(rows: list[dict]) -> list[dict]:
    used = set()
    out = []
    for row in sorted(rows, key=lambda item: item["distance"]):
        ids = (row["a"]["external_card_id"], row["b"]["external_card_id"])
        if ids[0] in used or ids[1] in used:
            continue
        used.update(ids)
        out.append(row)
    return out


def summarize_matches(rows: list[dict], target: str) -> dict:
    same = [row for row in rows if row["ovr_delta"] == 0]
    boundary = [row for row in rows if row["ovr_delta"] != 0]
    pos: dict[str, list[float]] = defaultdict(list)
    arch: dict[str, list[float]] = defaultdict(list)

    for row in rows:
        pos_key = "|".join(sorted((row["a"]["position"], row["b"]["position"])))
        pos[pos_key].append(abs(row["target_delta"]))
        arch_key = "|".join(sorted((row["a"]["archetype"], row["b"]["archetype"])))
        arch[arch_key].append(abs(row["target_delta"]))

    contradictions = sorted(
        rows,
        key=lambda row: (abs(row["target_delta"]), -row["distance"]),
        reverse=True,
    )[:20]
    return {
        "accepted_matches": len(rows),
        "independent_card_pairs": len(rows),
        "remaining_vector_distance": stats([row["distance"] for row in rows]),
        "same_ovr_target_abs_delta": stats(
            [abs(row["target_delta"]) for row in same]
        ),
        "adjacent_ovr_target_delta": stats(
            [
                row["target_delta"] * (1 if row["ovr_delta"] > 0 else -1)
                for row in boundary
            ]
        ),
        "position_pair_median_abs_delta": {
            key: median(values)
            for key, values in sorted(pos.items())
            if len(values) >= 3
        },
        "archetype_pair_median_abs_delta": {
            key: median(values)
            for key, values in sorted(arch.items())
            if len(values) >= 3
        },
        "strongest_counterexamples": [
            {
                "a": row["a"]["external_card_id"],
                "b": row["b"]["external_card_id"],
                "positions": [row["a"]["position"], row["b"]["position"]],
                "archetypes": [row["a"]["archetype"], row["b"]["archetype"]],
                "ovr": [row["a"]["overall"], row["b"]["overall"]],
                target: [
                    row["a"]["displayed_ratings"][target],
                    row["b"]["displayed_ratings"][target],
                ],
                "distance": row["distance"],
            }
            for row in contradictions
        ],
    }


def normalized_target_value(row: dict) -> float:
    if row["ovr_delta"] == 0:
        return abs(row["target_delta"])
    return row["target_delta"] * (1 if row["ovr_delta"] > 0 else -1)


def holdouts(rows: list[dict], target: str) -> dict:
    del target
    by_pos: dict[str, list[float]] = defaultdict(list)
    by_arch: dict[str, list[float]] = defaultdict(list)

    for row in rows:
        value = normalized_target_value(row)
        by_pos[row["a"]["position"]].append(value)
        by_pos[row["b"]["position"]].append(value)
        by_arch[row["a"]["archetype"]].append(value)
        by_arch[row["b"]["archetype"]].append(value)

    return {
        "leave_one_position_out": {
            key: stats(values)
            for key, values in sorted(by_pos.items())
            if len(values) >= 5
        },
        "archetype_holdout": {
            key: stats(values)
            for key, values in sorted(by_arch.items())
            if len(values) >= 5
        },
    }


def verdict(specs: dict) -> tuple[str, bool, str]:
    medians = [
        value["same_ovr_target_abs_delta"]["median"]
        for value in specs.values()
        if value["same_ovr_target_abs_delta"]["n"] >= 10
    ]
    if len(medians) < 2:
        return (
            "INSUFFICIENT EVIDENCE",
            False,
            "fewer than two specifications have >=10 same-OVR matches",
        )

    unstable = max(medians) - min(medians) > 2.0
    if unstable:
        return (
            "CONFOUNDED",
            True,
            "same-OVR target contrast is materially specification-sensitive",
        )

    # E.14 is reverse engineering: large target variation among otherwise similar
    # same-OVR cards is evidence against a single interchangeable cross-position
    # contribution, not proof of a position coefficient.
    if median(medians) <= 2.0:
        return (
            "SHARED COMPONENT",
            False,
            "matched same-OVR target differences are small and stable",
        )
    return (
        "POSITION-SCALED COMPONENT",
        False,
        "stable matched same-OVR target differences remain material across position groups",
    )


def family(cards: list[dict], target: str, groups: tuple[set[str], ...]) -> dict:
    positions = set().union(*groups)
    members = [
        card
        for card in cards
        if card["position"] in positions and target in card["displayed_ratings"]
    ]
    spec_results = {}
    raw_counts = {}

    for name, spec in SPECS.items():
        raw = candidates(members, target, groups, spec)
        raw_counts[name] = len(raw)
        matched = greedy_unique(raw) if name != "broad" else raw
        summary = summarize_matches(matched, target)
        summary["candidate_count"] = len(raw)
        summary["holdouts"] = holdouts(matched, target)
        spec_results[name] = summary

    label, unstable, rationale = verdict(spec_results)
    negative_rating = NEGATIVE[target]
    negative_result = {"rating": negative_rating, "available": False}
    negative_members = [
        card for card in members if negative_rating in card["displayed_ratings"]
    ]
    if len(negative_members) >= 50:
        negative_rows = greedy_unique(
            candidates(negative_members, negative_rating, groups, SPECS["moderate"])
        )
        negative_result = {
            "rating": negative_rating,
            "available": True,
            "moderate": summarize_matches(negative_rows, negative_rating),
        }

    return {
        "target": target,
        "eligible_cards": len(members),
        "positions": sorted(positions),
        "position_counts": dict(
            sorted(Counter(card["position"] for card in members).items())
        ),
        "native_position_archetype_ovr_strata": len(
            {
                (card["position"], card["archetype"], card["overall"])
                for card in members
            }
        ),
        "specifications": spec_results,
        "negative_control": negative_result,
        "alternative_hypotheses": {
            "H_shared": "single cross-position contribution",
            "H_position": "position-scaled contribution",
            "H_archetype": "archetype-scaled contribution",
        },
        "verdict": label,
        "unstable": unstable,
        "rationale": rationale,
        "raw_candidate_counts": raw_counts,
    }


def main() -> None:
    population = build_alpha_population(ROOT)
    all_cards = list(population["cards"].values())
    cards = [card for card in all_cards if eligible(card)]
    result = {
        "stage": "E.14_CROSS_POSITION_COMPONENT_EVIDENCE",
        "e15_started": False,
        "population": {
            "input_records": len(all_cards),
            "eligible_records": len(cards),
            "sha256": fingerprint(cards),
            "alpha_summary": population["summary"],
        },
        "method": {
            "specifications": SPECS,
            "target_excluded_from_confound_vector": True,
            "matching": "standardized RMS distance on shared non-target displayed ratings",
            "replacement": {"strict": False, "moderate": False, "broad": True},
        },
        "families": {
            target: family(cards, target, groups)
            for target, groups in FAMILIES.items()
        },
    }
    result["final_verdict_matrix"] = {
        target: {
            "verdict": family_result["verdict"],
            "unstable": family_result["unstable"],
            "rationale": family_result["rationale"],
        }
        for target, family_result in result["families"].items()
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    # Preserve the prior discovery artifact contract while marking execution advancement.
    if DISCOVERY.exists():
        discovery = json.loads(DISCOVERY.read_text())
        discovery["scientific_verdicts_emitted"] = True
        discovery["stage"] = "E.14_CROSS_POSITION_COMPONENT_EVIDENCE"
        discovery["e15_started"] = False
        DISCOVERY.write_text(
            json.dumps(discovery, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    print(
        f"E.14 population: {len(cards)}/{len(all_cards)} "
        f"sha256={result['population']['sha256']}"
    )
    for target, family_result in result["families"].items():
        matches = ",".join(
            f"{name}:{value['accepted_matches']}"
            for name, value in family_result["specifications"].items()
        )
        print(
            f"E.14 {target}: {family_result['verdict']} "
            f"unstable={family_result['unstable']} matches={matches}"
        )
    print(f"E.14 evidence artifact: {OUT.relative_to(ROOT)}")
    print("E.15 started: NO")


if __name__ == "__main__":
    main()
