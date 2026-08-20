#!/usr/bin/env python3
"""Build the durable OP-X-017 position/model inventory and 95% coverage matrix."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data/research/op_x_013"
OUTPUT = ROOT / "data/research/op_x_017"


def load(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def dump(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def model_row(
    *,
    position: str,
    model: str,
    version: str,
    archetype: str,
    production: bool,
    cfb25_n: int,
    cfb25_accuracy: float | None,
    cfb26_n: int,
    cfb26_accuracy: float | None,
    verdict: str,
    locked: bool,
    blocker: str,
    action: str,
) -> dict:
    return {
        "position": position,
        "model": model,
        "version": version,
        "archetype": archetype,
        "production_status": "production" if production else "diagnostic/non-production",
        "cfb25_n": cfb25_n,
        "cfb25_accuracy": cfb25_accuracy,
        "cfb26_n": cfb26_n,
        "cfb26_accuracy": cfb26_accuracy,
        "cross_season_verdict": verdict,
        "at_or_above_95_percent": bool(
            cfb25_accuracy is not None
            and cfb26_accuracy is not None
            and cfb25_accuracy >= 0.95
            and cfb26_accuracy >= 0.95
        ),
        "locked": locked,
        "remaining_blocker": blocker,
        "next_scientific_action": action,
    }


def main() -> None:
    seasons = {season: load_jsonl(SOURCE / f"cfb{season}_records.jsonl") for season in (25, 26)}
    counts = {
        str(season): dict(sorted(Counter(row.get("position") or "UNKNOWN" for row in rows).items()))
        for season, rows in seasons.items()
    }
    te = load(ROOT / "data/research/op_x_016/validation_results.json")
    center = load(ROOT / "data/research/op_x_016/center/validation_results.json")
    qb = load(OUTPUT / "qb_shared_001/validation_results.json")
    priors = load(OUTPUT / "qb_madden19_priors/validation_results.json")
    wr = load(ROOT / "data/research/op_x_018/validation_results.json")
    cb = load(ROOT / "data/research/op_x_018/cb/validation_results.json")
    rows = []
    te_models = {
        "Gritty Possession": ("TE-MODEL-001", "v1.1", True),
        "Physical Route Runner": ("TE-MODEL-003", "v1.1", True),
        "Pure Blocker": ("TE-MODEL-004", "v1.1", False),
        "Vertical Threat": ("TE-MODEL-006", "v1.3", True),
    }
    for archetype, (model, version, production) in te_models.items():
        cfb25 = te["seasons"]["25"]["models"][archetype]
        cfb26 = te["seasons"]["26"]["models"][archetype]
        verdict = te["cross_season_verdicts"][archetype]["verdict"]
        rows.append(
            model_row(
                position="TE",
                model=model,
                version=version,
                archetype=archetype,
                production=production,
                cfb25_n=cfb25["eligible_n"],
                cfb25_accuracy=cfb25["ranking_accuracy_excluding_ties"],
                cfb26_n=cfb26["eligible_n"],
                cfb26_accuracy=cfb26["ranking_accuracy_excluding_ties"],
                verdict=verdict,
                locked=verdict == "DURABLE PASS" and production,
                blocker=(
                    "No CFB25 compatible Physical Route Runner population."
                    if archetype == "Physical Route Runner"
                    else "Non-production external prior."
                    if not production
                    else "None."
                ),
                action=(
                    "Prospective validation only."
                    if verdict == "DURABLE PASS" and production
                    else "Retain frozen; await independent compatible population."
                ),
            )
        )
    center25 = center["seasons"]["25"]["overall"]
    center26 = center["seasons"]["26"]["overall"]
    rows.append(
        model_row(
            position="C",
            model="Historical Madden 19 Center",
            version="frozen historical hypothesis",
            archetype="all",
            production=False,
            cfb25_n=center25["eligible_n"],
            cfb25_accuracy=center25["ranking_accuracy_excluding_ties"],
            cfb26_n=center26["eligible_n"],
            cfb26_accuracy=center26["ranking_accuracy_excluding_ties"],
            verdict="DURABLE RANKING PASS; ABSOLUTE CALIBRATION REJECTED",
            locked=True,
            blocker="No validated CFB production calibration or archetype layer.",
            action="Lock ranking prior; recover/derive production calibration separately.",
        )
    )
    qb25 = qb["seasons"]["25"]["production_scope"]
    qb26 = qb["seasons"]["26"]["production_scope"]
    rows.append(
        model_row(
            position="QB",
            model="QB-SHARED-001",
            version="v1.0",
            archetype="shared; Pure Runner excluded",
            production=True,
            cfb25_n=qb25["eligible_n"],
            cfb25_accuracy=qb25["ranking_accuracy_excluding_ties"],
            cfb26_n=qb26["eligible_n"],
            cfb26_accuracy=qb26["ranking_accuracy_excluding_ties"],
            verdict=qb["cross_season_verdict"],
            locked=qb["cross_season_verdict"] == "DURABLE PASS",
            blocker="Pure Runner remains outside production scope.",
            action="Prospective validation; separately resolve Pure Runner.",
        )
    )
    prior_labels = {
        "Field General": (351, 305),
        "Scrambler": (100, 129),
        "Strong Arm": (19, 0),
        "West Coast": (0, 60),
    }
    for prior, (cfb25_n, cfb26_n) in prior_labels.items():
        values = priors["verdicts"][prior]["accuracies"]
        cfb25_accuracy = values[0] if cfb25_n else None
        cfb26_accuracy = values[-1] if cfb26_n else None
        rows.append(
            model_row(
                position="QB",
                model=f"Madden 19 {prior} prior",
                version="historical reference",
                archetype=prior,
                production=False,
                cfb25_n=cfb25_n,
                cfb25_accuracy=cfb25_accuracy,
                cfb26_n=cfb26_n,
                cfb26_accuracy=cfb26_accuracy,
                verdict=priors["verdicts"][prior]["verdict"],
                locked=False,
                blocker="External diagnostic prior; not a production CFB model.",
                action="Retain for architecture comparison only.",
            )
        )
    for position, model, validation in (
        ("WR", "WR-M19-ARCH-001", wr),
        ("CB", "CB-M19-ARCH-001", cb),
    ):
        cfb25 = validation["seasons"]["25"]
        cfb26 = validation["seasons"]["26"]
        rows.append(
            model_row(
                position=position,
                model=model,
                version="v1.0",
                archetype="generation-mapped archetype vectors",
                production=True,
                cfb25_n=cfb25["eligible_n"],
                cfb25_accuracy=cfb25["ranking_accuracy_excluding_ties"],
                cfb26_n=cfb26["eligible_n"],
                cfb26_accuracy=cfb26["ranking_accuracy_excluding_ties"],
                verdict=validation["cross_season_verdict"],
                locked=validation["locked"],
                blocker="None." if validation["locked"] else "Historical gate not cleared.",
                action="Prospective validation only." if validation["locked"] else "Investigate.",
            )
        )
    unresolved = [
        ("HB/RB", "HB", "783", "747"),
        ("FB", "FB", "58", "62"),
        ("LT/RT", "OT", "743", "719"),
        ("LG/RG", "G", "702", "713"),
        ("EDGE/DE", "DE→EDGE terminology", "831", "898"),
        ("DT", "DT", "609", "633"),
        ("MIKE/MLB", "MLB→MIKE terminology", "708", "614"),
        ("SAM/OLB", "OLB→SAM terminology", "733", "778"),
        ("FS", "historical S aggregate (shared with SS; do not double-count)", "955", "949"),
        ("SS", "historical S aggregate (shared with FS; do not double-count)", "955", "949"),
        ("K/P", "KP aggregate", "336", "323"),
    ]
    inventory = [
        {
            "position_family": position,
            "historical_source_label": label,
            "cfb25_population": int(n25),
            "cfb26_population": int(n26),
            "existing_model": None,
            "version": None,
            "frozen_status": "NO EXECUTABLE FROZEN COEFFICIENT VECTOR",
            "coefficient_provenance": None,
            "executable": False,
            "prior_validation": "Structural/component evidence only; no exact ranking formula.",
            "historical_population_compatibility": "Population present; formula absent.",
            "missing_evidence": (
                "Exact position/archetype coefficients frozen independently of CFB25/26."
            ),
        }
        for position, label, n25, n26 in unresolved
    ]
    inventory.extend(
        [
            {
                "position_family": "WR",
                "existing_model": "WR-M19-ARCH-001 v1.0",
                "frozen_status": "EXECUTED AND LOCKED BY OP-X-018",
                "coefficient_provenance": "SRC-M19-001 exact WR archetype vectors",
                "executable": True,
                "prior_validation": "CFB26 then unchanged CFB25 blind validation.",
                "historical_population_compatibility": (
                    "CFB25 1,305; CFB26 1,157 eligible of 1,158."
                ),
                "missing_evidence": "Prospective CFB27 validation only.",
            },
            {
                "position_family": "CB",
                "existing_model": "CB-M19-ARCH-001 v1.0",
                "frozen_status": "EXECUTED AND LOCKED BY OP-X-018",
                "coefficient_provenance": "SRC-M19-001 exact CB archetype vectors",
                "executable": True,
                "prior_validation": "CFB26 then unchanged CFB25 blind validation.",
                "historical_population_compatibility": "CFB25 1,079; CFB26 953 eligible of 955.",
                "missing_evidence": "Prospective CFB27 validation only.",
            },
            {
                "position_family": "QB",
                "existing_model": "QB-SHARED-001 v1.0 plus Madden 19 priors",
                "frozen_status": "EXECUTED",
                "coefficient_provenance": "canonical_v1.9.xlsx QB model/reference sheets",
                "executable": True,
                "prior_validation": "Player-disjoint CFB27 holdout.",
                "historical_population_compatibility": "CFB25 621; CFB26 494 production scope.",
                "missing_evidence": "Pure Runner production model.",
            },
            {
                "position_family": "TE",
                "existing_model": "TE-MODEL-001/003/004/006",
                "frozen_status": "EXECUTED BY OP-X-016",
                "coefficient_provenance": "SRC-M19-001 plus frozen CFB27 corrections/blend",
                "executable": True,
                "prior_validation": "CFB27 development/holdout and OP-X-016 historical.",
                "historical_population_compatibility": "CFB25 542; CFB26 657.",
                "missing_evidence": "CFB25 Physical Route Runner population only.",
            },
            {
                "position_family": "C",
                "existing_model": "Historical Madden 19 Center",
                "frozen_status": "EXECUTED BY OP-X-016; RESEARCH ONLY",
                "coefficient_provenance": "HIST-M19-CENTER-MODEL-001",
                "executable": True,
                "prior_validation": "Historical ranking passes; absolute calibration rejected.",
                "historical_population_compatibility": "CFB25 356; CFB26 372.",
                "missing_evidence": "Production calibration and archetype layer.",
            },
        ]
    )
    matrix = {
        "operation": "OP-X-017",
        "policy": ">=95% both meaningful generations = durable pass/lock",
        "historical_population_counts": counts,
        "models": rows,
        "summary": {
            "durable_production_locks": [
                f"{row['model']} {row['version']}"
                for row in rows
                if row["locked"] and row["production_status"] == "production"
            ],
            "currently_executable_frozen_models_exhausted": True,
            "highest_value_remaining_position": "S (historical FS/SS aggregate)",
            "reason": (
                "Largest remaining distinct two-season population (955 CFB25; 949 CFB26) "
                "without an executed frozen coefficient vector."
            ),
        },
    }
    dump(OUTPUT / "model_inventory.json", inventory)
    dump(OUTPUT / "coverage_matrix.json", matrix)
    lines = [
        "# Operation Pancake 95% Coverage Matrix",
        "",
        "| Position | Model | Archetype | Production | CFB25 N | CFB25 | CFB26 N | "
        "CFB26 | Verdict | Locked |",
        "|---|---|---|---|---:|---:|---:|---:|---|---|",
    ]
    for row in rows:
        accuracy25 = f"{row['cfb25_accuracy']:.4%}" if row["cfb25_accuracy"] is not None else "n/a"
        accuracy26 = f"{row['cfb26_accuracy']:.4%}" if row["cfb26_accuracy"] is not None else "n/a"
        lines.append(
            f"| {row['position']} | {row['model']} {row['version']} | {row['archetype']} | "
            f"{row['production_status']} | {row['cfb25_n']} | {accuracy25} | "
            f"{row['cfb26_n']} | {accuracy26} | {row['cross_season_verdict']} | "
            f"{'YES' if row['locked'] else 'NO'} |"
        )
    lines.extend(["", "## Non-executable families", ""])
    for item in inventory:
        if not item["executable"]:
            lines.append(
                f"- {item['position_family']}: CFB25 N={item['cfb25_population']}; "
                f"CFB26 N={item['cfb26_population']}; {item['missing_evidence']}"
            )
    lines.extend(
        [
            "",
            "## Next highest-value model",
            "",
            "S (historical FS/SS aggregate). It is the largest remaining distinct unmodeled "
            "two-season family. The recovered SRC-M19-001 workbook contains exact safety "
            "archetype vectors, but generation terminology must be frozen before validation.",
            "",
        ]
    )
    (OUTPUT / "COVERAGE.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
