#!/usr/bin/env python3
"""Execute exact Madden 19 QB priors as non-production historical diagnostics."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data/research/op_x_013"
OUTPUT = ROOT / "data/research/op_x_017/qb_madden19_priors"
EXPECTED = {25: 621, 26: 547}
WEIGHTS = {
    "Field General": {
        "AWR": 16,
        "THP": 25,
        "SAC": 18,
        "MAC": 18,
        "DAC": 12,
        "RUN": 3,
        "TUP": 5,
        "PAC": 3,
    },
    "Scrambler": {
        "SPD": 6,
        "ACC": 3,
        "AGI": 2,
        "AWR": 7,
        "THP": 23,
        "SAC": 15,
        "MAC": 14,
        "RUN": 10,
        "TUP": 7,
        "BSK": 10,
    },
    "Strong Arm": {
        "AWR": 12,
        "THP": 33,
        "MAC": 22,
        "DAC": 18,
        "TUP": 10,
        "PAC": 2,
        "BSK": 3,
    },
    "West Coast": {
        "SPD": 2,
        "ACC": 1,
        "AGI": 2,
        "AWR": 14,
        "THP": 15,
        "SAC": 24,
        "MAC": 18,
        "DAC": 3,
        "RUN": 5,
        "TUP": 5,
        "PAC": 11,
    },
}
SEASON_ARCHETYPES = {
    25: {
        "Field General": "Field General",
        "Scrambler": "Scrambler",
        "Strong Arm": "Strong Arm",
    },
    26: {
        "Field General": "Pocket Passer",
        "Scrambler": "Dual Threat",
        "West Coast": "Backfield Creator",
    },
}


def _load_analysis():
    path = ROOT / "scripts/op_x_016_historical_te_validation.py"
    spec = importlib.util.spec_from_file_location("op_x_016_analysis", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ANALYSIS = _load_analysis()


def score(row: dict, prior: str) -> dict:
    attributes = row.get("attributes") or {}
    weights = WEIGHTS[prior]
    missing = sorted(set(weights) - set(attributes))
    denominator = sum(weights.values())
    frozen_score = (
        sum(attributes[field] * weight for field, weight in weights.items()) / denominator
        if not missing
        else None
    )
    return {
        **row,
        "canonical_archetype": row.get("archetype", "UNKNOWN"),
        "frozen_model": f"Madden 19 {prior} QB prior",
        "frozen_score": frozen_score,
        "weight_denominator": denominator,
        "missing_weighted_attributes": missing,
        "scoring_eligible": frozen_score is not None,
    }


def dump(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    report = {
        "operation": "OP-X-017",
        "status": "NON-PRODUCTION HISTORICAL PRIORS",
        "coefficient_provenance": (
            "data/canonical/canonical_v1.9.xlsx :: Madden19_QB_Weights :: SRC-M19-QB-001"
        ),
        "mapping_provenance": (
            "CFB25 exact source labels; CFB26 mappings persisted by cfb27_phase2.py. "
            "Backfield Creator equals West Coast was previously rejected and remains diagnostic."
        ),
        "weights": WEIGHTS,
        "seasons": {},
    }
    for season in (25, 26):
        rows = ANALYSIS.load_jsonl(SOURCE / f"cfb{season}_records.jsonl")
        quarterbacks = [row for row in rows if row.get("position") == "QB"]
        if len(quarterbacks) != EXPECTED[season]:
            raise SystemExit(
                f"CFB{season} QB control mismatch: {len(quarterbacks)} != {EXPECTED[season]}"
            )
        season_result = {}
        for prior, source_archetype in SEASON_ARCHETYPES[season].items():
            scored = [
                score(row, prior)
                for row in quarterbacks
                if row.get("archetype") == source_archetype
            ]
            result = ANALYSIS.metrics(scored)
            result["source_archetype"] = source_archetype
            result["production_model"] = False
            season_result[prior] = result
            dump(OUTPUT / f"cfb{season}_{prior.lower().replace(' ', '_')}_scored.json", scored)
        report["seasons"][str(season)] = season_result
    verdicts = {}
    for prior in WEIGHTS:
        measured = [
            report["seasons"][str(season)].get(prior)
            for season in (25, 26)
            if prior in report["seasons"][str(season)]
        ]
        accuracies = [
            result["ranking_accuracy_excluding_ties"] for result in measured if result["eligible_n"]
        ]
        if len(accuracies) == 2 and all(value >= 0.95 for value in accuracies):
            verdict = "DURABLE DIAGNOSTIC PASS"
        elif len(accuracies) == 1 and accuracies[0] >= 0.95:
            verdict = "SINGLE-SEASON DIAGNOSTIC PASS"
        elif any(value < 0.90 for value in accuracies):
            verdict = "DIAGNOSTIC FAIL"
        elif accuracies:
            verdict = "DIAGNOSTIC NEAR TARGET"
        else:
            verdict = "INSUFFICIENT EVIDENCE"
        verdicts[prior] = {"accuracies": accuracies, "verdict": verdict}
    report["verdicts"] = verdicts
    dump(OUTPUT / "validation_results.json", report)
    lines = [
        "# Madden 19 QB Prior Diagnostics",
        "",
        "External historical priors only; no coefficients were refit or promoted.",
        "",
    ]
    for prior, verdict in verdicts.items():
        rendered = ", ".join(f"{value:.4%}" for value in verdict["accuracies"]) or "n/a"
        lines.append(f"- {prior}: {rendered}; **{verdict['verdict']}**")
    lines.append("")
    (OUTPUT / "RESULTS.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(verdicts, indent=2))


if __name__ == "__main__":
    main()
