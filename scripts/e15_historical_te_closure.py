#!/usr/bin/env python3
"""Generate the durable E.15 scientific closure report from frozen historical results."""
from __future__ import annotations
import json
from pathlib import Path

OUT = Path("data/research/cfb27_e15/historical_validation")
ARCHETYPES = ("Gritty Possession", "Vertical Threat", "Physical Route Runner", "Pure Blocker")
MODELS = {
    "Gritty Possession": "TE-MODEL-001 v1.1",
    "Vertical Threat": "TE-MODEL-006 v1.3",
    "Physical Route Runner": "TE-MODEL-003 v1.1",
    "Pure Blocker": "TE-MODEL-004 v1.1",
}


def classify(metric: dict) -> str:
    n = metric.get("n", 0)
    pairs = metric.get("comparable_distinct_ovr_pairs", 0)
    acc = metric.get("ranking_accuracy_excluding_ties")
    if n < 6 or pairs < 10 or acc is None:
        return "INSUFFICIENT EVIDENCE"
    if acc >= 0.98:
        return "SUPPORTED"
    if acc >= 0.95:
        return "SUPPORTED WITH EXCEPTIONS"
    return "CHALLENGED"


def main() -> None:
    summary = json.loads((OUT / "summary.json").read_text())
    metrics = json.loads((OUT / "validation_metrics.json").read_text())
    seasons = summary["seasons"]
    complete = all(s.get("complete") for s in seasons)
    lines = [
        "# OP-X-012E.15 — Historical TE population validation closure",
        "",
        "Frozen first-pass validation. CFB25/26 observations were not used to refit any model.",
        "",
        "## Population integrity",
        "",
    ]
    for s in seasons:
        lines.append(
            f"- CFB{s['season']}: pages={s.get('listing_pages_enumerated')}; "
            f"terminal={s.get('terminal_page')}/{s.get('terminal_status')}; "
            f"TE N={s.get('persisted_population')}/{s.get('enumerated_urls')}; "
            f"missing={len(s.get('missing_urls', []))}; duplicates={s.get('duplicate_urls')}; "
            f"fetch_failures={s.get('fetch_failures')}; parse_failures={s.get('parse_failures')}; "
            f"archetypes={s.get('archetype_counts')}; complete={s.get('complete')}."
        )
    lines += ["", "## Frozen-model results", ""]
    classifications = {}
    for arch in ARCHETYPES:
        classifications[arch] = {}
        for season in ("25", "26"):
            m = metrics[season][arch]
            state = classify(m)
            classifications[arch][season] = state
            acc = m.get("ranking_accuracy_excluding_ties")
            lines.append(
                f"- CFB{season} {MODELS[arch]} / {arch}: N={m.get('n')}; "
                f"pairs={m.get('comparable_distinct_ovr_pairs')}; correct={m.get('correct_rankings')}; "
                f"inversions={m.get('inversions')}; ties={m.get('ties')}; "
                f"ranking_accuracy={acc:.4%} MAE={m.get('raw_score_ovr_mae'):.4f}; {state}."
                if acc is not None and m.get('raw_score_ovr_mae') is not None else
                f"- CFB{season} {MODELS[arch]} / {arch}: N={m.get('n')}; {state}."
            )
    lines += ["", "## Failure science", ""]
    for season in ("25", "26"):
        for arch in ARCHETYPES:
            m = metrics[season][arch]
            inv = m.get("inversion_records", [])
            severe = [x for x in inv if x.get("score_delta", 0) <= -1.0 or x.get("ovr_gap", 0) >= 2]
            worst = inv[:5]
            lines.append(f"- CFB{season} {arch}: {len(inv)} inversions; {len(severe)} meaningful (score deficit >=1 or OVR gap >=2).")
            for x in worst:
                lines.append(
                    f"  - {x['higher_name']} {x['higher_ovr']} ({x['higher_score']:.3f}) < "
                    f"{x['lower_name']} {x['lower_ovr']} ({x['lower_score']:.3f}); "
                    f"delta={x['score_delta']:.3f}; gap={x['ovr_gap']}."
                )
    states = [state for by_season in classifications.values() for state in by_season.values()]
    overall = "INCOMPLETE"
    if complete:
        overall = "SUPPORTED WITH EXCEPTIONS" if "CHALLENGED" not in states else "MIXED / MODEL-SPECIFIC"
    lines += ["", "## E.15 classification", "", f"**{overall}**", "",
              "Ranking accuracy is the primary validation measure. Raw weighted-score/OVR MAE is diagnostic only; the frozen weights are not asserted to be the exact displayed-OVR conversion formula."]
    (OUT / "e15_scientific_closure.md").write_text("\n".join(lines) + "\n")
    (OUT / "e15_classification.json").write_text(json.dumps({"population_complete": complete, "model_classifications": classifications, "overall": overall}, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
