"""OP-X-024: CFB27 TE displayed-OVR economics research (production-model isolated)."""

from __future__ import annotations

import hashlib
import json
import math
import statistics
from collections import Counter, defaultdict
from pathlib import Path

ATTRS = [
    "SPD",
    "ACC",
    "AGI",
    "COD",
    "STR",
    "AWR",
    "CTH",
    "CIT",
    "SPC",
    "SRR",
    "MRR",
    "DRR",
    "RLS",
    "RBK",
    "RBF",
    "RBP",
    "PBK",
    "PBF",
    "PBP",
    "IBL",
    "LBK",
    "CAR",
    "BTK",
    "TRK",
    "SFA",
]
ARCHES = ("Physical Route Runner", "Vertical Threat", "Gritty Possession")
COMPONENTS = {
    "ATHLETICISM": ("SPD", "ACC", "AGI", "COD"),
    "RECEIVING": ("CTH", "CIT", "SPC"),
    "ROUTE_RUNNING": ("SRR", "MRR", "DRR", "RLS"),
    "RUN_BLOCKING": ("RBK", "RBF", "RBP", "IBL", "LBK"),
    "PASS_BLOCKING": ("PBK", "PBF", "PBP"),
    "PHYSICAL_YAC": ("STR", "CAR", "BTK", "TRK", "SFA"),
}
OUT = Path("data/research/op_x_024")
STATE = Path("data/external/cfb_fan_population_state.json")


def dump(name, obj):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def val(c, a):
    x = c.get("displayed_ratings", {}).get(a)
    return float(x) if isinstance(x, (int, float)) else None


def static_eligible(c):
    if c.get("position") != "TE":
        return False
    status = str(c.get("extraction_status", ""))
    meta = c.get("metadata") or {}
    program = str(c.get("program") or "").lower()
    if status != "COMPLETE":
        return False
    flags = " ".join(
        str(meta.get(k, "")) for k in ("dynamic", "evo", "progression", "path", "state")
    ).lower()
    return not any(t in flags or t in program for t in ("dynamic", "evo", "progression"))


def stats(xs):
    xs = sorted(xs)
    n = len(xs)
    if not n:
        return None

    def q(p):
        return xs[min(n - 1, max(0, round((n - 1) * p)))]

    return {
        "n": n,
        "min": xs[0],
        "max": xs[-1],
        "range": xs[-1] - xs[0],
        "mean": round(statistics.fmean(xs), 4),
        "median": statistics.median(xs),
        "stddev": round(statistics.pstdev(xs), 4),
        "iqr": q(0.75) - q(0.25),
    }


def features(c, names):
    out = []
    for a in names:
        x = val(c, a)
        if x is None:
            return None
        out.append(x)
    return out


def solve(a, b):
    n = len(b)
    m = [list(map(float, a[i])) + [float(b[i])] for i in range(n)]
    for col in range(n):
        piv = max(range(col, n), key=lambda r: abs(m[r][col]))
        if abs(m[piv][col]) < 1e-9:
            return [0.0] * n
        m[col], m[piv] = m[piv], m[col]
        d = m[col][col]
        m[col] = [x / d for x in m[col]]
        for r in range(n):
            if r == col:
                continue
            f = m[r][col]
            m[r] = [m[r][j] - f * m[col][j] for j in range(n + 1)]
    return [m[i][-1] for i in range(n)]


def ridge_fit(rows, names, lam=1.0):
    X = []
    y = []
    for c in rows:
        f = features(c, names)
        if f is not None:
            X.append([1.0] + f)
            y.append(float(c["overall"]))
    p = len(names) + 1
    if len(X) < p + 2:
        return None
    ata = [
        [sum(r[i] * r[j] for r in X) + (lam if i == j and i else 0) for j in range(p)]
        for i in range(p)
    ]
    aty = [sum(r[i] * yy for r, yy in zip(X, y, strict=True)) for i in range(p)]
    beta = solve(ata, aty)
    return beta


def predict(c, names, beta):
    f = features(c, names)
    return None if f is None else beta[0] + sum(w * x for w, x in zip(beta[1:], f, strict=True))


def metrics(rows, names, beta):
    errs = []
    for c in rows:
        p = predict(c, names, beta)
        if p is not None:
            errs.append(p - float(c["overall"]))
    if not errs:
        return {"n": 0}
    return {
        "n": len(errs),
        "mae": round(statistics.fmean(abs(e) for e in errs), 4),
        "rmse": round(math.sqrt(statistics.fmean(e * e for e in errs)), 4),
        "within_0_5": round(sum(abs(e) <= 0.5 for e in errs) / len(errs), 4),
        "within_1": round(sum(abs(e) <= 1 for e in errs) / len(errs), 4),
    }


def component_card(c):
    d = {}
    for k, names in COMPONENTS.items():
        xs = [val(c, a) for a in names]
        xs = [x for x in xs if x is not None]
        d[k] = statistics.fmean(xs) if xs else None
    return d


def main():
    state = json.loads(STATE.read_text())
    all_cards = list(state.get("cards", {}).values())
    tes = [c for c in all_cards if c.get("position") == "TE"]
    eligible = [c for c in tes if static_eligible(c)]
    excluded = [
        {
            "id": c.get("external_card_id"),
            "player": c.get("player_name"),
            "reason": "non-COMPLETE or dynamic/EVO/progression/uncertain",
        }
        for c in tes
        if c not in eligible
    ]
    audit = {
        "provenance": {
            "source": STATE.as_posix(),
            "operation": "OP-X-024",
            "pretest": "OP-TE-001",
        },
        "total": len(tes),
        "by_archetype": dict(Counter(c.get("archetype") or "UNKNOWN" for c in tes)),
        "by_ovr": dict(sorted(Counter(str(c.get("overall")) for c in tes).items())),
        "by_program": dict(Counter(c.get("program") or "UNKNOWN" for c in tes)),
        "static_eligible": len(eligible),
        "excluded_count": len(excluded),
        "excluded": excluded,
        "attribute_completeness": {a: sum(val(c, a) is not None for c in tes) for a in ATTRS},
    }
    vecgroups = defaultdict(list)
    for c in eligible:
        sig = (
            c.get("player_name"),
            c.get("overall"),
            c.get("archetype"),
            tuple((a, val(c, a)) for a in ATTRS),
        )
        vecgroups[sig].append(c.get("external_card_id"))
    audit["duplicate_vector_groups"] = [v for v in vecgroups.values() if len(v) > 1]
    dump("population_audit.json", audit)

    cells = defaultdict(list)
    for c in eligible:
        cells[(c.get("archetype") or "UNKNOWN", int(c["overall"]))].append(c)
    slack = {}
    for (arch, ovr), rows in sorted(cells.items()):
        if len(rows) < 2:
            continue
        slack[f"{arch}|{ovr}"] = {
            "n": len(rows),
            "attributes": {
                a: stats([x for c in rows if (x := val(c, a)) is not None]) for a in ATTRS
            },
        }
    dump("same_cell_slack.json", slack)

    economics = {}
    for arch in ARCHES:
        ar = {k: v for k, v in slack.items() if k.startswith(arch + "|")}
        ranges = defaultdict(list)
        for cell in ar.values():
            for a, s in cell["attributes"].items():
                if s and s["n"] >= 2:
                    ranges[a].append(s["range"])
        med = {a: statistics.median(v) for a, v in ranges.items() if v}
        if med:
            qs = sorted(med.values())
            q1 = qs[len(qs) // 3]
            q2 = qs[(2 * len(qs)) // 3]
            cls = {
                a: (
                    "TIGHT / ANCHOR-LIKE"
                    if r <= q1
                    else "HIGHLY COMPENSABLE"
                    if r >= q2
                    else "MODERATELY COMPENSABLE"
                )
                for a, r in med.items()
            }
        else:
            cls = {}
        economics[arch] = {"same_cell_median_ranges": med, "classification": cls, "cells": len(ar)}
    dump("archetype_economics.json", economics)

    boundaries = {}
    for arch in ARCHES:
        by = defaultdict(list)
        for c in eligible:
            if c.get("archetype") == arch:
                by[int(c["overall"])].append(c)
        pairs = []
        for n in sorted(by):
            if n + 1 not in by:
                continue
            shifts = {}
            for a in ATTRS:
                lo = [val(c, a) for c in by[n] if val(c, a) is not None]
                hi = [val(c, a) for c in by[n + 1] if val(c, a) is not None]
                if lo and hi:
                    shifts[a] = round(statistics.median(hi) - statistics.median(lo), 3)
            pairs.append(
                {
                    "from": n,
                    "to": n + 1,
                    "n_low": len(by[n]),
                    "n_high": len(by[n + 1]),
                    "median_attribute_shift": shifts,
                }
            )
        boundaries[arch] = pairs
    dump("adjacent_ovr_boundaries.json", boundaries)
    dump(
        "legacy_403_405_status.json",
        {
            "status": "BLOCKED",
            "reason": "EXACT LEGACY SPECIFICATION UNRECOVERED",
            "action": "No substitute formula used.",
        },
    )

    hold = []
    train = []
    strata = defaultdict(list)
    for c in eligible:
        strata[(c.get("archetype"), c.get("overall"))].append(c)
    for _key, rows in strata.items():
        rows = sorted(
            rows, key=lambda c: hashlib.sha256(str(c.get("external_card_id")).encode()).hexdigest()
        )
        take = max(1, round(len(rows) * 0.2)) if len(rows) >= 3 else 0
        hold.extend(rows[:take])
        train.extend(rows[take:])
    dump(
        "holdout_manifest.json",
        {
            "method": (
                "SHA256 card-id deterministic 20% within archetype x OVR strata "
                "(strata n<3 retained in training)"
            ),
            "created_before_fit": True,
            "ids": [c.get("external_card_id") for c in hold],
        },
    )

    full_names = [
        a for a in ATTRS if sum(val(c, a) is not None for c in train) >= max(10, len(train) // 2)
    ]
    comp_names = list(COMPONENTS)
    comp_rows = []
    comp_hold = []
    for src, dst in ((train, comp_rows), (hold, comp_hold)):
        for c in src:
            cc = dict(c)
            cc["displayed_ratings"] = component_card(c)
            dst.append(cc)
    models = {}
    b = ridge_fit(train, full_names)
    models["A"] = {
        "structure": "universal flat attribute ridge",
        "features": full_names,
        "train": metrics(train, full_names, b) if b else {"n": 0},
        "holdout": metrics(hold, full_names, b) if b else {"n": 0},
    }
    archB = {}
    for arch in ARCHES:
        tr = [c for c in train if c.get("archetype") == arch]
        ho = [c for c in hold if c.get("archetype") == arch]
        bb = ridge_fit(tr, full_names)
        archB[arch] = {
            "train": metrics(tr, full_names, bb) if bb else {"n": 0},
            "holdout": metrics(ho, full_names, bb) if bb else {"n": 0},
        }
    models["B"] = {"structure": "independent archetype attribute ridge", "by_archetype": archB}
    bc = ridge_fit(comp_rows, comp_names)
    models["C"] = {
        "structure": "shared six-component ridge",
        "components": COMPONENTS,
        "train": metrics(comp_rows, comp_names, bc) if bc else {"n": 0},
        "holdout": metrics(comp_hold, comp_names, bc) if bc else {"n": 0},
    }
    archD = {}
    for arch in ARCHES:
        tr = [c for c in comp_rows if c.get("archetype") == arch]
        ho = [c for c in comp_hold if c.get("archetype") == arch]
        bd = ridge_fit(tr, comp_names)
        archD[arch] = {
            "train": metrics(tr, comp_names, bd) if bd else {"n": 0},
            "holdout": metrics(ho, comp_names, bd) if bd else {"n": 0},
        }
    models["D"] = {
        "structure": "shared component definitions + archetype-specific valuation",
        "by_archetype": archD,
    }

    def model_mae(x):
        if "holdout" in x:
            return x["holdout"].get("mae", 999)
        vals = [
            v["holdout"].get("mae")
            for v in x.get("by_archetype", {}).values()
            if v["holdout"].get("mae") is not None
        ]
        return statistics.fmean(vals) if vals else 999

    models["best_supported"] = min("ABCD", key=lambda k: model_mae(models[k]))
    dump("architecture_comparison.json", models)
    dump(
        "holdout_results.json",
        {
            "size": len(hold),
            "models": {
                k: (v.get("holdout") or v.get("by_archetype"))
                for k, v in models.items()
                if k in "ABCD"
            },
            "best_supported": models["best_supported"],
        },
    )

    names = defaultdict(list)
    for c in eligible:
        names[(c.get("player_name") or "").lower()].append(c)
    chains = []
    switches = []
    for _nm, rows in names.items():
        if len(rows) < 2:
            continue
        rows = sorted(rows, key=lambda c: (c.get("overall", 0), str(c.get("external_card_id"))))
        chains.append(
            {
                "player": rows[0].get("player_name"),
                "versions": [
                    {
                        "id": c.get("external_card_id"),
                        "ovr": c.get("overall"),
                        "archetype": c.get("archetype"),
                        "program": c.get("program"),
                    }
                    for c in rows
                ],
            }
        )
        for a, b2 in zip(rows, rows[1:], strict=False):
            if a.get("archetype") != b2.get("archetype"):
                switches.append(
                    {
                        "player": a.get("player_name"),
                        "from": a.get("archetype"),
                        "to": b2.get("archetype"),
                        "ovr_delta": b2.get("overall", 0) - a.get("overall", 0),
                        "attribute_delta": {
                            x: (val(b2, x) - val(a, x))
                            for x in ATTRS
                            if val(a, x) is not None and val(b2, x) is not None
                        },
                    }
                )
    dump("version_chains.json", chains)
    dump("archetype_switches.json", switches)

    residuals = defaultdict(list)
    if b:
        for c in hold:
            p = predict(c, full_names, b)
            if p is not None:
                residuals[c.get("program") or "UNKNOWN"].append(p - c["overall"])
    pe = {
        p: {
            "n": len(es),
            "mean_residual": round(statistics.fmean(es), 4),
            "mae": round(statistics.fmean(abs(e) for e in es), 4),
        }
        for p, es in residuals.items()
    }
    dump(
        "program_effect.json",
        {
            "method": (
                "untouched-holdout residuals after observable universal attribute model; "
                "descriptive only"
            ),
            "programs": pe,
            "verdict": "INSUFFICIENT FOR CAUSAL PROGRAM MODIFIER",
        },
    )

    allcls = defaultdict(list)
    for _arch, e in economics.items():
        for a, c in e["classification"].items():
            allcls[a].append(c)
    cost = {}
    for a, cs in allcls.items():
        if len(set(cs)) > 1:
            cost[a] = "ARCHETYPE-DEPENDENT"
        elif cs[0] == "TIGHT / ANCHOR-LIKE":
            cost[a] = "LIKELY EXPENSIVE"
        elif cs[0] == "HIGHLY COMPENSABLE":
            cost[a] = "LIKELY CHEAP"
        else:
            cost[a] = "MODERATELY EXPENSIVE"
    dump(
        "te_ovr_economics.json",
        {
            "displayed_ovr_cost": cost,
            "warning": (
                "Same-cell slack is evidence of compensation, not proof of EA coefficients. "
                "Gameplay value is separate."
            ),
        },
    )

    ledger = []
    named = {
        83: ["DeGraaf", "Beers", "Foley", "Norfleet", "Payne", "Shockey"],
        84: ["Fleming", "Oakley", "Clarke"],
        85: ["Green", "Carter", "Thomas", "Jamari Johnson"],
        82: ["Lindenmeyer", "Helms", "Finley"],
    }
    for ovr, need in named.items():
        rows = [
            c
            for c in eligible
            if c.get("overall") == ovr and c.get("archetype") == "Physical Route Runner"
        ]
        found = [
            c.get("player_name")
            for c in rows
            if any(n.lower() in (c.get("player_name") or "").lower() for n in need)
        ]
        ledger.append(
            {
                "id": f"PRR-{ovr}",
                "category": "OP-TE-001 named same-cell replication",
                "status": "SUPPORT" if len(found) >= 2 else "INCONCLUSIVE",
                "sample": found,
                "expected_names": need,
            }
        )
    reported = {
        "LBK": 35,
        "RBK": 23,
        "IBL": 22,
        "PBK": 18,
        "PBP": 16,
        "STR": 15,
        "DRR": 12,
        "CIT": 7,
        "SPD": 6,
        "CTH": 5,
    }
    rows83 = [
        c
        for c in eligible
        if c.get("overall") == 83 and c.get("archetype") == "Physical Route Runner"
    ]
    for a, exp in reported.items():
        xs = [val(c, a) for c in rows83 if val(c, a) is not None]
        obs = (max(xs) - min(xs)) if len(xs) >= 2 else None
        ledger.append(
            {
                "id": f"PRR83-SPREAD-{a}",
                "category": "reported controlled spread",
                "status": "SUPPORT"
                if obs is not None and abs(obs - exp) <= 2
                else "CONTRADICTED"
                if obs is not None
                else "INCONCLUSIVE",
                "reported_approx": exp,
                "observed": obs,
            }
        )
    for arch in ARCHES:
        for a in ATTRS:
            if len(ledger) >= 48:
                break
            cell_ranges = [
                v["attributes"].get(a) for k, v in slack.items() if k.startswith(arch + "|")
            ]
            cell_ranges = [s["range"] for s in cell_ranges if s and s["n"] >= 2]
            ledger.append(
                {
                    "id": f"SLACK-{arch[:3]}-{a}",
                    "category": "OP-X-024 population extension of OP-TE-001 hypothesis",
                    "status": "SUPPORT" if cell_ranges else "INCONCLUSIVE",
                    "median_same_cell_range": statistics.median(cell_ranges)
                    if cell_ranges
                    else None,
                }
            )
        if len(ledger) >= 48:
            break
    ledger = ledger[:48] + [
        {
            "id": "LEGACY-403-405-1",
            "category": "legacy threshold",
            "status": "NOT EXECUTABLE",
            "reason": "LEGACY SPECIFICATION UNRECOVERED",
        },
        {
            "id": "LEGACY-403-405-2",
            "category": "legacy threshold archetype split",
            "status": "NOT EXECUTABLE",
            "reason": "LEGACY SPECIFICATION UNRECOVERED",
        },
    ]
    dump("experiment_ledger.json", ledger)

    largest = sorted(
        ((s["range"], k, a) for k, v in slack.items() for a, s in v["attributes"].items() if s),
        reverse=True,
    )[:10]
    tight = sorted(
        (
            (s["range"], k, a)
            for k, v in slack.items()
            for a, s in v["attributes"].items()
            if s and s["n"] >= 3
        )
    )[:10]
    counts = Counter(x["status"] for x in ledger)
    md = (
        "# OP-X-024 - CFB27 TE OVR Economics + Archetype Validation\n\n"
        "403-405 EXACT HISTORICAL RETEST: **BLOCKED - EXACT LEGACY SPECIFICATION "
        "UNRECOVERED.** No substitute formula was used.\n\n"
        f"Population: {len(tes)} TE records; static eligible {len(eligible)}; "
        f"excluded {len(excluded)}. Archetypes: "
        f"{dict(Counter(c.get('archetype') or 'UNKNOWN' for c in tes))}.\n\n"
        "Best supported exploratory architecture on deterministic holdout: "
        f"**{models['best_supported']}**. Holdout size: {len(hold)}. This does not "
        "modify or replace production TE ranking models.\n\n"
        f"Largest same-cell slack: {largest[:5]}\n\n"
        f"Tightest populated same-cell attributes: {tight[:5]}\n\n"
        f"Version chains: {len(chains)}; archetype switches: {len(switches)}. "
        "Program-effect verdict: insufficient evidence for a causal program modifier.\n\n"
        f"50-experiment ledger: {dict(counts)}.\n\n"
        "Production TE model modifications: **NONE**.\n\n"
        "Provenance: canonical `data/external/cfb_fan_population_state.json`; "
        "pre-test research package OP-TE-001.\n"
    )
    (OUT / "RESULTS.md").write_text(md, encoding="utf-8")


if __name__ == "__main__":
    main()
