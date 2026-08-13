"""Tests for canonical workbook import validation reporting."""

from pathlib import Path

from openpyxl import Workbook

from operation_pancake.reports.import_validation import validate_te_cards


def create_validation_workbook(
    path: Path,
    rows: list[list[object]],
) -> None:
    """Create a temporary canonical-style TE workbook."""
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
    """Return one valid canonical-style TE row."""
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


def test_valid_workbook_imports_all_rows(tmp_path: Path) -> None:
    path = tmp_path / "canonical.xlsx"
    create_validation_workbook(
        path,
        [
            valid_row(),
            valid_row("TE-002", "Todd Heap"),
        ],
    )

    report = validate_te_cards(path)

    assert report.total_rows == 2
    assert report.imported_count == 2
    assert report.failure_count == 0
    assert report.duplicate_card_ids == set()
    assert report.is_valid


def test_invalid_row_is_reported(tmp_path: Path) -> None:
    path = tmp_path / "canonical.xlsx"
    bad_row = valid_row()
    bad_row[5] = "unknown"

    create_validation_workbook(path, [bad_row])

    report = validate_te_cards(path)

    assert report.total_rows == 1
    assert report.imported_count == 0
    assert report.failure_count == 1
    assert report.failures[0].source_record == "TE_Cards!2"
    assert report.failures[0].error_type == "TypeError"
    assert not report.is_valid


def test_duplicate_card_id_is_reported(tmp_path: Path) -> None:
    path = tmp_path / "canonical.xlsx"
    create_validation_workbook(
        path,
        [
            valid_row("TE-001", "Mike Bennett"),
            valid_row("TE-001", "Todd Heap"),
        ],
    )

    report = validate_te_cards(path)

    assert report.imported_count == 2
    assert report.duplicate_card_ids == {"TE-001"}
    assert not report.is_valid


def test_missing_card_id_does_not_create_false_duplicate(
    tmp_path: Path,
) -> None:
    path = tmp_path / "canonical.xlsx"

    first = valid_row()
    first[0] = None

    second = valid_row(player="Todd Heap")
    second[0] = None

    create_validation_workbook(path, [first, second])

    report = validate_te_cards(path)

    assert report.imported_count == 2
    assert report.duplicate_card_ids == set()
    assert report.is_valid


def test_good_rows_survive_when_another_row_fails(tmp_path: Path) -> None:
    path = tmp_path / "canonical.xlsx"

    bad_row = valid_row("TE-002", "Broken Player")
    bad_row[2] = None

    create_validation_workbook(
        path,
        [
            valid_row(),
            bad_row,
        ],
    )

    report = validate_te_cards(path)

    assert report.total_rows == 2
    assert report.imported_count == 1
    assert report.failure_count == 1
    assert report.imported_cards[0].name == "Mike Bennett"