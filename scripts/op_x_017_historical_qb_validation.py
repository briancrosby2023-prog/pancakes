#!/usr/bin/env python3
"""OP-X-017: blind historical validation of frozen QB-SHARED-001 v1.0."""

from __future__ import annotations

import importlib.util
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data/research/op_x_013"
OUTPUT = ROOT / "data/research/op_x_017/qb_shared_001"
EXPECTED = {25: 621, 26: 547}
PRODUCTION_ARCHETYPES = {"Pocket Passer", "Backfield Creator", "Dual Threat"}
WEIGHTS = {
    "SPD": 3,
    "ACC": 1,
    "AGI": 8,
    "AWR": 10,
    "THP": 18,
    "SAC": 12,
    "MAC": 12,
    "DAC": 18,
    "RUN": 1,
    "TUP": 9,
    "PAC": 4,
    "BSK": 4,
}


def _load_analysis():
    path = ROOT / "scripts/op_x_016_historical_te_validation.py"
    spec = importlib.util.spec_from_file_location("op_x_016_analysis", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ANALYSIS = _load_analysis()


def score(row: dict) -> dict:
    attributes = row.get("attributes") or {}
    missing = sorted(set(WEIGHTS) - set(attributes))
    frozen_score = (
        sum(attributes[field] * weight for field, weight in WEIGHTS.items()) / 100
        if not missing
        else None
    )
    return {
        **row,
        "canonical_archetype": row.get("archetype", "UNKNOWN"),
        "frozen_model": "QB-SHARED-001 v1.0",
        "frozen_score": frozen_score,
        "missing_weighted_attributes": missing,
        "scoring_eligible": frozen_score is not None,
    }


def dump(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    report = {
        "operation": "OP-X-017",
        "model": {
            "id": "QB-SHARED-001",
            "version": "v1.0",
            "status": "OPERATIONALLY SOLVED / FROZEN",
            "production_archetypes": sorted(PRODUCTION_ARCHETYPES),
            "weights": WEIGHTS,
            "denominator": 100,
            "coefficient_provenance": (
                "data/canonical/canonical_v1.9.xlsx :: QB_Model_Weights; development-only "
                "selection with player-disjoint holdout"
            ),
            "prior_validation": {
                "global_holdout": "929/936 (99.2521%)",
                "full": "2046/2057 (99.4652%)",
            },
        },
        "control": "frozen coefficients; no historical refit or archetype relabeling",
        "seasons": {},
    }
    for season in (25, 26):
        rows = ANALYSIS.load_jsonl(SOURCE / f"cfb{season}_records.jsonl")
        quarterbacks = [row for row in rows if row.get("position") == "QB"]
        if len(quarterbacks) != EXPECTED[season]:
            raise SystemExit(
                f"CFB{season} QB control mismatch: {len(quarterbacks)} != {EXPECTED[season]}"
            )
        scored = [score(row) for row in quarterbacks]
        by_archetype = {}
        for archetype in sorted({row["canonical_archetype"] for row in scored}):
            by_archetype[archetype] = ANALYSIS.metrics(
                [row for row in scored if row["canonical_archetype"] == archetype]
            )
        production_scope = (
            scored
            if season == 25
            else [row for row in scored if row["canonical_archetype"] in PRODUCTION_ARCHETYPES]
        )
        report["seasons"][str(season)] = {
            "population_n": len(quarterbacks),
            "archetype_counts": dict(
                sorted(Counter(row["canonical_archetype"] for row in scored).items())
            ),
            "production_scope_n": len(production_scope),
            "production_scope_note": (
                "Older source taxonomy retained unchanged; positional-weight transfer diagnostic."
                if season == 25
                else (
                    "Declared production archetypes only; Pure Runner and malformed labels "
                    "excluded."
                )
            ),
            "overall_all_qb": ANALYSIS.metrics(scored),
            "production_scope": ANALYSIS.metrics(production_scope),
            "by_archetype": by_archetype,
        }
        dump(OUTPUT / f"cfb{season}_qb_scored.json", scored)
    accuracies = [
        report["seasons"][str(season)]["production_scope"]["ranking_accuracy_excluding_ties"]
        for season in (25, 26)
    ]
    report["cross_season_verdict"] = (
        "DURABLE PASS"
        if all(accuracy is not None and accuracy >= 0.95 for accuracy in accuracies)
        else "BELOW DURABLE TARGET"
    )
    report["taxonomy_control"] = (
        "CFB25 archetype names were not mapped to CFB26 names. Its result tests the shared "
        "positional vector across the older QB taxonomy, not archetype identity continuity."
    )
    dump(OUTPUT / "validation_results.json", report)
    lines = [
        "# OP-X-017 QB-SHARED-001 Historical Validation",
        "",
        report["control"],
        "",
        report["taxonomy_control"],
        "",
    ]
    for season in (25, 26):
        result = report["seasons"][str(season)]["production_scope"]
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
            {season: report["seasons"][season]["production_scope"] for season in ("25", "26")},
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
