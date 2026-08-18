import json
from pathlib import Path

from operation_pancake.research.cfb27_alpha_population import build_alpha_population
from operation_pancake.research.cfb27_alpha_readiness import build_alpha_readiness

ROOT = Path(__file__).resolve().parents[1]


def test_alpha_population_reuses_snapshotted_vectors_without_mutating_state():
    persisted = json.loads((ROOT / "data/external/cfb_fan_population_state.json").read_text())
    alpha = build_alpha_population(ROOT)
    summary = alpha["summary"]
    assert summary["total"] == len(persisted["cards"]) == 8838
    assert summary["persisted_complete"] == 8309
    assert summary["mutates_persisted_state"] is False
    assert summary["alpha_complete"] >= summary["persisted_complete"]
    assert summary["alpha_complete"] + summary["alpha_partial"] == 8838
    assert summary["alpha_position_only_promotions"] == summary["alpha_complete"] - 8309


def test_promoted_alpha_cards_preserve_cfb27_position_and_provenance():
    alpha = build_alpha_population(ROOT)
    promoted = [
        card
        for card in alpha["cards"].values()
        if (card.get("metadata") or {}).get("secondary_position_non_blocking")
    ]
    assert promoted
    for card in promoted:
        metadata = card["metadata"]
        assert card["position"] == metadata["canonical_position"]
        assert metadata["alpha_canonical_source"] == "CFB_FAN"
        assert metadata["alpha_canonical_taxonomy"] == "CFB27_GAME"
        assert metadata["secondary_structured_position"] != card["position"]
        assert card["extraction_status"] == "COMPLETE"
        assert len(card["displayed_ratings"]) >= 15


def test_formula_readiness_is_derived_from_alpha_population():
    readiness = build_alpha_readiness(ROOT)
    population = readiness["alpha_population"]
    eligibility = readiness["formula_eligibility"]
    assert eligibility["eligible"] + eligibility["excluded"] == population["total"]
    assert readiness["natural_experiment_inventory"]["same_ovr_archetype_cells"] > 0
    assert readiness["natural_experiment_inventory"]["pairwise_comparisons"] > 0
    for position in ("C", "CB", "FS", "SS", "DT", "SAM", "MIKE", "WILL", "LEDG", "REDG"):
        assert position in readiness["focus_position_readiness"]
