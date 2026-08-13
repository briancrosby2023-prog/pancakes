"""Tests for database-wide progression mining."""

from pathlib import Path

import pytest

from operation_pancake.research.progression_mining import (
    CONFIRMED,
    CONTRADICTED,
    UNRESOLVED,
    build_progression_audit,
    write_progression_artifacts,
)


@pytest.fixture(scope="module")
def audit() -> dict[str, object]:
    output = Path("data/research/progression_audit")
    return build_progression_audit(
        "data/canonical/canonical_v1.9.xlsx",
        [
            str(path)
            for path in Path("data/research").rglob("*")
            if path.is_file() and output not in path.parents
        ],
    )


def test_inventory_covers_every_canonical_position(audit: dict[str, object]) -> None:
    inventory = audit["inventory"]
    assert inventory["canonical_observation_count"] == 145
    assert inventory["observations_by_position"] == {"C": 3, "QB": 74, "TE": 68}
    assert inventory["unique_players_by_position"] == {"C": 3, "QB": 57, "TE": 54}
    assert inventory["repeated_player_groups"] == 26
    assert len(audit["canonical_cards"]) == 145


def test_candidate_classification_is_conservative(audit: dict[str, object]) -> None:
    candidates = audit["progression_candidates"]
    assert len(candidates) == 31
    counts = audit["inventory"]["candidate_classification_counts"]
    assert counts == {CONFIRMED: 2, CONTRADICTED: 26, UNRESOLVED: 3}
    assert not any(item["classification"] == "PROBABLE_PROGRESSION" for item in candidates)


def test_same_player_different_program_is_never_promoted(
    audit: dict[str, object],
) -> None:
    candidates = audit["progression_candidates"]
    cross_program = [item for item in candidates if item["lower_program"] != item["upper_program"]]
    assert cross_program
    assert all(item["classification"] == CONTRADICTED for item in cross_program)


def test_confirmed_chains_and_transition_deltas(audit: dict[str, object]) -> None:
    assert len(audit["confirmed_chains"]) == 12
    assert len(audit["confirmed_transitions"]) == 25
    by_position = audit["pattern_analysis"]["confirmed_by_position"]
    assert by_position == {"QB": 3, "UNSPECIFIED": 22}
    harrington = [item for item in audit["confirmed_transitions"] if item["position"] == "QB"]
    assert [item["delta_ovr"] for item in harrington] == [2, 3, 2]
    assert all(len(item["attribute_deltas"]) == 15 for item in harrington)
    assert all(item["unchanged_attributes"] == ["AWR", "TAC", "TGH"] for item in harrington)


def test_position_specific_attributes_are_preserved(audit: dict[str, object]) -> None:
    reset = next(
        item for item in audit["confirmed_transitions"] if item["transition_id"] == "SAT-11B"
    )
    assert reset["position"] == "UNSPECIFIED"
    assert reset["attribute_deltas"]["RCK"] == 4
    assert "THP" not in reset["attribute_deltas"]
    assert reset["general_ea_architecture_evidence_only"]
    assert not reset["can_constrain_qb_directly"]


def test_information_ranking_prefers_sparse_one_ovr_transitions(
    audit: dict[str, object],
) -> None:
    ranking = audit["high_information_ranking"]
    assert ranking[0]["changed_attribute_count"] == 1
    assert ranking[0]["delta_ovr"] == 1
    assert all(
        left["information_value_score"] >= right["information_value_score"]
        for left, right in zip(ranking[:-1], ranking[1:], strict=True)
    )


def test_constraint_matrix_and_qb_limits_are_explicit(audit: dict[str, object]) -> None:
    matrix = audit["constraint_matrix"]
    assert len(matrix) == 25
    assert sum(item["can_constrain_qb_directly"] for item in matrix) == 3
    assert sum(item["general_ea_architecture_evidence_only"] for item in matrix) == 22
    assert audit["qb_implications"]["additional_confirmed_qb_chains_beyond_harrington"] == 0
    assert not audit["formula_fitting_performed"]
    assert not audit["speculative_progressions_promoted"]


def test_output_is_deterministic(audit: dict[str, object], tmp_path: Path) -> None:
    output = Path("data/research/progression_audit")
    second = build_progression_audit(
        "data/canonical/canonical_v1.9.xlsx",
        [
            str(path)
            for path in Path("data/research").rglob("*")
            if path.is_file() and output not in path.parents
        ],
    )
    assert second == audit
    write_progression_artifacts(tmp_path, audit)
    assert len(list(tmp_path.glob("*.json"))) == 10
