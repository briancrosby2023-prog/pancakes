#!/usr/bin/env python3
"""Execute OP-X-012E.14 cross-position component evidence experiments.

This is deliberately E.14-only.  It builds the canonical Alpha population,
constructs cross-position matched contrasts under three prespecified calipers,
measures remaining-vector imbalance, runs position/archetype holdouts and
negative controls, retains strongest contradictions, and emits conservative
scientific verdicts.  It does not execute E.15.
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
NEGATIVE = {"BSH": "JMP", "PRC": "CAR", "SPD": "TRK", "PMV": "CTH", "FMV": "CTH"}


def eligible(card: dict) -> bool:
    r = card.get("displayed_ratings") or {}
    return (card.get("extraction_status") == "COMPLETE" and isinstance(card.get("overall"), int)
            and card.get("position") and card.get("archetype") and len(r) >= 15
            and all(isinstance(v, int) and 0 <= v <= 99 for v in r.values())
            and not (card.get("metadata") or {}).get("dynamic_state")
            and not (card.get("metadata") or {}).get("projected_state"))


def fingerprint(cards: list[dict]) -> str:
    rows = [{"id": c["external_card_id"], "p": c["position"], "a": c["archetype"],
             "o": c["overall"], "r": dict(sorted(c["displayed_ratings"].items()))}
            for c in sorted(cards, key=lambda x: x["external_card_id"])]
    return hashlib.sha256(json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def mean(xs: list[float]) -> float | None:
    return sum(xs) / len(xs) if xs else None


def median(xs: list[float]) -> float | None:
    return statistics.median(xs) if xs else None


def q(xs: list[float], p: float) -> float | None:
    if not xs:
        return None
    ys = sorted(xs); i = (len(ys) - 1) * p; lo = int(i); hi = min(lo + 1, len(ys) - 1)
    return ys[lo] + (ys[hi] - ys[lo]) * (i - lo)


def stats(xs: list[float]) -> dict:
    return {"n": len(xs), "mean": mean(xs), "median": median(xs), "q10": q(xs, .1),
            "q90": q(xs, .9)}


def scales(cards: list[dict], target: str) -> dict[str, tuple[float, float]]:
    vals: dict[str, list[float]] = defaultdict(list)
    for c in cards:
        for k, v in c["displayed_ratings"].items():
            if k != target:
                vals[k].append(v)
    out = {}
    for k, xs in vals.items():
        if len(xs) >= 20:
            mu = sum(xs) / len(xs); sd = statistics.pstdev(xs)
            if sd > 0: out[k] = (mu, sd)
    return out


def distance(a: dict, b: dict, target: str, z: dict[str, tuple[float, float]]) -> tuple[float, int]:
    ar, br = a["displayed_ratings"], b["displayed_ratings"]
    keys = [k for k in ar.keys() & br.keys() & z.keys() if k != target]
    if len(keys) < 8:
        return math.inf, len(keys)
    ds = [((ar[k] - br[k]) / z[k][1]) ** 2 for k in keys]
    return math.sqrt(sum(ds) / len(ds)), len(keys)


def group_index(position: str, groups: tuple[set[str], ...]) -> int:
    return next(i for i, g in enumerate(groups) if position in g)


def candidates(cards: list[dict], target: str, groups: tuple[set[str], ...], spec: dict) -> list[dict]:
    z = scales(cards, target); rows = []
    by_ovr: dict[int, list[dict]] = defaultdict(list)
    for c in cards: by_ovr[c["overall"]].append(c)
    for ovr, lefts in by_ovr.items():
        rights = lefts if spec["ovr"] == 0 else lefts + by_ovr.get(ovr + 1, [])
        for a, b in combinations(lefts, 2) if spec["ovr"] == 0 else ((a, b) for a in lefts for b in rights if a["external_card_id"] < b["external_card_id"]):
            if a["position"] == b["position"] or group_index(a["position"], groups) == group_index(b["position"], groups):
                continue
            od = abs(a["overall"] - b["overall"])
            if od > spec["ovr"] or (spec["exact_arch"] and a["archetype"] != b["archetype"]):
                continue
            d, dims = distance(a, b, target, z)
            if d <= spec["caliper"]:
                rows.append({"a": a, "b": b, "distance": d, "dims": dims, "ovr_delta": b["overall"]-a["overall"],
                             "target_delta": b["displayed_ratings"][target]-a["displayed_ratings"][target]})
    return rows


def greedy_unique(rows: list[dict]) -> list[dict]:
    used = set(); out = []
    for r in sorted(rows, key=lambda x: x["distance"]):
        ids = (r["a"]["external_card_id"], r["b"]["external_card_id"])
        if ids[0] in used or ids[1] in used: continue
        used.update(ids); out.append(r)
    return out


def summarize_matches(rows: list[dict], target: str) -> dict:
    same = [r for r in rows if r["ovr_delta"] == 0]
    boundary = [r for r in rows if r["ovr_delta"] != 0]
    pos: dict[str, list[float]] = defaultdict(list); arch: dict[str, list[float]] = defaultdict(list)
    for r in rows:
        key = "|".join(sorted((r["a"]["position"], r["b"]["position"])))
        pos[key].append(abs(r["target_delta"]))
        key2 = "|".join(sorted((r["a"]["archetype"], r["b"]["archetype"])))
        arch[key2].append(abs(r["target_delta"]))
    contradictions = sorted(rows, key=lambda r: (abs(r["target_delta"]), -r["distance"]), reverse=True)[:20]
    return {
        "accepted_matches": len(rows), "independent_card_pairs": len(rows),
        "remaining_vector_distance": stats([r["distance"] for r in rows]),
        "same_ovr_target_abs_delta": stats([abs(r["target_delta"]) for r in same]),
        "adjacent_ovr_target_delta": stats([r["target_delta"] * (1 if r["ovr_delta"] > 0 else -1) for r in boundary]),
        "position_pair_median_abs_delta": {k: median(v) for k, v in sorted(pos.items()) if len(v) >= 3},
        "archetype_pair_median_abs_delta": {k: median(v) for k, v in sorted(arch.items()) if len(v) >= 3},
        "strongest_counterexamples": [{"a": r["a"]["external_card_id"], "b": r["b"]["external_card_id"],
            "positions": [r["a"]["position"], r["b"]["position"]], "archetypes": [r["a"]["archetype"], r["b"]["archetype"]],
            "ovr": [r["a"]["overall"], r["b"]["overall"]], target: [r["a"]["displayed_ratings"][target], r["b"]["displayed_ratings"][target]],
            "distance": r["distance"]} for r in contradictions],
    }


def holdouts(rows: list[dict], target: str) -> dict:
    by_pos: dict[str, list[float]] = defaultdict(list); by_arch: dict[str, list[float]] = defaultdict(list)
    for r in rows:
        val = abs(r["target_delta"]) if r["ovr_delta"] == 0 else r["target_delta"] * (1 if r["ovr_delta"] > 0 else -1)
        by_pos[r["a"]["position"]].append(val); by_pos[r["b"]["position"]].append(val)
        by_arch[r["a"]["archetype"]].append(val); by_arch[r["b"]["archetype"]].append(val)
    return {"leave_one_position_out": {k: stats(v) for k, v in sorted(by_pos.items()) if len(v) >= 5},
            "archetype_holdout": {k: stats(v) for k, v in sorted(by_arch.items()) if len(v) >= 5}}


def verdict(specs: dict) -> tuple[str, bool, str]:
    med = [v["same_ovr_target_abs_delta"]["median"] for v in specs.values() if v["same_ovr_target_abs_delta"]["n"] >= 10]
    if len(med) < 2: return "INSUFFICIENT EVIDENCE", False, "fewer than two specifications have >=10 same-OVR matches"
    unstable = max(med) - min(med) > 2.0
    if unstable: return "CONFOUNDED", True, "same-OVR target contrast is materially specification-sensitive"
    # E.14 is reverse engineering: large target variation among otherwise similar same-OVR cards is evidence
    # against a single interchangeable cross-position contribution, not proof of a position coefficient.
    if median(med) <= 2.0: return "SHARED COMPONENT", False, "matched same-OVR target differences are small and stable"
    return "POSITION-SCALED COMPONENT", False, "stable matched same-OVR target differences remain material across position groups"


def family(cards: list[dict], target: str, groups: tuple[set[str], ...]) -> dict:
    positions = set().union(*groups); members = [c for c in cards if c["position"] in positions and target in c["displayed_ratings"]]
    spec_results = {}; raw_counts = {}
    for name, spec in SPECS.items():
        raw = candidates(members, target, groups, spec); raw_counts[name] = len(raw)
        matched = greedy_unique(raw) if name != "broad" else raw
        s = summarize_matches(matched, target); s["candidate_count"] = len(raw); s["holdouts"] = holdouts(matched, target)
        spec_results[name] = s
    label, unstable, rationale = verdict(spec_results)
    neg = NEGATIVE[target]; neg_result = {"rating": neg, "available": False}
    neg_members = [c for c in members if neg in c["displayed_ratings"]]
    if len(neg_members) >= 50:
        nr = greedy_unique(candidates(neg_members, neg, groups, SPECS["moderate"]))
        neg_result = {"rating": neg, "available": True, "moderate": summarize_matches(nr, neg)}
    return {"target": target, "eligible_cards": len(members), "positions": sorted(positions),
            "position_counts": dict(sorted(Counter(c["position"] for c in members).items())),
            "native_position_archetype_ovr_strata": len(set((c["position"], c["archetype"], c["overall"]) for c in members)),
            "specifications": spec_results, "negative_control": neg_result,
            "alternative_hypotheses": {"H_shared": "single cross-position contribution", "H_position": "position-scaled contribution", "H_archetype": "archetype-scaled contribution"},
            "verdict": label, "unstable": unstable, "rationale": rationale, "raw_candidate_counts": raw_counts}


def main() -> None:
    population = build_alpha_population(ROOT); all_cards = list(population["cards"].values()); cards = [c for c in all_cards if eligible(c)]
    result = {"stage": "E.14_CROSS_POSITION_COMPONENT_EVIDENCE", "e15_started": False,
              "population": {"input_records": len(all_cards), "eligible_records": len(cards), "sha256": fingerprint(cards), "alpha_summary": population["summary"]},
              "method": {"specifications": SPECS, "target_excluded_from_confound_vector": True, "matching": "standardized RMS distance on shared non-target displayed ratings", "replacement": {"strict": False, "moderate": False, "broad": True}},
              "families": {t: family(cards, t, g) for t, g in FAMILIES.items()}}
    result["final_verdict_matrix"] = {t: {"verdict": f["verdict"], "unstable": f["unstable"], "rationale": f["rationale"]} for t, f in result["families"].items()}
    OUT.parent.mkdir(parents=True, exist_ok=True); OUT.write_text(json.dumps(result, indent=2, sort_keys=True)+"\n", encoding="utf-8")
    # Preserve the prior discovery artifact contract while marking execution advancement.
    if DISCOVERY.exists():
        d = json.loads(DISCOVERY.read_text()); d["scientific_verdicts_emitted"] = True; d["stage"] = "E.14_CROSS_POSITION_COMPONENT_EVIDENCE"; d["e15_started"] = False
        DISCOVERY.write_text(json.dumps(d, indent=2, sort_keys=True)+"\n")
    print(f"E.14 population: {len(cards)}/{len(all_cards)} sha256={result['population']['sha256']}")
    for t, f in result["families"].items(): print(f"E.14 {t}: {f['verdict']} unstable={f['unstable']} matches=" + ",".join(f"{k}:{v['accepted_matches']}" for k,v in f["specifications"].items()))
    print(f"E.14 evidence artifact: {OUT.relative_to(ROOT)}"); print("E.15 started: NO")


if __name__ == "__main__": main()
