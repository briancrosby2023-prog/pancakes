"""Tests for the Operation Pancake progression repository."""

import pytest

from operation_pancake.models.progression import ProgressionRecord
from operation_pancake.models.progression_chain import ProgressionChain
from operation_pancake.repository.progression_repository import ProgressionRepository


def make_chain(
    player_name: str = "Marcus Allen",
    position: str = "HB",
) -> ProgressionChain:
    """Create a progression chain for repository tests."""
    record = ProgressionRecord(
        player_name=player_name,
        position=position,
        starting_overall=81,
        ending_overall=82,
        attribute_changes={"SPD": 5},
    )

    return ProgressionChain(
        player_name=player_name,
        position=position,
        records=[record],
    )


def test_add_and_get_chain() -> None:
    repository = ProgressionRepository()
    chain = make_chain()

    repository.add(chain)

    assert repository.get("Marcus Allen", "HB") == chain


def test_get_normalizes_name_and_position() -> None:
    repository = ProgressionRepository()
    chain = make_chain()

    repository.add(chain)

    assert repository.get("  MARCUS ALLEN  ", "hb") == chain


def test_get_unknown_chain_returns_none() -> None:
    repository = ProgressionRepository()

    assert repository.get("Unknown Player", "HB") is None


def test_duplicate_chain_is_rejected() -> None:
    repository = ProgressionRepository()
    chain = make_chain()

    repository.add(chain)

    with pytest.raises(ValueError):
        repository.add(chain)


def test_all_returns_stored_chains() -> None:
    repository = ProgressionRepository()
    first = make_chain()
    second = make_chain("Marshall Faulk", "HB")

    repository.add(first)
    repository.add(second)

    assert repository.all() == [first, second]


def test_by_position_returns_matching_chains() -> None:
    repository = ProgressionRepository()
    halfback = make_chain()
    quarterback = make_chain("Test Quarterback", "QB")

    repository.add(halfback)
    repository.add(quarterback)

    assert repository.by_position("hb") == [halfback]


def test_len_returns_number_of_chains() -> None:
    repository = ProgressionRepository()

    repository.add(make_chain())
    repository.add(make_chain("Marshall Faulk", "HB"))

    assert len(repository) == 2