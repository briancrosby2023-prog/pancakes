"""Tests for the canonical Operation Pancake player-card model."""

import pytest

from operation_pancake.models.player_card import PlayerCard


def test_create_valid_player_card() -> None:
    card = PlayerCard(
        name="Test Player",
        position="QB",
        overall=85,
        archetype="Field General",
        program="Test Program",
        attributes={
            "SPD": 82,
            "THP": 88,
            "SAC": 86,
            "MAC": 84,
            "DAC": 81,
        },
        source="test",
        confidence="validated",
    )

    assert card.name == "Test Player"
    assert card.position == "QB"
    assert card.overall == 85
    assert card.attributes["THP"] == 88


def test_reject_empty_player_name() -> None:
    with pytest.raises(ValueError):
        PlayerCard(
            name="",
            position="QB",
            overall=85,
        )


def test_reject_empty_position() -> None:
    with pytest.raises(ValueError):
        PlayerCard(
            name="Test Player",
            position="",
            overall=85,
        )


def test_reject_invalid_overall() -> None:
    with pytest.raises(ValueError):
        PlayerCard(
            name="Test Player",
            position="QB",
            overall=100,
        )


def test_reject_non_integer_attribute() -> None:
    with pytest.raises(TypeError):
        PlayerCard(
            name="Test Player",
            position="QB",
            overall=85,
            attributes={"SPD": 85.5},
        )


def test_reject_attribute_above_99() -> None:
    with pytest.raises(ValueError):
        PlayerCard(
            name="Test Player",
            position="QB",
            overall=85,
            attributes={"SPD": 100},
        )