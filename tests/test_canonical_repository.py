"""Tests for the canonical Operation Pancake repository."""

from operation_pancake.models.player_card import PlayerCard
from operation_pancake.models.progression import ProgressionRecord
from operation_pancake.models.progression_chain import ProgressionChain
from operation_pancake.repository.canonical_repository import CanonicalRepository


def make_player(
    name: str = "Marcus Allen",
    position: str = "HB",
    overall: int = 81,
) -> PlayerCard:
    """Create a player card for canonical repository tests."""
    return PlayerCard(
        name=name,
        position=position,
        overall=overall,
        attributes={"SPD": 85, "ACC": 84},
        source="test",
    )


def make_progression() -> ProgressionChain:
    """Create a progression chain for canonical repository tests."""
    record = ProgressionRecord(
        player_name="Marcus Allen",
        position="HB",
        starting_overall=81,
        ending_overall=82,
        attribute_changes={"SPD": 5},
        source="test",
    )

    return ProgressionChain(
        player_name="Marcus Allen",
        position="HB",
        records=[record],
    )


def test_new_repository_is_empty() -> None:
    repository = CanonicalRepository()

    assert repository.player_count == 0
    assert repository.progression_count == 0
    assert len(repository) == 0


def test_add_player() -> None:
    repository = CanonicalRepository()
    player = make_player()

    repository.add_player(player)

    assert repository.player_count == 1
    assert len(repository) == 1


def test_players_by_position() -> None:
    repository = CanonicalRepository()

    repository.add_player(make_player())
    repository.add_player(
        make_player(
            name="Test Quarterback",
            position="QB",
            overall=82,
        )
    )

    assert repository.players_by_position("HB") == [
        make_player()
    ]


def test_add_progression() -> None:
    repository = CanonicalRepository()
    progression = make_progression()

    repository.add_progression(progression)

    assert repository.progression_count == 1
    assert len(repository) == 1


def test_progression_for_player() -> None:
    repository = CanonicalRepository()
    progression = make_progression()

    repository.add_progression(progression)

    assert repository.progression_for_player(
        "Marcus Allen",
        "HB",
    ) == progression


def test_missing_progression_returns_none() -> None:
    repository = CanonicalRepository()

    assert repository.progression_for_player(
        "Unknown Player",
        "QB",
    ) is None


def test_len_counts_players_and_progressions() -> None:
    repository = CanonicalRepository()

    repository.add_player(make_player())
    repository.add_progression(make_progression())

    assert len(repository) == 2