"""Integration tests for loading the real canonical QB research database."""

from pathlib import Path

import pytest

from operation_pancake.importers.position_database_importer import (
    PositionImportResult,
    import_registered_position,
)
from operation_pancake.importers.position_registry import create_default_registry
from operation_pancake.repository.canonical_repository import CanonicalRepository

CANONICAL_WORKBOOK = Path("data/canonical/canonical_v1.9.xlsx")
QB_ATTRIBUTES = {
    "SPD",
    "ACC",
    "AGI",
    "AWR",
    "STR",
    "TGH",
    "THP",
    "TAC",
    "SAC",
    "MAC",
    "DAC",
    "RUN",
    "TUP",
    "PAC",
    "BSK",
}


@pytest.fixture(scope="module")
def canonical_qbs() -> tuple[CanonicalRepository, PositionImportResult]:
    """Load canonical QBs through the registered application architecture."""
    repository = CanonicalRepository()
    registry = create_default_registry()
    result = import_registered_position("QB", registry, repository)
    return repository, result


def test_all_canonical_qbs_load_through_registered_repository(
    canonical_qbs: tuple[CanonicalRepository, PositionImportResult],
) -> None:
    repository, result = canonical_qbs

    assert CANONICAL_WORKBOOK.is_file()
    assert result.position == "QB"
    assert result.sheet_name == "QB_Cards"
    assert result.total_rows == 74
    assert result.imported_count == 74
    assert result.failure_count == 0
    assert result.is_valid
    assert repository.player_count == 74
    assert len(repository.players_by_position("QB")) == 74


def test_canonical_qbs_preserve_identity_ratings_and_provenance(
    canonical_qbs: tuple[CanonicalRepository, PositionImportResult],
) -> None:
    repository, _ = canonical_qbs
    card = repository.qb_by_id("QB-0001")

    assert card is not None
    assert card.name == "Julian Sayin"
    assert card.position == "QB"
    assert card.overall == 87
    assert card.program == "Standouts"
    assert set(card.attributes) == QB_ATTRIBUTES
    assert card.source == "SRC-QB-001 | all qb.pdf p.1"
    assert card.source_record == "QB_Cards!5"
    assert card.metadata == {
        "qb_id": "QB-0001",
        "source_id": "SRC-QB-001",
        "source_locator": "all qb.pdf p.1",
        "population_scope": "PRIMARY 80+ POPULATION",
        "model_role": "DEVELOPMENT",
        "unique_profile_key": (
            "Pocket Passer|79-79-75-81-46-90-86-87-88-87-86-82-86-85-70"
        ),
        "duplicate_note": None,
        "frozen_score_check": pytest.approx(83.98),
        "frozen_score_formula": 83.98,
        "formula_delta": pytest.approx(0, abs=1e-12),
        "workbook_sheet": "QB_Cards",
        "workbook_row": 5,
    }


def test_every_canonical_qb_has_stable_identity_and_only_qb_ratings(
    canonical_qbs: tuple[CanonicalRepository, PositionImportResult],
) -> None:
    repository, _ = canonical_qbs
    cards = repository.players_by_position("QB")

    assert len({card.metadata["qb_id"] for card in cards}) == 74
    assert all(set(card.attributes) == QB_ATTRIBUTES for card in cards)
    assert all(card.metadata["source_id"] for card in cards)
    assert all(card.metadata["source_locator"] for card in cards)
    assert all(card.metadata["population_scope"] for card in cards)
    assert all(card.metadata["model_role"] for card in cards)
    assert all(card.metadata["unique_profile_key"] for card in cards)
    assert all(card.metadata["workbook_sheet"] == "QB_Cards" for card in cards)
    assert len({card.metadata["workbook_row"] for card in cards}) == 74


def test_profile_duplicate_and_boundary_records_are_retained(
    canonical_qbs: tuple[CanonicalRepository, PositionImportResult],
) -> None:
    repository, _ = canonical_qbs
    profile = "Pocket Passer|79-73-73-78-55-80-79-74-79-80-76-65-71-78-66"
    duplicates = repository.qbs_by_profile(profile)

    assert {card.metadata["qb_id"] for card in duplicates} == {"QB-0067", "QB-0068"}
    assert {card.program for card in duplicates} == {"Core Rare", "Platinum Rare"}
    assert {card.metadata["model_role"] for card in duplicates} == {
        "DEVELOPMENT",
        "PROFILE DUPLICATE — EXCLUDED FROM MODEL COUNT",
    }

    boundaries = repository.players_by_metadata(
        "population_scope", "PROGRESSION BOUNDARY <80"
    )
    assert len(boundaries) == 1
    assert boundaries[0].metadata["model_role"] == "DEVELOPMENT BOUNDARY"
