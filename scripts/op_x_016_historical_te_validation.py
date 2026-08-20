#!/usr/bin/env python3
"""OP-X-016: execute frozen TE models against canonical CFB25/26 databases."""

from __future__ import annotations

import itertools
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data/research/op_x_013"
OUT = ROOT / "data/research/op_x_016"
SPEC = OUT / "frozen_te_scoring_spec.json"
EXPECTED = {25: 542, 26: 657}


def load_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def weighted(attrs: dict, weights: dict) -> tuple[float | None, int, list[str]]:
    used = {key: value for key, value in weights.items() if key in attrs}
    denominator = sum(used.values())
    value = (
        sum(attrs[key] * weight for key, weight in used.items()) / denominator
        if denominator
        else None
    )
    return value, denominator, sorted(set(weights) - set(used))


def score(row: dict, spec: dict) -> dict:
    aliases = spec["archetype_aliases"]
    archetype = aliases.get(row.get("archetype"), row.get("archetype", "UNKNOWN"))
    attrs = row.get("attributes") or {}
    weights = spec["madden19_weights"]
    component_denominators = None
    if archetype == "Gritty Possession":
        value, denominator, missing = weighted(attrs, weights["Possession"])
        model = "TE-MODEL-001 v1.1"
    elif archetype == "Pure Blocker":
        value, denominator, missing = weighted(attrs, weights["Blocking"])
        model = "TE-MODEL-004 v1.1"
    elif archetype == "Vertical Threat":
        visible_weights = dict(weights["Vertical Threat"])
        visible_weights.pop("ELU", None)
        visible_weights.update({"LBK": 2, "IBL": 3})
        value, denominator, missing = weighted(attrs, visible_weights)
        model = "TE-MODEL-006 v1.3"
    elif archetype == "Physical Route Runner":
        visible_weights = dict(weights["Vertical Threat"])
        visible_weights.pop("ELU", None)
        vertical, vertical_denominator, vertical_missing = weighted(attrs, visible_weights)
        possession, possession_denominator, possession_missing = weighted(
            attrs, weights["Possession"]
        )
        value = (
            0.71 * vertical + 0.29 * possession
            if vertical is not None and possession is not None
            else None
        )
        denominator = None
        component_denominators = {
            "vertical_threat": vertical_denominator,
            "possession": possession_denominator,
        }
        missing = sorted(set(vertical_missing + possession_missing))
        model = "TE-MODEL-003 v1.1"
    else:
        value = denominator = None
        missing = []
        model = None
    return {
        **row,
        "canonical_archetype": archetype,
        "frozen_model": model,
        "frozen_score": value,
        "weight_denominator": denominator,
        "component_denominators": component_denominators,
        "missing_weighted_attributes": missing,
        "scoring_eligible": value is not None,
    }


def average_ranks(values: list[float]) -> list[float]:
    ordered = sorted(range(len(values)), key=values.__getitem__)
    ranks = [0.0] * len(values)
    start = 0
    while start < len(ordered):
        end = start + 1
        while end < len(ordered) and values[ordered[end]] == values[ordered[start]]:
            end += 1
        rank = (start + 1 + end) / 2
        for index in ordered[start:end]:
            ranks[index] = rank
        start = end
    return ranks


def pearson(left: list[float], right: list[float]) -> float | None:
    if len(left) < 2:
        return None
    left_mean = sum(left) / len(left)
    right_mean = sum(right) / len(right)
    numerator = sum((a - left_mean) * (b - right_mean) for a, b in zip(left, right, strict=True))
    left_ss = sum((value - left_mean) ** 2 for value in left)
    right_ss = sum((value - right_mean) ** 2 for value in right)
    denominator = math.sqrt(left_ss * right_ss)
    return numerator / denominator if denominator else None


def gate(accuracy: float | None) -> str:
    if accuracy is None:
        return "INSUFFICIENT EVIDENCE"
    if accuracy >= 0.95:
        return "PASS"
    if accuracy >= 0.90:
        return "NEAR TARGET"
    return "FAIL"


def band_label(ovr: int) -> str:
    lower = (ovr // 5) * 5
    return f"{lower}-{lower + 4}"


def identity(row: dict) -> dict:
    return {key: row.get(key) for key in ("card_id", "name", "season", "ovr", "frozen_score")}


def pair_counts(rows: list[dict], capture_inversions: bool = True) -> dict:
    correct = inversions = ties = 0
    inversion_records = []
    transition_counts: dict[str, Counter] = defaultdict(Counter)
    for first, second in itertools.combinations(rows, 2):
        if first["ovr"] == second["ovr"]:
            continue
        high, low = (first, second) if first["ovr"] > second["ovr"] else (second, first)
        score_delta = high["frozen_score"] - low["frozen_score"]
        transition = f"{low['ovr']}->{high['ovr']}"
        if math.isclose(score_delta, 0, abs_tol=1e-12):
            ties += 1
            transition_counts[transition]["ties"] += 1
        elif score_delta > 0:
            correct += 1
            transition_counts[transition]["correct"] += 1
        else:
            inversions += 1
            transition_counts[transition]["inversions"] += 1
            if capture_inversions:
                inversion_records.append(
                    {
                        "score_gap": -score_delta,
                        "ovr_gap": high["ovr"] - low["ovr"],
                        "higher_ovr": identity(high),
                        "lower_ovr": identity(low),
                    }
                )
    inversion_records.sort(key=lambda item: (item["score_gap"], item["ovr_gap"]), reverse=True)
    worst_transitions = []
    for transition, counts in transition_counts.items():
        comparisons = counts["correct"] + counts["inversions"] + counts["ties"]
        if counts["inversions"]:
            denominator = counts["correct"] + counts["inversions"]
            worst_transitions.append(
                {
                    "ovr_transition": transition,
                    "comparisons": comparisons,
                    "inversions": counts["inversions"],
                    "ties": counts["ties"],
                    "accuracy_excluding_ties": counts["correct"] / denominator,
                }
            )
    worst_transitions.sort(
        key=lambda item: (item["inversions"], -item["accuracy_excluding_ties"]), reverse=True
    )
    return {
        "cross_ovr_pair_count": correct + inversions + ties,
        "correct_ordering_count": correct,
        "inversions": inversions,
        "ties": ties,
        "ranking_accuracy_excluding_ties": correct / (correct + inversions)
        if correct + inversions
        else None,
        "worst_inversions": inversion_records[:10],
        "worst_ovr_transition_clusters": worst_transitions[:10],
    }


def metrics(rows: list[dict]) -> dict:
    eligible = [row for row in rows if row["scoring_eligible"]]
    excluded = [row for row in rows if not row["scoring_eligible"]]
    residuals = [row["frozen_score"] - row["ovr"] for row in eligible]
    ordered_residuals = sorted(residuals)
    result = {
        "population_n": len(rows),
        "eligible_n": len(eligible),
        "excluded_n": len(excluded),
        "exclusion_reasons": dict(Counter("no_weighted_attributes" for _ in excluded)),
        "mean_residual": sum(residuals) / len(residuals) if residuals else None,
        "median_residual": ordered_residuals[len(ordered_residuals) // 2] if residuals else None,
        "min_residual": min(residuals) if residuals else None,
        "max_residual": max(residuals) if residuals else None,
        "raw_score_ovr_mae": sum(abs(value) for value in residuals) / len(residuals)
        if residuals
        else None,
        "rank_correlation_spearman": pearson(
            average_ranks([row["ovr"] for row in eligible]),
            average_ranks([row["frozen_score"] for row in eligible]),
        ),
        "missing_attribute_patterns": dict(
            Counter(
                ",".join(row["missing_weighted_attributes"]) or "none" for row in eligible
            ).most_common()
        ),
    }
    result.update(pair_counts(eligible))
    bands: dict[str, list[dict]] = defaultdict(list)
    for row in eligible:
        bands[band_label(row["ovr"])].append(row)
    result["ovr_band_performance"] = {}
    for band, band_rows in sorted(bands.items()):
        band_metrics = pair_counts(band_rows, capture_inversions=False)
        band_metrics["n"] = len(band_rows)
        band_metrics["mae"] = sum(abs(row["frozen_score"] - row["ovr"]) for row in band_rows) / len(
            band_rows
        )
        result["ovr_band_performance"][band] = band_metrics
    result["classification"] = gate(result["ranking_accuracy_excluding_ties"])
    return result


def durable_verdict(spec: dict, report: dict) -> dict:
    verdicts = {}
    for archetype, model_spec in spec["models"].items():
        seasons = {
            season: report["seasons"][season]["models"][archetype] for season in ("25", "26")
        }
        available = [result for result in seasons.values() if result["eligible_n"]]
        if len(available) < 2:
            verdict = "INSUFFICIENT CROSS-SEASON EVIDENCE"
        elif all(result["classification"] == "PASS" for result in available):
            verdict = "DURABLE PASS"
        elif any(result["classification"] == "FAIL" for result in available):
            verdict = "FAIL"
        else:
            verdict = "NEAR TARGET"
        verdicts[archetype] = {
            "model": f"{model_spec['id']} {model_spec['version']}",
            "production_model": model_spec["production"],
            "cfb25_accuracy": seasons["25"]["ranking_accuracy_excluding_ties"],
            "cfb26_accuracy": seasons["26"]["ranking_accuracy_excluding_ties"],
            "verdict": verdict,
        }
    return verdicts


def render_summary(report: dict, spec: dict) -> str:
    lines = [
        "# OP-X-016 Historical TE Validation",
        "",
        "Frozen coefficients only; no refit. Ranking accuracy is the primary decision "
        "measure. Raw-score/OVR residuals and MAE are diagnostic because these ranking "
        "models are not asserted to reproduce displayed OVR exactly. TE-MODEL-004 is a "
        "non-production prior.",
        "",
    ]
    for season in ("25", "26"):
        season_result = report["seasons"][season]
        lines.extend(
            [
                f"## CFB{season}",
                "",
                f"Population: {season_result['population_n']} TE; scored: "
                f"{season_result['scored_n']}; excluded: {season_result['excluded_n']}.",
                "",
                "| Model | N | Pairs | Correct | Inversions | Ties | Accuracy | "
                "Spearman | MAE | Gate |",
                "|---|---:|---:|---:|---:|---:|---:|---:|---:|---|",
            ]
        )
        for archetype, model_spec in spec["models"].items():
            result = season_result["models"][archetype]
            accuracy = result["ranking_accuracy_excluding_ties"]
            if accuracy is None:
                lines.append(
                    f"| {model_spec['id']} {model_spec['version']} ({archetype}) | "
                    "0 | 0 | 0 | 0 | 0 | n/a | n/a | n/a | INSUFFICIENT EVIDENCE |"
                )
            else:
                lines.append(
                    f"| {model_spec['id']} {model_spec['version']} ({archetype}) | "
                    f"{result['eligible_n']} | {result['cross_ovr_pair_count']} | "
                    f"{result['correct_ordering_count']} | {result['inversions']} | "
                    f"{result['ties']} | {accuracy:.4%} | "
                    f"{result['rank_correlation_spearman']:.6f} | "
                    f"{result['raw_score_ovr_mae']:.4f} | {result['classification']} |"
                )
        lines.append("")
    lines.extend(["## Cross-season decision", ""])
    for archetype, verdict in report["cross_season_verdicts"].items():
        lines.append(f"- {verdict['model']} ({archetype}): **{verdict['verdict']}**")
    lines.extend(
        [
            "",
            "## Residual and failure interpretation",
            "",
            "The machine-readable results include five-point OVR bands, missing-attribute "
            "patterns, the ten worst inversions, and the ten OVR-transition clusters with "
            "the most inversions for every season/model. Cross-season pooled comparisons "
            "are reported separately from within-season aggregate counts because "
            "season-to-season score calibration shifts can create inversions that do not "
            "affect either season's validation gate.",
            "",
        ]
    )
    return "\n".join(lines)


def dump(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    spec = json.loads(SPEC.read_text(encoding="utf-8"))
    report = {
        "operation": "OP-X-016",
        "control": "frozen models; no refit",
        "specification_provenance": spec["provenance"],
        "seasons": {},
    }
    all_scored = []
    for season in (25, 26):
        rows = load_jsonl(SRC / f"cfb{season}_records.jsonl")
        tight_ends = [row for row in rows if row.get("position") == "TE"]
        if len(tight_ends) != EXPECTED[season]:
            raise SystemExit(
                f"CFB{season} TE control mismatch: {len(tight_ends)} != {EXPECTED[season]}"
            )
        scored = [score(row, spec) for row in tight_ends]
        all_scored.extend(scored)
        season_result = {
            "population_n": len(tight_ends),
            "scored_n": sum(row["scoring_eligible"] for row in scored),
            "excluded_n": sum(not row["scoring_eligible"] for row in scored),
            "archetype_counts": dict(
                sorted(Counter(row["canonical_archetype"] for row in scored).items())
            ),
            "models": {},
        }
        for archetype, model_spec in spec["models"].items():
            result = metrics([row for row in scored if row["canonical_archetype"] == archetype])
            result["model"] = f"{model_spec['id']} {model_spec['version']}"
            result["production_model"] = model_spec["production"]
            season_result["models"][archetype] = result
        report["seasons"][str(season)] = season_result
        dump(OUT / f"cfb{season}_te_scored.json", scored)
    report["combined"] = {
        "population_n": len(all_scored),
        "scored_n": sum(row["scoring_eligible"] for row in all_scored),
        "models": {},
    }
    for archetype, model_spec in spec["models"].items():
        pooled = metrics([row for row in all_scored if row["canonical_archetype"] == archetype])
        season_results = [report["seasons"][season]["models"][archetype] for season in ("25", "26")]
        correct = sum(result["correct_ordering_count"] for result in season_results)
        inversions = sum(result["inversions"] for result in season_results)
        ties = sum(result["ties"] for result in season_results)
        pooled["within_season_aggregate"] = {
            "cross_ovr_pair_count": correct + inversions + ties,
            "correct_ordering_count": correct,
            "inversions": inversions,
            "ties": ties,
            "ranking_accuracy_excluding_ties": correct / (correct + inversions)
            if correct + inversions
            else None,
        }
        pooled["model"] = f"{model_spec['id']} {model_spec['version']}"
        report["combined"]["models"][archetype] = pooled
    report["cross_season_verdicts"] = durable_verdict(spec, report)
    dump(OUT / "validation_results.json", report)
    (OUT / "RESULTS.md").write_text(render_summary(report, spec), encoding="utf-8")
    print(json.dumps(report["cross_season_verdicts"], indent=2))


if __name__ == "__main__":
    main()
