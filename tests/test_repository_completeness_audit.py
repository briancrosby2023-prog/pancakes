import json
from pathlib import Path

from operation_pancake.research.repository_completeness_audit import build_repository_audit

ROOT = Path(__file__).resolve().parents[1]


def audit():
    return build_repository_audit(ROOT)


def test_position_inventory_covers_all_repository_positions() -> None:
    result = audit()
    positions = {item["position"] for item in result["position_inventory"]}
    assert positions == {"C", "CB", "FB", "FS", "GUARD", "HB", "MLB", "QB", "SS", "TE", "WR"}
    qb = next(item for item in result["position_inventory"] if item["position"] == "QB")
    assert qb["canonical_cards"] == 74
    assert qb["complete_rating_vectors"] == 74


def test_readiness_is_dimensioned_not_single_accuracy() -> None:
    result = audit()
    qb = next(item for item in result["readiness"] if item["position"] == "QB")
    assert qb["STATIC_POPULATION"] == "READY"
    assert qb["FORMULA_RESEARCH"] == "READY"
    assert qb["INDEPENDENT_VALIDATION"] == "BLOCKED"
    assert "accuracy" not in qb
    assert all(
        item["recovery_priority"] in {"CRITICAL", "HIGH", "MEDIUM", "LOW"}
        for item in result["readiness"]
    )


def test_player_card_completeness_preserves_program_variants() -> None:
    result = audit()["player_card_completeness"]
    harrington = next(
        item
        for item in result["same_player_multiple_programs"]
        if item["player"] == "Joey Harrington"
    )
    assert len(harrington["programs"]) == 2
    assert result["canonical_cards_with_one_source"]


def test_progression_matrix_includes_recovered_inventory() -> None:
    matrix = {item["position"]: item for item in audit()["progression_matrix"]}
    assert matrix["WR"]["historical_only_chains"] == 3
    assert matrix["WR"]["missing_vectors"] == 14
    assert matrix["QB"]["validated_chains"] == 2
    assert matrix["QB"]["historical_only_chains"] == 1


def test_source_value_ranking_is_deterministic_and_actionable() -> None:
    first = audit()["source_value_ranking"]
    second = audit()["source_value_ranking"]
    assert first == second
    assert first[0]["source_id"] == "SRC-IMG-ARCH"
    assert first[0]["known_present"] is True
    assert all(item["status"] in {"PARTIAL", "UNPROCESSED", "NEEDS_REVIEW"} for item in first)


def test_wr_76_to_83_is_top_screenshot_priority() -> None:
    ranking = audit()["screenshot_recovery_ranking"]
    assert ranking[0]["record_id"] == "RECOVERY-PROG-WR-76-83"
    assert ranking[0]["one_ovr_transitions"] == 7


def test_formula_gaps_are_practical_and_position_specific() -> None:
    gaps = {item["position"]: item for item in audit()["formula_gap_map"]}
    assert "5 complete regular CUT Center profiles" in gaps["C"]["smallest_material_evidence_set"]
    assert ">=98%" in gaps["QB"]["operationally_solved_standard"]


def test_pc_gap_map_uses_ready_partial_blocked() -> None:
    gaps = {item["capability"]: item for item in audit()["pc_application_gap_map"]}
    assert gaps["card_lookup"]["status"] == "READY"
    assert gaps["progression_analysis"]["status"] == "PARTIAL"
    assert gaps["market_evaluation"]["status"] == "BLOCKED"


def test_external_schema_maps_to_staging_without_auto_promotion() -> None:
    schema = audit()["external_card_schema"]
    assert {
        "external_id",
        "player",
        "position",
        "overall",
        "source_reference",
        "retrieved_at",
    } <= set(schema["required"])
    assert schema["staging_mapping"]["automatic_canonical_promotion"] is False
    assert "displayed_ratings" in schema["recommended"]


def test_recovery_queue_is_deduplicated() -> None:
    queue = audit()["recovery_work_queue"]
    ids = [item["item_id"] for item in queue]
    assert len(ids) == len(set(ids))
    assert all(
        {"priority", "target", "why_it_matters", "expected_benefit", "blocked_by", "next_action"}
        <= item.keys()
        for item in queue
    )


def test_top_ten_recovery_output_is_exact_and_useful() -> None:
    targets = audit()["chatgpt_top_10_recovery_targets"]
    assert len(targets) == 10
    assert [item["rank"] for item in targets] == list(range(1, 11))
    assert "WR" in targets[0]["search_terms"] and "76" in targets[0]["search_terms"]
    assert all(item["partial_evidence_useful"] for item in targets)


def test_generated_artifacts_match_builder() -> None:
    result = audit()
    output = ROOT / "data/research/repository_completeness_audit"
    for key, value in result.items():
        assert json.loads((output / f"{key}.json").read_text()) == value
