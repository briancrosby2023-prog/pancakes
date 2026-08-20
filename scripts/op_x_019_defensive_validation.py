#!/usr/bin/env python3
"""Blind historical validator for frozen OP-X-019 defensive archetype models."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from op_x_018_historical_wr_validation import dump, load_jsonl, score, season_report

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data/research/op_x_013"


def validate_family(
    *,
    family: str,
    spec_path: Path,
    positions: dict[int, str],
    expected: dict[int, int],
    control_commit: str,
) -> dict:
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    output = spec_path.parent
    report = {
        "operation": spec["operation"],
        "family": family,
        "control_commit": control_commit,
        "model": f"{spec['model']['id']} {spec['model']['version']}",
        "control": "frozen before outcomes; no refit; CFB26 persisted before CFB25",
        "seasons": {},
    }
    for season in (26, 25):
        population = [
            row
            for row in load_jsonl(SOURCE / f"cfb{season}_records.jsonl")
            if row.get("position") == positions[season]
        ]
        if len(population) != expected[season]:
            raise SystemExit(
                f"CFB{season} {family} control mismatch: {len(population)} != {expected[season]}"
            )
        scored = [score(row, spec) for row in population]
        result = season_report(scored)
        result["source_position"] = positions[season]
        if family == "SAFETY":
            result["fs_vs_ss_behavior"] = {
                "status": "UNAVAILABLE_IN_HISTORICAL_RECORD_SCHEMA",
                "note": "All records use aggregate position S; no FS/SS subtype was inferred.",
            }
        report["seasons"][str(season)] = result
        dump(output / f"cfb{season}_blind_result.json", result)
        dump(output / f"cfb{season}_{family.lower()}_scored.json", scored)
    classifications = [report["seasons"][season]["classification"] for season in ("26", "25")]
    report["cross_season_verdict"] = (
        "DURABLE PASS"
        if classifications == ["PASS", "PASS"]
        else "FAIL"
        if "FAIL" in classifications
        else "NEAR TARGET"
    )
    report["locked"] = report["cross_season_verdict"] == "DURABLE PASS"
    dump(output / "validation_results.json", report)
    (output / "RESULTS.md").write_text(render(report), encoding="utf-8")
    return report


def render(report: dict) -> str:
    lines = [
        f"# {report['operation']} blind historical validation",
        "",
        f"`{report['model']}` was frozen and committed before scoring. CFB26 was "
        "persisted before the unchanged CFB25 replication.",
        "",
        "| Season | Population | Eligible | Pairs | Correct | Inversions | Ties | "
        "Accuracy | Spearman | Gate |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for season in ("26", "25"):
        row = report["seasons"][season]
        lines.append(
            f"| CFB{season} | {row['population_n']} | {row['eligible_n']} | "
            f"{row['cross_ovr_pair_count']} | {row['correct_ordering_count']} | "
            f"{row['inversions']} | {row['ties']} | "
            f"{row['ranking_accuracy_excluding_ties']:.4%} | "
            f"{row['rank_correlation_spearman']:.6f} | {row['classification']} |"
        )
    lines.extend(["", f"Cross-season verdict: **{report['cross_season_verdict']}**.", ""])
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("family", choices=("safety", "edge", "mike", "dt", "sam"))
    args = parser.parse_args()
    if args.family == "safety":
        report = validate_family(
            family="SAFETY",
            spec_path=ROOT / "data/research/op_x_019/safety/frozen_safety_scoring_spec.json",
            positions={25: "S", 26: "S"},
            expected={25: 955, 26: 949},
            control_commit="b6419ddc6caca909a4ad10c7b668b0ba3f6af6a4",
        )
    elif args.family == "edge":
        report = validate_family(
            family="EDGE",
            spec_path=ROOT / "data/research/op_x_019/edge/frozen_edge_scoring_spec.json",
            positions={25: "DE", 26: "EDGE"},
            expected={25: 831, 26: 898},
            control_commit="0142f301f0a526f83ef76c1b2d608b1f6350d536",
        )
    elif args.family == "mike":
        report = validate_family(
            family="MIKE",
            spec_path=ROOT / "data/research/op_x_019/mike/frozen_mike_scoring_spec.json",
            positions={25: "MLB", 26: "MIKE"},
            expected={25: 708, 26: 614},
            control_commit="9279ebb3ba6c95ed3e7e33ac398b77bebc54693b",
        )
    elif args.family == "dt":
        report = validate_family(
            family="DT",
            spec_path=ROOT / "data/research/op_x_019/dt/frozen_dt_scoring_spec.json",
            positions={25: "DT", 26: "DT"},
            expected={25: 609, 26: 633},
            control_commit="5a526b8d8ef52dfe1c0cb34ee046e135e330ca65",
        )
    elif args.family == "sam":
        report = validate_family(
            family="SAM",
            spec_path=ROOT / "data/research/op_x_019/sam/frozen_sam_scoring_spec.json",
            positions={25: "OLB", 26: "SAM"},
            expected={25: 733, 26: 778},
            control_commit="PENDING_PRE_BLIND_COMMIT",
        )
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
