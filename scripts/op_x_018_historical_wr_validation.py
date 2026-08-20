#!/usr/bin/env python3
"""Execute the pre-blind WR-M19-ARCH-001 specification without refitting."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from op_x_016_historical_te_validation import metrics

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data/research/op_x_013"
OUT = ROOT / "data/research/op_x_018"
SPEC_PATH = OUT / "frozen_wr_scoring_spec.json"
EXPECTED = {26: 1158, 25: 1305}


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def dump(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def score(row: dict, spec: dict) -> dict:
    mapping = spec["archetype_mappings"][f"CFB{row['season']}"].get(row.get("archetype"))
    if not mapping:
        reason = "unmapped_archetype"
        model_archetype = None
    else:
        model_archetype = mapping["model_archetype"]
        reason = "unsupported_archetype" if model_archetype is None else "ok"
    weights = spec["weights"].get(model_archetype, {})
    attrs = row.get("attributes") or {}
    used = {attribute: weight for attribute, weight in weights.items() if attribute in attrs}
    denominator = sum(used.values())
    latent = (
        sum(attrs[attribute] * weight for attribute, weight in used.items()) / denominator
        if denominator and reason == "ok"
        else None
    )
    return {
        **row,
        "source_archetype": row.get("archetype"),
        "model_archetype": model_archetype,
        "mapping_status": mapping["status"] if mapping else "UNSUPPORTED",
        "frozen_model": f"{spec['model']['id']} {spec['model']['version']}",
        "frozen_score": latent,
        "weight_denominator": denominator or None,
        "missing_weighted_attributes": sorted(set(weights) - set(used)),
        "scoring_eligible": latent is not None,
        "exclusion_reason": reason if latent is None else None,
    }


def subgroup_metrics(rows: list[dict], field: str) -> dict:
    values = {}
    for label in sorted({str(row.get(field) or "UNKNOWN") for row in rows}):
        subset = [row for row in rows if str(row.get(field) or "UNKNOWN") == label]
        values[label] = metrics(subset)
    return values


def season_report(rows: list[dict]) -> dict:
    result = metrics(rows)
    result["candidate_n"] = len(rows)
    result["source_archetype_counts"] = dict(
        sorted(Counter(row["source_archetype"] for row in rows).items())
    )
    result["model_archetype_counts"] = dict(
        sorted(Counter(row["model_archetype"] or "UNSUPPORTED" for row in rows).items())
    )
    result["exclusion_reasons"] = dict(
        sorted(
            Counter(row["exclusion_reason"] for row in rows if not row["scoring_eligible"]).items()
        )
    )
    result["archetype_behavior"] = subgroup_metrics(rows, "source_archetype")
    result["program_card_type_behavior"] = {
        "status": "UNAVAILABLE_IN_HISTORICAL_RECORD_SCHEMA",
        "available_fields": sorted(set().union(*(row.keys() for row in rows))),
        "note": "Records contain no program or card-type field; no proxy was invented.",
    }
    return result


def render(report: dict) -> str:
    lines = [
        "# OP-X-018 blind historical WR validation",
        "",
        "`WR-M19-ARCH-001 v1.0` was frozen and committed before scoring. CFB26 was "
        "executed and persisted first; CFB25 then used the unchanged specification. "
        "Ranking accuracy excludes score ties, matching prior Operation Pancake gates.",
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
    lines.extend(
        [
            "",
            f"Cross-season verdict: **{report['cross_season_verdict']}**.",
            "",
            "Program/card-type behavior is explicitly unavailable because those fields are "
            "not present in the historical record schema. Machine-readable results preserve "
            "OVR-band behavior, archetype behavior, residuals, worst inversions, and boundary "
            "transition clusters.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    spec = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    report = {
        "operation": "OP-X-018",
        "control_commit": "f13e8eaae473d2939372090f7e773e2b8ddc4738",
        "model": f"{spec['model']['id']} {spec['model']['version']}",
        "control": "frozen before outcomes; no refit; CFB26 executed before CFB25",
        "seasons": {},
    }
    for season in (26, 25):
        population = [
            row
            for row in load_jsonl(SOURCE / f"cfb{season}_records.jsonl")
            if row.get("position") == "WR"
        ]
        if len(population) != EXPECTED[season]:
            raise SystemExit(
                f"CFB{season} WR control mismatch: {len(population)} != {EXPECTED[season]}"
            )
        scored = [score(row, spec) for row in population]
        result = season_report(scored)
        report["seasons"][str(season)] = result
        dump(OUT / f"cfb{season}_wr_scored.json", scored)
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
            {s: report["seasons"][s]["ranking_accuracy_excluding_ties"] for s in ("26", "25")},
            indent=2,
        )
    )
    print(report["cross_season_verdict"])


if __name__ == "__main__":
    main()
