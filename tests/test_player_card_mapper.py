"""Tests for canonical workbook player-card mapping."""

import pytest

from operation_pancake.importers.player_card_mapper import map_te_card
from operation_pancake.importers.workbook_importer import WorkbookRecord


def make_te_record(**overrides: object) -> WorkbookRecord:
    """Create a canonical-style TE_Cards row for mapper tests."""
    values = {
        "Card_ID": "TE-001",
        "Player": "Mike Bennett",
        "OVR": 82,
        "Program": "Test Program",
        "Archetype": "Gritty",
        "SPD": 84,
        "CTH": 82,
        "RBK": 80,
        "PBK": None,
        "Source_ID": "TE Research PDF",
        "Source_Page": 4,
        "Validation_Status": "validated",
        "Notes": "Observed card.",
    }
    values.update(overrides)

    return WorkbookRecord(
        sheet_name="TE_Cards",
        row_number=2,
        values=values,
    )


def test_maps_identity_fields() -> None:
    card = map_te_card(make_te_record())

    assert card.name == "Mike Bennett"
    assert card.position == "TE"
    assert card.overall == 82
    assert card.archetype == "Gritty"
    assert card.program == "Test Program"


def test_maps_observed_attributes() -> None:
    card = map_te_card(make_te_record())

    assert card.attributes == {
        "SPD": 84,
        "CTH": 82,
        "RBK": 80,
    }


def test_blank_attribute_is_not_invented() -> None:
    card = map_te_card(make_te_record())

    assert "PBK" not in card.attributes


def test_preserves_workbook_provenance() -> None:
    card = map_te_card(make_te_record())

    assert card.source == "TE Research PDF | 4"
    assert card.source_record == "TE_Cards!2"
    assert card.metadata["card_id"] == "TE-001"
    assert card.metadata["workbook_sheet"] == "TE_Cards"
    assert card.metadata["workbook_row"] == 2


def test_preserves_validation_status() -> None:
    card = map_te_card(make_te_record())

    assert card.confidence == "validated"


def test_missing_validation_status_becomes_unverified() -> None:
    card = map_te_card(make_te_record(Validation_Status=None))

    assert card.confidence == "unverified"


def test_missing_player_is_rejected() -> None:
    with pytest.raises(ValueError):
        map_te_card(make_te_record(Player=None))


def test_missing_overall_is_rejected() -> None:
    with pytest.raises(TypeError):
        map_te_card(make_te_record(OVR=None))


def test_invalid_attribute_is_rejected() -> None:
    with pytest.raises(TypeError):
        map_te_card(make_te_record(SPD="unknown"))


def test_whole_number_excel_float_is_accepted() -> None:
    card = map_te_card(make_te_record(OVR=82.0, SPD=84.0))

    assert card.overall == 82
    assert card.attributes["SPD"] == 84


def test_fractional_rating_is_rejected() -> None:
    with pytest.raises(TypeError):
        map_te_card(make_te_record(SPD=84.5))