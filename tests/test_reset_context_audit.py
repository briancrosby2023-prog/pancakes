"""Tests for Saturday Reset context and TE progression resolution."""

import json
from pathlib import Path

import pytest

from operation_pancake.research.reset_context_audit import (
    SPARSE_IDS,
    UNRESOLVED,
    build_reset_context_audit,
    write_reset_context_artifacts,
)


@pytest.fixture(scope="module")
def progression() -> dict[str, object]:
    result = json.loads(
        Path("data/research/progression_audit/progression_inventory.json").read_text(
            encoding="utf-8"
        )
    )
    result["confirmed_transitions"] = json.loads(
        Path("data/research/progression_audit/confirmed_transition_deltas.json").read_text(
            encoding="utf-8"
        )
    )
    return result


@pytest.fixture(scope="module")
def audit(progression: dict[str, object]) -> dict[str, object]:
    return build_reset_context_audit(
        progression,
        "data/canonical/canonical_v1.9.xlsx",
        [str(path) for path in Path(".").rglob("*") if path.is_file()],
    )


def test_all_reset_series_are_conservatively_unresolved(
    audit: dict[str, object],
) -> None:
    linkages = audit["reset_linkages"]
    assert len(linkages) == 11
    assert sum(len(item["transitions"]) for item in linkages) == 22
    assert all(item["classification"] == UNRESOLVED for item in linkages)
    assert all(not item["raw_source_present"] for item in linkages)
    assert all(item["recovered_context"]["position"] is None for item in linkages)


def test_no_full_vectors_are_invented(audit: dict[str, object]) -> None:
    vectors = audit["reconstructed_vectors"]
    assert len(vectors) == 11
    for series in vectors:
        assert all(state["status"] == "MISSING" for state in series["vectors"].values())
        assert all(
            transition["status"] == "DIRECTLY_OBSERVED"
            for transition in series["known_transition_deltas"]
        )
    assert not audit["canonical_observations_modified"]


def test_sparse_transitions_remain_complete_but_position_unassigned(
    audit: dict[str, object],
) -> None:
    sparse = audit["sparse_transitions"]
    assert tuple(item["transition_id"] for item in sparse) == SPARSE_IDS
    assert all(item["delta_ovr"] == 1 for item in sparse)
    assert all(item["position"] == "UNSPECIFIED" for item in sparse)
    assert all(item["context_linkage"] == UNRESOLVED for item in sparse)
    assert all(item["positional_information_value"] == "UNASSIGNABLE" for item in sparse)


def test_three_te_candidates_preserve_observed_vectors_without_promotion(
    audit: dict[str, object],
) -> None:
    candidates = audit["te_progression_classifications"]
    assert len(candidates) == 3
    assert {item["player"] for item in candidates} == {
        "Eli Finley",
        "Jalen Hoffman",
        "Ozzie Newsome",
    }
    assert all(item["classification"] == UNRESOLVED for item in candidates)
    assert all(item["vector_provenance"] == "DIRECTLY_OBSERVED" for item in candidates)
    assert all(len(item["lower_vector"]) == 30 for item in candidates)
    assert all(not item["actual_upgrade_chain_established"] for item in candidates)


def test_te_false_link_warning_and_deltas_are_preserved(
    audit: dict[str, object],
) -> None:
    by_player = {item["player"]: item for item in audit["te_progression_classifications"]}
    assert by_player["Eli Finley"]["negative_deltas"] == {"TGH": -1}
    assert by_player["Jalen Hoffman"]["negative_deltas"] == {"TGH": -4}
    assert by_player["Ozzie Newsome"]["negative_deltas"] == {}
    assert by_player["Eli Finley"]["progression_metadata"]["Evidence_Type"] == (
        "Same-player card comparison"
    )


def test_template_and_source_gap_classification(audit: dict[str, object]) -> None:
    templates = audit["reset_template_analysis"]
    assert templates["raw_positive_point_range"] == [1, 26]
    assert templates["repeated_exact_template_count"] == 1
    gaps = audit["source_gaps"]
    assert len(gaps["REFERENCED_BUT_RAW_SOURCE_ABSENT"]) == 1
    assert len(gaps["NO_REFERENCE_EXISTS"]) == 3
    assert not audit["unsupported_linkages_promoted"]


def test_artifacts_are_deterministic(
    progression: dict[str, object], audit: dict[str, object], tmp_path: Path
) -> None:
    second = build_reset_context_audit(
        progression,
        "data/canonical/canonical_v1.9.xlsx",
        [str(path) for path in Path(".").rglob("*") if path.is_file()],
    )
    assert second == audit
    write_reset_context_artifacts(tmp_path, audit)
    assert len(list(tmp_path.glob("*.json"))) == 8
