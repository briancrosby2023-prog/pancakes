"""Tests for the Operation Pancake player repository."""

import pytest

from operation_pancake.models.player_card import PlayerCard
from operation_pancake.repository.player_repository import PlayerRepository


def make_player(
    name: str = "Marcus Allen",
    position: str = "HB",
    overall: int = 81,
) -> PlayerCard:
    """Create a player card for repository tests."""
    return PlayerCard(
        name=name,
        position=position,
        overall=overall,
    )


def test_add_and_get_player() -> None:
    repository = PlayerRepository()
    player = make_player()

    repository.add(player)

    result = repository.get("Marcus Allen", "HB", 81)

    assert result == player


def test_get_normalizes_name_and_position() -> None:
    repository = PlayerRepository()
    player = make_player()

    repository.add(player)

    result = repository.get("  MARCUS ALLEN  ", "hb", 81)

    assert result == player


def test_get_unknown_player_returns_none() -> None:
    repository = PlayerRepository()

    assert repository.get("Unknown Player", "HB", 81) is None


def test_duplicate_player_is_rejected() -> None:
    repository = PlayerRepository()
    player = make_player()

    repository.add(player)

    with pytest.raises(ValueError):
        repository.add(player)


def test_all_returns_stored_players() -> None:
    repository = PlayerRepository()
    player_one = make_player()
    player_two = make_player(
        name="Marshall Faulk",
        overall=82,
    )

    repository.add(player_one)
    repository.add(player_two)

    assert repository.all() == [player_one, player_two]


def test_by_position_returns_matching_players() -> None:
    repository = PlayerRepository()
    halfback = make_player()
    quarterback = make_player(
        name="Test Quarterback",
        position="QB",
        overall=82,
    )

    repository.add(halfback)
    repository.add(quarterback)

    assert repository.by_position("hb") == [halfback]


def test_len_returns_number_of_players() -> None:
    repository = PlayerRepository()

    repository.add(make_player())
    repository.add(
        make_player(
            name="Marshall Faulk",
            overall=82,
        )
    )

    assert len(repository) == 2