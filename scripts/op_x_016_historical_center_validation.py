#!/usr/bin/env python3
"""Validate the already-frozen historical Center ranking hypothesis on CFB25/26."""

from __future__ import annotations

import importlib.util
import json
from collections import Counter
from pathlib import Path

from operation_pancake.research.center_exact_validation import (
    FrozenHistoricalCenterModel,
)

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data/research/op_x_013"
OUTPUT = ROOT / "data/research/op_x_016/center"
MODEL_SPEC = ROOT / "data/research/center_exact_validation/madden_center_frozen_model.json"
EXPECTED = {25: 356, 26: 372}


def _load_te_analysis():
    path = ROOT / "scripts/op_x_016_historical_te_validation.py"
    spec = importlib.util.spec_from_file_location("op_x_016_analysis", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ANALYSIS = _load_te_analysis()


def score(row: dict, model: FrozenHistoricalCenterModel) -> dict:
    attributes = row.get("attributes") or {}
    required = {field for field, _ in model.weights}
    missing = sorted(required - set(attributes))
    weighted_score = model.weighted_score(attributes) if not missing else None
    return {
        **row,
        "canonical_archetype": row.get("archetype", "UNKNOWN"),
        "frozen_model": "Historical Madden 19 Center",
        "frozen_score": weighted_score,
        "historical_calibrated_score": model.calibrated_score(attributes) if not missing else None,
        "historical_predicted_ovr": model.predict(attributes) if not missing else None,
        "missing_weighted_attributes": missing,
        "scoring_eligible": not missing,
    }


def dump(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    model = FrozenHistoricalCenterModel()
    frozen_spec = json.loads(MODEL_SPEC.read_text(encoding="utf-8"))
    report = {
        "operation": "OP-X-016 additional position execution",
        "position": "C",
        "model": frozen_spec,
        "control": "frozen historical weights and calibration; no refit",
        "scientific_scope": (
            "Ranking transfer test only. Existing evidence rejects the historical absolute "
            "calibration as a CFB production implementation."
        ),
        "seasons": {},
    }
    for season in (25, 26):
        rows = ANALYSIS.load_jsonl(SOURCE / f"cfb{season}_records.jsonl")
        centers = [row for row in rows if row.get("position") == "C"]
        if len(centers) != EXPECTED[season]:
            raise SystemExit(
                f"CFB{season} Center control mismatch: {len(centers)} != {EXPECTED[season]}"
            )
        scored = [score(row, model) for row in centers]
        by_archetype = {}
        for archetype in sorted({row["canonical_archetype"] for row in scored}):
            by_archetype[archetype] = ANALYSIS.metrics(
                [row for row in scored if row["canonical_archetype"] == archetype]
            )
        report["seasons"][str(season)] = {
            "population_n": len(centers),
            "eligible_n": sum(row["scoring_eligible"] for row in scored),
            "excluded_n": sum(not row["scoring_eligible"] for row in scored),
            "archetype_counts": dict(
                sorted(Counter(row["canonical_archetype"] for row in scored).items())
            ),
            "overall": ANALYSIS.metrics(scored),
            "by_archetype": by_archetype,
        }
        dump(OUTPUT / f"cfb{season}_center_scored.json", scored)
    season_gates = [
        report["seasons"][str(season)]["overall"]["classification"] for season in (25, 26)
    ]
    report["cross_season_verdict"] = (
        "DURABLE RANKING PASS; ABSOLUTE CALIBRATION REMAINS REJECTED"
        if all(value == "PASS" for value in season_gates)
        else "HISTORICAL RANKING TRANSFER BELOW DURABLE TARGET"
    )
    dump(OUTPUT / "validation_results.json", report)
    lines = [
        "# Historical Center Cross-Season Validation",
        "",
        report["scientific_scope"],
        "",
    ]
    for season in (25, 26):
        result = report["seasons"][str(season)]["overall"]
        lines.append(
            f"- CFB{season}: N={result['eligible_n']}; pairs={result['cross_ovr_pair_count']}; "
            f"accuracy={result['ranking_accuracy_excluding_ties']:.4%}; "
            f"Spearman={result['rank_correlation_spearman']:.6f}; "
            f"MAE={result['raw_score_ovr_mae']:.4f}; {result['classification']}."
        )
    lines.extend(["", f"Verdict: **{report['cross_season_verdict']}**", ""])
    (OUTPUT / "RESULTS.md").write_text("\n".join(lines), encoding="utf-8")
    print(
        json.dumps(
            {season: report["seasons"][season]["overall"] for season in ("25", "26")}, indent=2
        )
    )


if __name__ == "__main__":
    main()
