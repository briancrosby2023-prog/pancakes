"""Tests for importing position databases into the canonical repository."""

from pathlib import Path

from openpyxl import Workbook

from operation_pancake.importers.player_card_mapper import map_te_card
from operation_pancake.importers.position_database_importer import (
    import_position_database,
)
from operation_pancake.repository.canonical_repository import CanonicalRepository


def create_te_workbook(
    path: Path,
    rows: list[list[object]],
) -> None:
    """Create a temporary TE position database."""
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "TE_Cards"

    sheet.append(
        [
            "Card_ID",
            "Player",
            "OVR",
            "Program",
            "Archetype",
            "SPD",
            "CTH",
            "RBK",
            "Source_ID",
            "Source_Page",
            "Validation_Status",
            "Notes",
        ]
    )

    for row in rows:
        sheet.append(row)

    workbook.save(path)
    workbook.close()


def valid_row(
    card_id: str = "TE-001",
    player: str = "Mike Bennett",
) -> list[object]:
    """Return one valid TE position-database row."""
    return [
        card_id,
        player,
        82,
        "Test Program",
        "Gritty",
        84,
        82,
        80,
        "TE Research PDF",
        4,
        "validated",
        "Observed card.",
    ]


def test_imports_valid_position_database(tmp_path: Path) -> None:
    path = tmp_path / "te_database.xlsx"
    create_te_workbook(
        path,
        [
            valid_row(),
            valid_row("TE-002", "Todd Heap"),
        ],
    )

    repository = CanonicalRepository()

    result = import_position_database(
        workbook_path=path,
        sheet_name="TE_Cards",
        position="TE",
        mapper=map_te_card,
        repository=repository,
    )

    assert result.total_rows == 2
    assert result.imported_count == 2
    assert result.failure_count == 0
    assert result.is_valid
    assert repository.player_count == 2


def test_imported_cards_are_queryable(tmp_path: Path) -> None:
    path = tmp_path / "te_database.xlsx"
    create_te_workbook(path, [valid_row()])

    repository = CanonicalRepository()

    import_position_database(
        workbook_path=path,
        sheet_name="TE_Cards",
        position="TE",
        mapper=map_te_card,
        repository=repository,
    )

    cards = repository.players_by_position("TE")

    assert len(cards) == 1
    assert cards[0].name == "Mike Bennett"
    assert cards[0].overall == 82


def test_bad_row_is_reported_without_stopping_import(
    tmp_path: Path,
) -> None:
    path = tmp_path / "te_database.xlsx"

    bad_row = valid_row("TE-002", "Broken Player")
    bad_row[5] = "unknown"

    create_te_workbook(
        path,
        [
            valid_row(),
            bad_row,
        ],
    )

    repository = CanonicalRepository()

    result = import_position_database(
        workbook_path=path,
        sheet_name="TE_Cards",
        position="TE",
        mapper=map_te_card,
        repository=repository,
    )

    assert result.total_rows == 2
    assert result.imported_count == 1
    assert result.failure_count == 1
    assert repository.player_count == 1
    assert not result.is_valid


def test_duplicate_player_is_reported(tmp_path: Path) -> None:
    path = tmp_path / "te_database.xlsx"

    create_te_workbook(
        path,
        [
            valid_row(),
            valid_row(),
        ],
    )

    repository = CanonicalRepository()

    result = import_position_database(
        workbook_path=path,
        sheet_name="TE_Cards",
        position="TE",
        mapper=map_te_card,
        repository=repository,
    )

    assert result.imported_count == 1
    assert result.failure_count == 1
    assert repository.player_count == 1
    assert result.failures[0].error_type == "ValueError"


def test_position_mismatch_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "te_database.xlsx"
    create_te_workbook(path, [valid_row()])

    repository = CanonicalRepository()

    result = import_position_database(
        workbook_path=path,
        sheet_name="TE_Cards",
        position="QB",
        mapper=map_te_card,
        repository=repository,
    )

    assert result.imported_count == 0
    assert result.failure_count == 1
    assert repository.player_count == 0
    assert not result.is_valid