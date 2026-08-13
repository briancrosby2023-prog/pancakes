"""Tests for the QB Formula Phase population and boundary research layer."""

import json
from pathlib import Path

import pytest

from operation_pancake.importers.position_database_importer import import_registered_position
from operation_pancake.importers.position_registry import create_default_registry
from operation_pancake.models.player_card import PlayerCard
from operation_pancake.repository.canonical_repository import CanonicalRepository
from operation_pancake.research.qb_formula_phase import (
    QB_RATING_FIELDS,
    build_qb_formula_research,
    observation_from_card,
    observations_from_repository,
    write_qb_formula_research,
)


@pytest.fixture(scope="module")
def qb_repository() -> CanonicalRepository:
    """Load all canonical QBs through the production repository pipeline."""
    repository = CanonicalRepository()
    result = import_registered_position("QB", create_default_registry(), repository)
    assert result.is_valid
    return repository


@pytest.fixture(scope="module")
def research(qb_repository: CanonicalRepository) -> dict[str, object]:
    """Build the canonical QB research result once for module tests."""
    return build_qb_formula_research(qb_repository)


def test_complete_population_and_partitions_are_represented(
    research: dict[str, object],
) -> None:
    population = research["population"]

    assert population["count"] == 74
    assert population["counts_by_archetype"] == {
        "Backfield Creator": 9,
        "Dual Threat": 10,
        "Pocket Passer": 52,
        "Pure Runner": 3,
    }
    assert population["counts_by_analysis_partition"] == {
        "boundary": 1,
        "fit": 51,
        "holdout": 18,
        "profile_duplicate": 1,
        "research_only": 3,
    }
    assert len(research["observations"]) == 74


def test_ovr_coverage_is_explicit(research: dict[str, object]) -> None:
    population = research["population"]

    assert population["overall_minimum"] == 79
    assert population["overall_maximum"] == 89
    assert population["missing_overall_levels"] == []
    assert population["counts_by_overall"] == {
        "79": 1,
        "80": 23,
        "81": 10,
        "82": 6,
        "83": 12,
        "84": 7,
        "85": 3,
        "86": 6,
        "87": 3,
        "88": 2,
        "89": 1,
    }
    assert population["sparse_ovr_archetype_cells"]


def test_all_rating_fields_have_global_and_archetype_statistics(
    research: dict[str, object],
) -> None:
    statistics = research["attribute_statistics"]

    assert tuple(statistics["global"]) == QB_RATING_FIELDS
    assert all(result["count"] == 74 for result in statistics["global"].values())
    assert set(statistics["by_archetype"]) == {
        "Backfield Creator",
        "Dual Threat",
        "Pocket Passer",
        "Pure Runner",
    }
    assert all(
        tuple(group["statistics"]) == QB_RATING_FIELDS
        for group in statistics["by_archetype"].values()
    )


def test_observation_rating_vectors_exclude_research_metadata(
    research: dict[str, object],
) -> None:
    observations = research["observations"]

    assert all(tuple(observation["ratings"]) == QB_RATING_FIELDS for observation in observations)
    assert all("model_role" not in observation["ratings"] for observation in observations)
    assert all("frozen_score_formula" not in observation["ratings"] for observation in observations)


def test_archetype_grouping_and_observation_order_are_deterministic(
    qb_repository: CanonicalRepository,
) -> None:
    first = observations_from_repository(qb_repository)
    second = observations_from_repository(qb_repository)

    assert first == second
    assert [observation.qb_id for observation in first] == sorted(
        observation.qb_id for observation in first
    )


def test_boundary_and_duplicate_evidence_is_retained(
    research: dict[str, object],
) -> None:
    evidence = research["boundary_evidence"]
    repeated = evidence["repeated_profiles"]
    explicit = evidence["explicit_boundary_records"]
    sequences = evidence["same_player_card_sequences"]

    assert len(repeated) == 1
    assert repeated[0]["qb_ids"] == ["QB-0067", "QB-0068"]
    assert len(explicit) == 1
    assert explicit[0]["qb_id"] == "QB-0074"
    assert explicit[0]["analysis_partition"] == "boundary"
    assert len(sequences) == 17
    assert sum(item["evidence_type"] == "same_player_same_ovr" for item in sequences) == 1
    assert all(item["confirmed_progression"] is False for item in sequences)
    assert evidence["adjacent_ovr_nearest_within_archetype"]
    assert evidence["same_ovr_maximum_contrasts_within_archetype"]


def test_formula_architectures_are_hypotheses_not_a_selected_winner(
    research: dict[str, object],
) -> None:
    assert research["formula_status"] == "unsolved"
    assert [item["id"] for item in research["architecture_hypotheses"]] == [
        "A",
        "B",
        "C",
        "D",
    ]
    assert "held_out_performance" in research["model_selection_criteria"]
    assert "ea_plausibility" in research["model_selection_criteria"]


def test_generated_analysis_is_byte_deterministic(
    qb_repository: CanonicalRepository,
    tmp_path: Path,
) -> None:
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"

    write_qb_formula_research(first, qb_repository)
    write_qb_formula_research(second, qb_repository)

    assert first.read_bytes() == second.read_bytes()
    assert json.loads(first.read_text(encoding="utf-8"))["population"]["count"] == 74


def test_checked_in_research_artifact_matches_canonical_analysis(
    research: dict[str, object],
) -> None:
    artifact = Path("data/research/qb_formula_phase_population_boundary.json")

    assert json.loads(artifact.read_text(encoding="utf-8")) == research


def test_missing_rating_is_rejected_instead_of_filled(
    qb_repository: CanonicalRepository,
) -> None:
    original = qb_repository.qb_by_id("QB-0001")
    assert original is not None
    ratings = dict(original.attributes)
    ratings.pop("BSK")
    malformed = PlayerCard(
        name=original.name,
        position=original.position,
        overall=original.overall,
        archetype=original.archetype,
        program=original.program,
        attributes=ratings,
        source=original.source,
        source_record=original.source_record,
        metadata=dict(original.metadata),
    )

    with pytest.raises(ValueError, match="exactly 15 fields"):
        observation_from_card(malformed)


def test_missing_research_classification_is_rejected(
    qb_repository: CanonicalRepository,
) -> None:
    original = qb_repository.qb_by_id("QB-0001")
    assert original is not None
    metadata = dict(original.metadata)
    metadata["model_role"] = None
    malformed = PlayerCard(
        name=original.name,
        position=original.position,
        overall=original.overall,
        archetype=original.archetype,
        program=original.program,
        attributes=dict(original.attributes),
        source=original.source,
        source_record=original.source_record,
        metadata=metadata,
    )

    with pytest.raises(ValueError, match="model_role"):
        observation_from_card(malformed)
