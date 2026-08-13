"""Tests for the Operation Pancake canonical workbook importer."""

from pathlib import Path

import pytest
from openpyxl import Workbook

from operation_pancake.importers.workbook_importer import WorkbookImporter


def create_test_workbook(path: Path) -> None:
    """Create a small workbook used only by importer tests."""
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Players"

    sheet.append(["Name", "Position", "OVR", "SPD"])
    sheet.append(["Marcus Allen", "HB", 81, 85])
    sheet.append(["Marshall Faulk", "HB", 82, 86])
    sheet.append([None, None, None, None])

    progression = workbook.create_sheet("Progression")
    progression.append(["Player", "Start OVR", "End OVR"])
    progression.append(["Marcus Allen", 81, 82])

    workbook.save(path)
    workbook.close()


def test_missing_workbook_is_rejected(tmp_path: Path) -> None:
    importer = WorkbookImporter(tmp_path / "missing.xlsx")

    with pytest.raises(FileNotFoundError):
        importer.validate_source()


def test_non_workbook_extension_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "canonical.txt"
    path.write_text("not a workbook")

    importer = WorkbookImporter(path)

    with pytest.raises(ValueError):
        importer.validate_source()


def test_sheet_names_are_read(tmp_path: Path) -> None:
    path = tmp_path / "canonical.xlsx"
    create_test_workbook(path)

    importer = WorkbookImporter(path)

    assert importer.sheet_names() == ["Players", "Progression"]


def test_records_are_read_with_headers(tmp_path: Path) -> None:
    path = tmp_path / "canonical.xlsx"
    create_test_workbook(path)

    importer = WorkbookImporter(path)
    records = importer.records("Players")

    assert len(records) == 2
    assert records[0].values == {
        "Name": "Marcus Allen",
        "Position": "HB",
        "OVR": 81,
        "SPD": 85,
    }


def test_record_preserves_provenance(tmp_path: Path) -> None:
    path = tmp_path / "canonical.xlsx"
    create_test_workbook(path)

    importer = WorkbookImporter(path)
    record = importer.records("Players")[0]

    assert record.sheet_name == "Players"
    assert record.row_number == 2
    assert record.source_record == "Players!2"


def test_blank_rows_are_ignored(tmp_path: Path) -> None:
    path = tmp_path / "canonical.xlsx"
    create_test_workbook(path)

    importer = WorkbookImporter(path)

    assert len(importer.records("Players")) == 2


def test_unknown_sheet_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "canonical.xlsx"
    create_test_workbook(path)

    importer = WorkbookImporter(path)

    with pytest.raises(KeyError):
        importer.records("Does Not Exist")