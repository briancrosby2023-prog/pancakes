"""Tests for the Operation Pancake progression-record model."""

import pytest

from operation_pancake.models.progression import ProgressionRecord


def test_create_valid_progression_record() -> None:
    record = ProgressionRecord(
        player_name="Marcus Allen",
        position="HB",
        starting_overall=81,
        ending_overall=82,
        attribute_changes={"AWR": 7, "SPD": 5, "ACC": 7},
        source="Operation Pancake progression research",
    )

    assert record.player_name == "Marcus Allen"
    assert record.position == "HB"
    assert record.starting_overall == 81
    assert record.ending_overall == 82
    assert record.attribute_changes["SPD"] == 5


def test_reject_empty_player_name() -> None:
    with pytest.raises(ValueError):
        ProgressionRecord(
            player_name="",
            position="HB",
            starting_overall=81,
            ending_overall=82,
        )


def test_reject_empty_position() -> None:
    with pytest.raises(ValueError):
        ProgressionRecord(
            player_name="Test Player",
            position="",
            starting_overall=81,
            ending_overall=82,
        )


def test_reject_invalid_starting_overall() -> None:
    with pytest.raises(ValueError):
        ProgressionRecord(
            player_name="Test Player",
            position="HB",
            starting_overall=100,
            ending_overall=100,
        )


def test_reject_invalid_ending_overall() -> None:
    with pytest.raises(ValueError):
        ProgressionRecord(
            player_name="Test Player",
            position="HB",
            starting_overall=81,
            ending_overall=100,
        )


def test_reject_ending_overall_below_starting_overall() -> None:
    with pytest.raises(ValueError):
        ProgressionRecord(
            player_name="Test Player",
            position="HB",
            starting_overall=82,
            ending_overall=81,
        )


def test_reject_non_integer_attribute_change() -> None:
    with pytest.raises(TypeError):
        ProgressionRecord(
            player_name="Test Player",
            position="HB",
            starting_overall=81,
            ending_overall=82,
            attribute_changes={"SPD": 5.5},
        )