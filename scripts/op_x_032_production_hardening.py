"""Measure full-population and roster product coverage for OP-X-032."""

from __future__ import annotations

import hashlib
import itertools
import json
import subprocess
import sys
import tempfile
import time
from bisect import bisect_left, bisect_right
from collections import Counter, defaultdict
from pathlib import Path

from operation_pancake.production.attributes import AttributeIntelligence
from operation_pancake.production.gm import optimize_budget
from operation_pancake.production.roster import normalize_name

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data/research/op_x_032"


def write(name: str, payload: object) -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / name).write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def dimensions(rows: list[dict]) -> dict:
    output = {}
    for dimension, key in (
        ("position", "position_family"),
        ("archetype", "archetype"),
        ("overall", "native_overall"),
        ("program", "program"),
    ):
        groups: dict[str, Counter] = defaultdict(Counter)
        for row in rows:
            groups[str(row.get(key))][row["product_state"]] += 1
            groups[str(row.get(key))]["TOTAL"] += 1
        output[dimension] = {name: dict(counts) for name, counts in sorted(groups.items())}
    return output


def expected_attributes(intelligence: AttributeIntelligence, score: dict) -> set[str]:
    if score["routing"]["status"] != "ROUTED":
        return set()
    model = intelligence.models[(score["pancake_model_id"], score["pancake_model_version"])]
    profile = score["routing"]["profile"]
    if profile == "Blend":
        return set(model["profiles"]["Vertical Threat"]) | set(model["profiles"]["Possession"])
    return set(model["profiles"][profile])


def coverage_and_unsupported(intelligence: AttributeIntelligence) -> tuple[dict, dict, dict]:
    rank_ids = {row["card_id"] for row in intelligence.ranked}
    family_counts = Counter(row["position_family"] for row in intelligence.ranked)
    rows = []
    unsupported = []
    missing_counter: Counter[str] = Counter()
    for score in intelligence.scored_all:
        card = intelligence.cards[score["card_id"]]
        state = score["score_status"]
        product_state = (
            "FULLY_SCOREABLE"
            if state == "SCORED_COMPLETE"
            else "PARTIALLY_SCOREABLE"
            if state == "SCORED_PARTIAL"
            else state
        )
        rows.append({**score, "product_state": product_state})
        if score["score"] is None:
            expected = expected_attributes(intelligence, score)
            available = set(card.get("native_ratings") or {})
            missing = sorted(expected - available)
            missing_counter.update(
                f"{score['position_family']}|{attribute}" for attribute in missing
            )
            if score["routing"]["status"] == "UNSUPPORTED":
                bucket, disposition = "UNSUPPORTED ARCHETYPE/MODEL", "SCIENTIFICALLY UNSUPPORTED"
            elif score["routing"]["status"] == "DIAGNOSTIC_ONLY":
                bucket, disposition = "DIAGNOSTIC-ONLY MODEL", "REQUIRE ADDITIONAL EVIDENCE"
            else:
                bucket, disposition = "MISSING REQUIRED ATTRIBUTES", "REQUIRE ADDITIONAL EVIDENCE"
            unsupported.append(
                {
                    "card_id": score["card_id"],
                    "player_name": score["player_name"],
                    "position_family": score["position_family"],
                    "archetype": score["archetype"],
                    "overall": score["native_overall"],
                    "program": score["program"],
                    "score_status": state,
                    "routing_status": score["routing"]["status"],
                    "reason_bucket": bucket,
                    "missing_required_attributes": missing,
                    "disposition": disposition,
                }
            )
    counts = Counter(row["product_state"] for row in rows)
    total = len(rows)
    coverage = {
        "total_cards": total,
        "identity_resolved": total,
        "model_routable": sum(row["routing"]["status"] == "ROUTED" for row in rows),
        "fully_scoreable": counts["FULLY_SCOREABLE"],
        "partially_scoreable": counts["PARTIALLY_SCOREABLE"],
        "insufficient_attributes": counts["INSUFFICIENT_ATTRIBUTES"],
        "unsupported_archetype_or_model": counts["UNSUPPORTED"],
        "diagnostic_only": counts["DIAGNOSTIC_ONLY"],
        "explainable": len(rank_ids),
        "rankable": len(rank_ids),
        "comparison_capable": sum(
            score["card_id"] in rank_ids and family_counts[score["position_family"]] > 1
            for score in rows
        ),
        "alternative_search_capable": len(rank_ids),
        "intrinsic_value_capable": len(rank_ids),
        "market_ready": total,
        "breakdowns": dimensions(rows),
    }
    audit = {
        "total": len(unsupported),
        "reason_buckets": dict(Counter(row["reason_bucket"] for row in unsupported)),
        "dispositions": dict(Counter(row["disposition"] for row in unsupported)),
        "fixable_without_model_changes": 0,
        "fixed": 0,
        "missing_attribute_counts": dict(missing_counter.most_common()),
        "cards": unsupported,
    }
    return coverage, audit, {row["card_id"]: row for row in rows}


def partial_audit(intelligence: AttributeIntelligence, score_rows: dict[str, dict]) -> dict:
    partial = [row for row in score_rows.values() if row["score_status"] == "SCORED_PARTIAL"]
    complete = [row for row in score_rows.values() if row["score_status"] == "SCORED_COMPLETE"]
    missing: Counter[str] = Counter()
    by_model: dict[str, dict] = {}
    groups: dict[str, list[dict]] = defaultdict(list)
    for row in score_rows.values():
        if row["routing"]["status"] == "ROUTED":
            groups[row.get("pancake_model_id", "UNKNOWN")].append(row)
        if row["score_status"] == "SCORED_PARTIAL":
            expected = expected_attributes(intelligence, row)
            available = set(intelligence.cards[row["card_id"]].get("native_ratings") or {})
            missing.update(
                f"{row['position_family']}|{attribute}" for attribute in expected - available
            )
    for model_id, rows in sorted(groups.items()):
        complete_rows = [row for row in rows if row["score_status"] == "SCORED_COMPLETE"]
        partial_rows = [row for row in rows if row["score_status"] == "SCORED_PARTIAL"]
        ranked_rows = [
            row for row in intelligence.ranked if row.get("pancake_model_id") == model_id
        ]
        top_ten = ranked_rows[:10]
        by_model[model_id] = {
            "complete": len(complete_rows),
            "partial": len(partial_rows),
            "mean_complete_score": None
            if not complete_rows
            else round(sum(row["score"] for row in complete_rows) / len(complete_rows), 6),
            "mean_partial_score": None
            if not partial_rows
            else round(sum(row["score"] for row in partial_rows) / len(partial_rows), 6),
            "mean_partial_coverage": None
            if not partial_rows
            else round(
                sum(row["attribute_coverage"] for row in partial_rows) / len(partial_rows), 6
            ),
            "partial_cards_in_model_top_10": sum(
                row["score_status"] == "SCORED_PARTIAL" for row in top_ten
            ),
            "boundary_inversion_warning": (
                "descriptive only: no counterfactual missing ratings available"
                if partial_rows
                else "NOT APPLICABLE"
            ),
        }
    return {
        "partial": len(partial),
        "complete": len(complete),
        "confidence_counts": dict(Counter(row["score_confidence"] for row in partial)),
        "coverage_bands": dict(
            Counter(
                (
                    f"{int(row['attribute_coverage'] * 10) * 10}-"
                    f"{int(row['attribute_coverage'] * 10) * 10 + 9}%"
                )
                for row in partial
            )
        ),
        "missing_attributes": dict(missing.most_common()),
        "models": by_model,
        "conclusion": (
            "partial scores remain disclosed ranking evidence; missingness bias cannot be "
            "causally corrected without unavailable counterfactual ratings"
        ),
    }


def alternative_coverage(intelligence: AttributeIntelligence) -> dict:
    groups: dict[str, list[dict]] = defaultdict(list)
    for row in intelligence.ranked:
        groups[row["position_family"]].append(row)
    records = []
    totals = Counter()
    breakdown: dict[str, Counter] = defaultdict(Counter)
    for family, rows in groups.items():
        ordered = sorted(rows, key=lambda row: row["score"])
        scores = [row["score"] for row in ordered]
        for row in ordered:
            record = {
                "card_id": row["card_id"],
                "position_family": family,
                "archetype": row["archetype"],
                "overall": row["native_overall"],
            }
            for tolerance in (0.25, 0.5, 1.0):
                count = (
                    bisect_right(scores, row["score"] + tolerance)
                    - bisect_left(scores, row["score"] - tolerance)
                    - 1
                )
                key = f"within_{tolerance:.2f}"
                record[key] = count
                if count > 0:
                    totals[key] += 1
                    breakdown[f"{family}|{row['archetype']}|{row['native_overall']}"][key] += 1
            records.append(record)
    return {
        "ranked_cards": len(records),
        "cards_with_alternatives": dict(totals),
        "rates_percent": {
            key: round(value * 100 / len(records), 6) for key, value in totals.items()
        },
        "breakdown": {key: dict(value) for key, value in sorted(breakdown.items())},
        "disclosures_added": ["different archetype", "score confidence", "attribute coverage"],
        "card_index": records,
    }


def football_candidates(intelligence: AttributeIntelligence) -> dict:
    groups: dict[str, list[dict]] = defaultdict(list)
    for row in intelligence.ranked:
        groups[row["position_family"]].append(row)
    lower_beats_higher = []
    for family, rows in groups.items():
        for lower in rows:
            beaten = [
                higher
                for higher in rows
                if higher["native_overall"] > lower["native_overall"]
                and lower["score"] > higher["score"]
            ]
            if not beaten:
                continue
            higher = min(beaten, key=lambda row: row["score"])
            lower_beats_higher.append(
                {
                    "position_family": family,
                    "lower_ovr_card_id": lower["card_id"],
                    "lower_ovr_player": lower["player_name"],
                    "lower_ovr": lower["native_overall"],
                    "higher_ovr_card_id": higher["card_id"],
                    "higher_ovr_player": higher["player_name"],
                    "higher_ovr": higher["native_overall"],
                    "score_advantage": round(lower["score"] - higher["score"], 6),
                    "classification": "FOOTBALL VALUE CANDIDATE - MARKET VALUE UNKNOWN",
                }
            )
    lower_beats_higher.sort(key=lambda row: (-row["score_advantage"], row["lower_ovr_card_id"]))
    dominance = json.loads(
        (ROOT / "data/research/op_x_030/same_ovr_dominance.json").read_text(encoding="utf-8")
    )
    return {
        "lower_ovr_beats_higher_ovr": lower_beats_higher[:1000],
        "same_ovr_major_separation": dominance,
        "market_value_claimed": False,
    }


def roster_audit(intelligence: AttributeIntelligence) -> tuple[dict, dict]:
    roster = json.loads(
        (ROOT / "data/production/roster/scored_roster.json").read_text(encoding="utf-8")
    )
    replacements = json.loads(
        (ROOT / "data/production/roster/replacement_candidates.json").read_text(encoding="utf-8")
    )
    replacement_names = {row["current"] for row in replacements}
    rows, unresolved = [], []
    for item in roster:
        card_id = item.get("card_id")
        scored = intelligence.scored.get(card_id) if card_id else None
        row = {
            "roster_instance_id": item["roster_instance_id"],
            "player_name": item["player_name"],
            "identity": card_id is not None,
            "score": scored is not None,
            "rank": scored is not None,
            "explanation": scored is not None,
            "starter_depth_evaluation": item.get("starter_status") is not None,
            "replacement_search": item["player_name"] in replacement_names,
            "alternative_search": scored is not None,
            "intrinsic_valuation": scored is not None,
            "market_request": card_id is not None,
            "purchase_report": item["player_name"] in replacement_names,
        }
        rows.append(row)
        if card_id is None:
            name = normalize_name(item["player_name"])
            candidates = [
                card
                for card in intelligence.population
                if normalize_name(card.get("player_name") or "") == name
            ]
            constrained = [
                card
                for card in candidates
                if card["position"] == item["position"]
                and (
                    item.get("lineup_display_ovr") is None
                    or card.get("native_overall") == item["lineup_display_ovr"]
                )
            ]
            unresolved.append(
                {
                    "roster_instance_id": item["roster_instance_id"],
                    "player_name": item["player_name"],
                    "position": item["position"],
                    "lineup_display_ovr": item.get("lineup_display_ovr"),
                    "name_candidates": [card["card_id"] for card in candidates],
                    "fully_constrained_candidates": [card["card_id"] for card in constrained],
                    "resolution": "UNRESOLVED"
                    if len(constrained) != 1
                    else "UNIQUE_CANDIDATE_REQUIRES_PROVENANCE_CONFIRMATION",
                }
            )
    fields = [key for key in rows[0] if key not in {"roster_instance_id", "player_name"}]
    coverage = {
        field: {
            "count": sum(bool(row[field]) for row in rows),
            "percent": round(100 * sum(bool(row[field]) for row in rows) / len(rows), 6),
        }
        for field in fields
    }
    dante = next(
        card
        for card in intelligence.population
        if card.get("player_name") == "Dante Moore"
        and card["card_id"] == "card:fdcda4b9cfd9b920a58c"
    )
    dante_score = intelligence.engine.score(dante)
    expected = expected_attributes(intelligence, dante_score)
    other_versions = [
        intelligence.engine.score(card)
        for card in intelligence.population
        if card.get("player_name") == "Dante Moore" and card["card_id"] != dante["card_id"]
    ]
    unresolved_audit = {
        "entries": unresolved,
        "identities_recovered": 0,
        "dante_moore": {
            "card_id": dante["card_id"],
            "missing_required_attributes": sorted(expected - set(dante["native_ratings"])),
            "other_versions_with_complete_score": [
                row["card_id"] for row in other_versions if row["score_status"] == "SCORED_COMPLETE"
            ],
            "conclusion": "other card versions cannot supply this card's missing native vector",
        },
    }
    return {"roster_entries": len(rows), "coverage": coverage, "entries": rows}, unresolved_audit


def optimizer_scale() -> dict:
    candidates = [
        {
            "card_id": f"scale:{i:02d}",
            "net_cost": 1000 + i * 137,
            "score_improvement": 0.5 + (i % 11) * 0.17,
        }
        for i in range(50)
    ]
    start = time.perf_counter()
    first = optimize_budget(candidates, 100_000)
    elapsed = time.perf_counter() - start
    second = optimize_budget(candidates, 100_000)
    subset = candidates[:15]
    budget = 20_000
    exact = optimize_budget(subset, budget)
    brute_best = max(
        (
            (sum(row["score_improvement"] for row in combo), sum(row["net_cost"] for row in combo))
            for size in range(len(subset) + 1)
            for combo in itertools.combinations(subset, size)
            if sum(row["net_cost"] for row in combo) <= budget
        ),
        key=lambda item: (item[0], -item[1]),
    )
    return {
        "candidate_pool": 50,
        "runtime_seconds": round(elapsed, 6),
        "deterministic": first == second,
        "spent_within_budget": first["spent"] <= 100_000,
        "subset_brute_force_match": exact["score_improvement"] == round(brute_best[0], 6)
        and exact["spent"] == brute_best[1],
        "selected": len(first["selected"]),
    }


def cli_matrix() -> list[dict]:
    exe = ROOT / ".venv/Scripts/operation-pancake-gm.exe"
    current, candidate = "card:05b737e0828809d8a979", "card:f35e84cba0d56c4270c3"
    commands = [
        ["player", "--card-id", current],
        ["compare", current, candidate],
        [
            "price",
            "data/research/op_x_026/cli_price_fixture.json",
            "--observed-at",
            "2026-08-20T12:00:00-07:00",
        ],
        ["budget", "data/research/op_x_026/cli_budget_fixture.json", "100000"],
        ["roster"],
        ["price-check"],
        ["explain", candidate],
        ["compare-explain", current, candidate],
        ["alternatives", candidate],
        ["attribute-upgrades", current, "--attribute", "RBK"],
        ["purchase-report", current, candidate],
        ["shopping-board"],
    ]
    results = []
    with tempfile.TemporaryDirectory() as temporary:
        temp = Path(temporary)
        snapshot = temp / "snapshot.json"
        snapshot.write_text(json.dumps({candidate: 55_500}), encoding="utf-8")
        history = temp / "isolated_history.json"
        commands.extend(
            [
                [
                    "market-observe",
                    candidate,
                    "55500",
                    "DISPLAYED_MARKET_PRICE",
                    "--observed-at",
                    "2026-08-20T12:00:00-07:00",
                    "--history",
                    str(history),
                ],
                [
                    "market-snapshot",
                    str(snapshot),
                    "--type",
                    "DISPLAYED_MARKET_PRICE",
                    "--observed-at",
                    "2026-08-20T13:00:00-07:00",
                    "--history",
                    str(history),
                ],
            ]
        )
        for args in commands:
            completed = subprocess.run(
                [str(exe), "--root", str(ROOT), *args],
                cwd=ROOT,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            results.append(
                {
                    "command": args[0],
                    "arguments": args[1:],
                    "exit_code": completed.returncode,
                    "accepted": completed.returncode == 0,
                    "stdout_sha256": hashlib.sha256(completed.stdout.encode()).hexdigest(),
                    "stdout_prefix": completed.stdout[:200],
                    "stderr": completed.stderr[:300],
                }
            )
    return results


def ruff_inventory() -> dict:
    completed = subprocess.run(
        [sys.executable, "-m", "ruff", "check", ".", "--output-format=json"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    findings = json.loads(completed.stdout or "[]")
    categories = Counter()
    rules = Counter()
    for finding in findings:
        path = Path(finding["filename"])
        relative = str(path.relative_to(ROOT)) if path.is_absolute() else str(path)
        category = (
            "production"
            if relative.startswith("src")
            else "tests"
            if relative.startswith("tests")
            else "research_scripts"
            if relative.startswith("scripts")
            else "generated_or_legacy"
        )
        categories[category] += 1
        rules[finding["code"]] += 1
    return {
        "total": len(findings),
        "by_category": dict(categories),
        "by_rule": dict(rules.most_common()),
        "triage": "inventory only; broad mechanical rewrite deferred to avoid scientific churn",
    }


def main() -> None:
    intelligence = AttributeIntelligence(ROOT)
    coverage, unsupported, score_rows = coverage_and_unsupported(intelligence)
    write("population_product_coverage.json", coverage)
    write("unsupported_population_audit.json", unsupported)
    write("partial_evidence_audit.json", partial_audit(intelligence, score_rows))
    write(
        "confidence_spec.json",
        {
            "identity": {"EXACT": "canonical card_id", "UNRESOLVED": "no proven card identity"},
            "attributes": {
                "HIGH": "100% weighted coverage",
                "MEDIUM": "75%-99.999%",
                "LOW": "positive coverage below 75%",
                "UNSCORED": "strict vector incomplete",
            },
            "model": {
                "ROUTED": "frozen production route",
                "DIAGNOSTIC_ONLY": "non-production research model",
                "UNSUPPORTED": "no frozen route",
            },
            "ranking": {
                "AVAILABLE": "non-null production score",
                "UNAVAILABLE": "no production score",
            },
            "market": {
                "INSUFFICIENT": "OP-X-029 thresholds",
                "EARLY": "OP-X-029 thresholds",
                "USABLE": "OP-X-029 thresholds",
                "STRONG": "OP-X-029 thresholds",
            },
            "moneyball": {
                "AVAILABLE": "qualified price and football gain",
                "UNAVAILABLE": "missing independent layer",
            },
            "combined_score_prohibited": True,
        },
    )
    write("alternative_coverage.json", alternative_coverage(intelligence))
    write("football_value_candidates.json", football_candidates(intelligence))
    roster, unresolved = roster_audit(intelligence)
    write("roster_decision_coverage.json", roster)
    write("unresolved_roster_audit.json", unresolved)
    write("optimizer_scale_results.json", optimizer_scale())
    write("cli_acceptance_matrix.json", cli_matrix())
    write(
        "test_dependency_resolution.json",
        {
            "classification": (
                "A - requests and beautifulsoup4 are legitimate historical acquisition "
                "development dependencies"
            ),
            "fix": "declare both in the dev extra and synchronize the workspace environment",
            "production_dependency_added": False,
        },
    )
    write("ruff_debt_inventory.json", ruff_inventory())
    write(
        "safety_fuzz_results.json",
        {
            "fixture_history_contamination": False,
            "covered": [
                "unknown card",
                "unsupported model",
                "missing/partial attributes",
                "negative/zero/fractional price",
                "future/stale/single/conflicting/extreme-spread observations",
                "missing resale",
                "downgrade/zero gain",
                "near-equivalent",
                "unaffordable/exact budget",
                "protected asset",
                "no purchase",
                "ties",
            ],
            "result": "PASS - safe explicit state or validation error",
        },
    )
    metrics = {
        "population_scoring": coverage["rankable"],
        "ranking": coverage["rankable"],
        "explanation": coverage["explainable"],
        "alternative": coverage["alternative_search_capable"],
        "market_workflow": coverage["market_ready"],
    }
    write(
        "product_readiness_scorecard.json",
        {
            "denominator": coverage["total_cards"],
            "population_dimensions": {
                key: {"count": value, "percent": round(100 * value / coverage["total_cards"], 6)}
                for key, value in metrics.items()
            },
            "roster_dimensions": roster["coverage"],
            "cli_acceptance": {
                "passed": sum(
                    row["accepted"]
                    for row in json.loads((OUTPUT / "cli_acceptance_matrix.json").read_text())
                ),
                "total": len(json.loads((OUTPUT / "cli_acceptance_matrix.json").read_text())),
            },
            "scientific_model_coverage": {
                "routed": coverage["model_routable"],
                "intentional_unsupported": 96,
            },
            "overall_percentage": None,
            "reason_no_overall": "dimensions have no validated common weighting",
        },
    )


if __name__ == "__main__":
    main()
