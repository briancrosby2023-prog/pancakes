"""Tests for the Operation Pancake player repository."""

import pytest

from operation_pancake.models.player_card import PlayerCard
from operation_pancake.repository.player_repository import PlayerRepository


def make_player(
    name: str = "Marcus Allen",
    position: str = "HB",
    overall: int = 81,
    program: str | None = None,
    metadata: dict[str, object] | None = None,
) -> PlayerCard:
    """Create a player card for repository tests."""
    return PlayerCard(
        name=name,
        position=position,
        overall=overall,
        program=program,
        metadata=metadata or {},
    )


def test_add_and_get_player() -> None:
    repository = PlayerRepository()
    player = make_player()

    repository.add(player)

    assert repository.get("Marcus Allen", "HB", 81) == player


def test_get_normalizes_name_and_position() -> None:
    repository = PlayerRepository()
    player = make_player()

    repository.add(player)

    assert repository.get("  MARCUS ALLEN  ", "hb", 81) == player


def test_get_unknown_player_returns_none() -> None:
    repository = PlayerRepository()

    assert repository.get("Unknown Player", "HB", 81) is None


def test_duplicate_player_is_rejected() -> None:
    repository = PlayerRepository()
    player = make_player()
    repository.add(player)

    with pytest.raises(ValueError):
        repository.add(player)


def test_same_player_overall_with_different_programs_is_preserved() -> None:
    repository = PlayerRepository()
    core = make_player(program="Core Rare")
    platinum = make_player(program="Platinum Rare")

    repository.add(core)
    repository.add(platinum)

    assert len(repository) == 2
    assert repository.get(core.name, core.position, core.overall, "Core Rare") == core
    assert repository.get(core.name, core.position, core.overall, "Platinum Rare") == platinum


def test_ambiguous_player_lookup_requires_program() -> None:
    repository = PlayerRepository()
    core = make_player(program="Core Rare")
    repository.add(core)
    repository.add(make_player(program="Platinum Rare"))

    with pytest.raises(ValueError, match="specify the program"):
        repository.get(core.name, core.position, core.overall)


def test_all_returns_stored_players() -> None:
    repository = PlayerRepository()
    player_one = make_player()
    player_two = make_player(name="Marshall Faulk", overall=82)

    repository.add(player_one)
    repository.add(player_two)

    assert repository.all() == [player_one, player_two]


def test_by_position_returns_matching_players() -> None:
    repository = PlayerRepository()
    halfback = make_player()
    quarterback = make_player(name="Test Quarterback", position="QB", overall=82)

    repository.add(halfback)
    repository.add(quarterback)

    assert repository.by_position("hb") == [halfback]


def test_players_can_be_queried_by_metadata() -> None:
    repository = PlayerRepository()
    player = make_player(metadata={"model_role": "DEVELOPMENT"})
    repository.add(player)

    assert repository.by_metadata("model_role", "DEVELOPMENT") == [player]


def test_duplicate_qb_id_is_rejected_without_rejecting_profile_duplicates() -> None:
    repository = PlayerRepository()
    first = make_player(
        position="QB",
        program="Core Rare",
        metadata={"qb_id": "QB-0001", "unique_profile_key": "shared"},
    )
    profile_duplicate = make_player(
        position="QB",
        program="Platinum Rare",
        metadata={"qb_id": "QB-0002", "unique_profile_key": "shared"},
    )
    duplicate_id = make_player(
        name="Different Player",
        position="QB",
        program="Legends",
        metadata={"qb_id": "QB-0001", "unique_profile_key": "different"},
    )

    repository.add(first)
    repository.add(profile_duplicate)

    with pytest.raises(ValueError, match="QB_ID already exists"):
        repository.add(duplicate_id)

    assert len(repository) == 2


def test_len_returns_number_of_players() -> None:
    repository = PlayerRepository()
    repository.add(make_player())
    repository.add(make_player(name="Marshall Faulk", overall=82))

    assert len(repository) == 2
