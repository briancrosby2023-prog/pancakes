import json
from pathlib import Path

from operation_pancake.production.engine import ProductionEngine, load_population
from operation_pancake.production.registry import build_model_registry
from operation_pancake.production.roster import (
    RosterGMEngine,
    canonical_roster,
    reconcile_roster,
)

ROOT = Path(__file__).resolve().parents[1]


def engine():
    return ProductionEngine(build_model_registry(ROOT))


def test_identity_matching_accepts_unique_exact_and_rejects_tie():
    source = [
        {"roster_instance_id": "r", "slot": "WR1", "player": "A Player", "lineup_display_ovr": 85}
    ]
    base = {
        "player_name": "A Player",
        "position": "WR",
        "native_overall": 85,
        "program": "X",
        "archetype": "Speedster",
        "source": "test",
    }
    exact = reconcile_roster(source, [{**base, "card_id": "one"}])[0]
    assert exact["classification"] == "EXACT"
    tied = reconcile_roster(
        source,
        [
            {**base, "card_id": "one", "native_overall": 84},
            {**base, "card_id": "two", "native_overall": 84},
        ],
    )[0]
    assert tied["classification"] == "AMBIGUOUS" and tied["matched_card_id"] is None


def test_real_reconciliation_is_conservative_and_improves_prior_coverage():
    roster = json.loads(
        (
            ROOT / "data/research/cfb27_op_x_010/canonical_exports_v2/roster_instances.json"
        ).read_text()
    )
    rows = reconcile_roster(roster, load_population(ROOT))
    counts = {
        status: sum(row["classification"] == status for row in rows)
        for status in ("EXACT", "HIGH CONFIDENCE", "AMBIGUOUS", "UNRESOLVED")
    }
    assert counts == {"EXACT": 1, "HIGH CONFIDENCE": 17, "AMBIGUOUS": 1, "UNRESOLVED": 5}


def test_canonical_roster_schema_preserves_unknowns_and_provenance():
    source = [
        {
            "roster_instance_id": "r",
            "roster_id": "team",
            "slot": "WR1",
            "player": "Missing",
            "lineup_display_ovr": 88,
            "display_source": "screen",
        }
    ]
    resolution = reconcile_roster(source, [])
    row = canonical_roster(source, resolution, [], engine())[0]
    assert row["card_id"] is None and row["acquisition_cost"] is None
    assert row["provenance"]["roster"] == "screen"


def test_starter_selection_uses_score_not_displayed_overall():
    gm = RosterGMEngine(engine(), [])

    def item(name, order, score, ovr):
        return {
            "player_name": name,
            "position_family": "WR",
            "depth_slot": f"WR{order}",
            "depth_order": order,
            "starter_status": "STARTER" if order == 1 else "BACKUP",
            "card_id": name,
            "pancake": {"score": score},
            "lineup_display_ovr": ovr,
        }

    group = gm.evaluate_depth([item("OVR", 1, 70, 90), item("Pancake", 2, 80, 85)])[0]
    assert group["highest_ranked_roster_player"] == "Pancake"
    assert group["recommended_change"]["replace"] == "OVR"


def test_percentile_is_within_position_and_budget_is_optional():
    gm = RosterGMEngine(engine(), [{"position_family": "WR"}] * 100)
    assert gm.percentile("WR", 1) == 100
    assert gm.percentile("WR", 100) == 1
    assert gm.budget_decision(2, 10)["status"] == "PRICE CHECK REQUIRED"
    priced = gm.budget_decision(2, 10, candidate_price=300, current_resale=100, budget=250)
    assert priced["net_upgrade_cost"] == 200 and priced["affordable"] is True
    assert priced["improvement_per_coin"] == 0.01


def test_real_replacement_search_includes_rank_gain_role_and_attribute_tradeoffs():
    population = load_population(ROOT)
    scoring = engine()
    ranked = scoring.rank([scoring.score(card) for card in population])
    gm = RosterGMEngine(scoring, ranked, population)
    roster = json.loads((ROOT / "data/production/roster/canonical_roster.json").read_text())
    current = next(row for row in roster if row["player_name"] == "Anthony Donkoh")
    result = gm.replacements(current)
    best = result["candidates"]["best_overall"]
    assert result["status"] == "UPGRADE_AVAILABLE"
    assert best["position_rank_improvement"] > 0
    assert best["role_implication"] and best["attribute_deltas"]


def test_strength_aggregates_multiple_starters_into_one_position_group():
    population = load_population(ROOT)
    scoring = engine()
    ranked = scoring.rank([scoring.score(card) for card in population])
    gm = RosterGMEngine(scoring, ranked, population)
    roster = json.loads((ROOT / "data/production/roster/canonical_roster.json").read_text())
    replacements = [result for row in roster if (result := gm.replacements(row))]
    strength, priorities = gm.strength_and_priorities(roster, replacements)
    assert len([row for row in strength if row["position_family"] == "G"]) == 1
    assert all(row["priority_type"] == "QUALITY PRIORITY" for row in priorities)
