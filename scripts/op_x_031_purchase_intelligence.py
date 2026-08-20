"""Generate OP-X-031 unified purchase and shopping-board artifacts."""

from __future__ import annotations

import json
import statistics
from pathlib import Path

from operation_pancake.production.purchase import PurchaseIntelligence

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data/research/op_x_031"


def write(name: str, payload: object) -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    text = (
        payload
        if isinstance(payload, str)
        else json.dumps(payload, indent=2, sort_keys=True) + "\n"
    )
    (OUTPUT / name).write_text(text, encoding="utf-8")


def quantile(values: list[float], percentile: float) -> float:
    ordered = sorted(values)
    location = (len(ordered) - 1) * percentile / 100
    lower = int(location)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = location - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def main() -> None:
    engine = PurchaseIntelligence(ROOT)
    reports = [engine.report(current, candidate) for current, candidate in engine.valuations]
    write(
        "purchase_report_spec.json",
        {
            "sections": [
                "identity",
                "football",
                "why",
                "roster",
                "intrinsic_value",
                "alternatives",
                "market",
                "cost",
                "moneyball",
                "decision",
            ],
            "decision_hierarchy": [
                "identity",
                "model support",
                "football upgrade",
                "upgrade magnitude",
                "alternative challenge",
                "market sufficiency",
                "net cost",
                "efficiency",
                "budget",
            ],
            "firewall": {
                "ranking_coefficients": "UNCHANGED",
                "op_x_028_intrinsic_definition": "UNCHANGED",
                "op_x_029_sample_rules": "UNCHANGED",
                "fixture_market_evidence": "EXCLUDED",
            },
        },
    )
    score_gains = [row["score_gain"] for row in engine.reference if row["score_gain"] > 0]
    rank_gains = [row["rank_gain"] for row in engine.reference if row["rank_gain"] > 0]
    write(
        "upgrade_tiers.json",
        {
            "method": "quintile of mean empirical score-gain and rank-gain percentiles",
            "labels": ["MARGINAL", "MODEST", "MEANINGFUL", "MAJOR", "TRANSFORMATIVE"],
            "reference_opportunities": len(score_gains),
            "score_gain_quintiles": {
                str(p): round(quantile(score_gains, p), 6) for p in (20, 40, 60, 80)
            },
            "rank_gain_quintiles": {
                str(p): round(quantile(rank_gains, p), 6) for p in (20, 40, 60, 80)
            },
            "price_included": False,
        },
    )
    write("current_purchase_reports.json", reports)
    write(
        "target_premiums.json",
        [
            {
                "current": report["current_player"]["player_name"],
                "target": report["candidate"]["player_name"],
                **(report["alternatives"]["target_premium"] or {"status": "NO NEAR EQUIVALENT"}),
            }
            for report in reports
        ],
    )
    board = engine.shopping_board()
    write("roster_shopping_board.json", board)
    write(
        "alternative_shopping_board.json",
        [
            {
                "current": report["current_player"]["player_name"],
                "best_football": report["candidate"]["player_name"],
                "best_near_equivalent": report["alternatives"]["best_near_equivalent"],
                "best_value": "PRICE CHECK REQUIRED",
                "budget": "PRICE CHECK REQUIRED",
                "premium": report["candidate"]["player_name"],
                "reason": "alternative prices lack sufficient evidence",
            }
            for report in reports
        ],
    )
    write(
        "budget_integration.json",
        {
            "evidence_warning": (
                "OP-X-027 prices are contextual; allocations are scenarios, not BUY"
            ),
            "budgets": {
                str(budget): engine.optimize_reports(reports, budget)
                for budget in (
                    50_000,
                    100_000,
                    150_000,
                    250_000,
                    500_000,
                    750_000,
                    1_000_000,
                    2_000_000,
                    5_000_000,
                )
            },
        },
    )
    write(
        "decision_change_spec.json",
        {
            "material_fields": ["gm_action", "market_evidence_quality", "net_upgrade_cost"],
            "ignored_alone": ["ingestion timestamp", "observation age metadata"],
            "examples": ["PRICE CHECK REQUIRED -> WAIT", "WAIT -> BUY", "BUY -> WAIT"],
            "persistence_hook": "compare previous purchase object with regenerated object",
        },
    )
    write("evidence_request_priority.json", engine.evidence_priority(reports, limit=2))
    text = "# Current Pancake GM Purchase Reports\n\n" + "\n---\n\n".join(
        engine.render(report) for report in reports
    )
    write("CURRENT_REPORTS.md", text)
    write(
        "population_summary.json",
        {
            "shopping_board_rows": len(board),
            "purchase_reports": len(reports),
            "mean_reference_score_gain": round(statistics.mean(score_gains), 6),
        },
    )


if __name__ == "__main__":
    main()
