import json
from pathlib import Path

from operation_pancake.research.cfb27_op_x_012 import build_op_x_012

ROOT = Path(__file__).resolve().parents[1]
RESEARCH = ROOT / "data/research/cfb27_op_x_012"


def load(name):
    return json.loads((RESEARCH / f"{name}.json").read_text())


def test_public_denominator_and_card_count_do_not_regress():
    coverage = load("database_coverage_v3")
    checkpoint = json.loads(
        (ROOT / "data/external/cfb_fan_population_v3_checkpoint.json").read_text()
    )
    state = json.loads((ROOT / "data/external/cfb_fan_population_state.json").read_text())
    assert coverage["public_denominator"] == 8838
    assert coverage["unique_discovered"] == len(checkpoint["cards"])
    assert coverage["ingested"] == len(state["cards"])
    assert coverage["ingested"] > 435
    assert coverage["full_native_vectors"] == 432


def test_listing_vectors_remain_partial_and_unknown_is_not_zero():
    state = json.loads((ROOT / "data/external/cfb_fan_population_state.json").read_text())
    partial = next(
        row
        for row in state["cards"].values()
        if row["extraction_status"] == "PARTIAL_LISTING_VECTOR"
    )
    assert partial["release_date"] is None
    assert 0 < len(partial["displayed_ratings"]) < 10


def test_same_player_versions_survive_global_deduplication():
    state = json.loads((ROOT / "data/external/cfb_fan_population_state.json").read_text())
    by_player = {}
    for card in state["cards"].values():
        by_player.setdefault(card["external_player_id"], set()).add(card["external_card_id"])
    assert any(len(card_ids) > 1 for card_ids in by_player.values())
    assert len({row["external_card_id"] for row in state["cards"].values()}) == len(state["cards"])


def test_upgradeability_requires_evidence_and_keeps_unknown():
    rows = load("upgrade_eligibility_map")
    validated = [row for row in rows if row["eligibility"] == "VALIDATED_UPGRADEABLE"]
    unknown = [row for row in rows if row["eligibility"] == "UNKNOWN"]
    assert validated and unknown
    assert all(row["source"] and row["confidence"] != "NO_CARD_LEVEL_EVIDENCE" for row in validated)
    assert all(row["system"] is None for row in unknown)


def test_native_active_and_market_boundaries_remain_intact():
    analysis = build_op_x_012(ROOT)
    assert analysis["market_source_discovery"]["CFB_FAN"]["completed_sales"] is False
    assert analysis["validation"]["native_active_conflation"] is False
    assert analysis["validation"]["listing_sale_conflation"] is False


def test_generation_is_deterministic_and_source_conflicts_are_preserved():
    first = build_op_x_012(ROOT)
    assert first == build_op_x_012(ROOT)
    assert first["freeze"]["source_commit"] == "83d10a8"
    assert first["source_conflicts_v3"]["overwrite"] is False
    assert all(value is False for value in first["validation"].values())
