#!/usr/bin/env python3
"""Execute frozen CB-M19-ARCH-001 after its pre-blind control commit."""

from __future__ import annotations

import json
from pathlib import Path

from op_x_018_historical_wr_validation import dump, load_jsonl, score, season_report

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data/research/op_x_013"
OUT = ROOT / "data/research/op_x_018/cb"
EXPECTED = {26: 955, 25: 1079}


def render(report: dict) -> str:
    lines = [
        "# OP-X-018 blind historical CB validation",
        "",
        "`CB-M19-ARCH-001 v1.0` was frozen and committed before scoring. CFB26 was "
        "persisted first; CFB25 used the unchanged specification.",
        "",
        "| Season | Population | Eligible | Pairs | Accuracy | Spearman | Gate |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    for season in ("26", "25"):
        row = report["seasons"][season]
        lines.append(
            f"| CFB{season} | {row['population_n']} | {row['eligible_n']} | "
            f"{row['cross_ovr_pair_count']} | {row['ranking_accuracy_excluding_ties']:.4%} | "
            f"{row['rank_correlation_spearman']:.6f} | {row['classification']} |"
        )
    lines.extend(["", f"Cross-season verdict: **{report['cross_season_verdict']}**.", ""])
    return "\n".join(lines)


def main() -> None:
    spec = json.loads((OUT / "frozen_cb_scoring_spec.json").read_text(encoding="utf-8"))
    report = {
        "operation": "OP-X-018-CB",
        "control_commit": "05f295943138ddf80e096ab0249b755f583f977d",
        "model": f"{spec['model']['id']} {spec['model']['version']}",
        "control": "frozen before CB outcomes; no refit; CFB26 before CFB25",
        "seasons": {},
    }
    for season in (26, 25):
        population = [
            row
            for row in load_jsonl(SOURCE / f"cfb{season}_records.jsonl")
            if row.get("position") == "CB"
        ]
        if len(population) != EXPECTED[season]:
            raise SystemExit(f"CFB{season} CB control mismatch: {len(population)}")
        scored = [score(row, spec) for row in population]
        result = season_report(scored)
        report["seasons"][str(season)] = result
        dump(OUT / f"cfb{season}_cb_scored.json", scored)
        dump(OUT / f"cfb{season}_blind_result.json", result)
    classifications = [report["seasons"][season]["classification"] for season in ("26", "25")]
    report["cross_season_verdict"] = (
        "DURABLE PASS"
        if classifications == ["PASS", "PASS"]
        else "FAIL"
        if "FAIL" in classifications
        else "NEAR TARGET"
    )
    report["locked"] = report["cross_season_verdict"] == "DURABLE PASS"
    dump(OUT / "validation_results.json", report)
    (OUT / "RESULTS.md").write_text(render(report), encoding="utf-8")
    print(
        json.dumps(
            {
                season: report["seasons"][season]["ranking_accuracy_excluding_ties"]
                for season in ("26", "25")
            },
            indent=2,
        )
    )
    print(report["cross_season_verdict"])


if __name__ == "__main__":
    main()
