"""Tests for Operation Pancake progression chains."""

import pytest

from operation_pancake.models.progression import ProgressionRecord
from operation_pancake.models.progression_chain import ProgressionChain


def make_record(
    start: int,
    end: int,
    changes: dict[str, int],
) -> ProgressionRecord:
    """Create a progression record for chain tests."""
    return ProgressionRecord(
        player_name="Marcus Allen",
        position="HB",
        starting_overall=start,
        ending_overall=end,
        attribute_changes=changes,
    )


def test_empty_chain() -> None:
    chain = ProgressionChain(
        player_name="Marcus Allen",
        position="HB",
    )

    assert len(chain) == 0
    assert chain.starting_overall is None
    assert chain.ending_overall is None
    assert chain.overall_gain == 0
    assert chain.attribute_totals == {}


def test_single_record_chain() -> None:
    record = make_record(
        81,
        82,
        {"AWR": 7, "SPD": 5, "ACC": 7},
    )

    chain = ProgressionChain(
        player_name="Marcus Allen",
        position="HB",
        records=[record],
    )

    assert len(chain) == 1
    assert chain.starting_overall == 81
    assert chain.ending_overall == 82
    assert chain.overall_gain == 1
    assert chain.attribute_total("SPD") == 5


def test_multi_step_chain_totals_attributes() -> None:
    first = make_record(
        81,
        82,
        {"SPD": 5, "ACC": 7, "AWR": 7},
    )
    second = make_record(
        82,
        83,
        {"SPD": 2, "ACC": 1, "AWR": 3},
    )

    chain = ProgressionChain(
        player_name="Marcus Allen",
        position="HB",
        records=[first, second],
    )

    assert len(chain) == 2
    assert chain.starting_overall == 81
    assert chain.ending_overall == 83
    assert chain.overall_gain == 2
    assert chain.attribute_totals == {
        "SPD": 7,
        "ACC": 8,
        "AWR": 10,
    }


def test_add_record() -> None:
    chain = ProgressionChain(
        player_name="Marcus Allen",
        position="HB",
    )

    chain.add_record(
        make_record(
            81,
            82,
            {"SPD": 5},
        )
    )
    chain.add_record(
        make_record(
            82,
            83,
            {"SPD": 2},
        )
    )

    assert len(chain) == 2
    assert chain.ending_overall == 83
    assert chain.attribute_total("SPD") == 7


def test_reject_wrong_player() -> None:
    record = ProgressionRecord(
        player_name="Marshall Faulk",
        position="HB",
        starting_overall=81,
        ending_overall=82,
        attribute_changes={"SPD": 6},
    )

    with pytest.raises(ValueError):
        ProgressionChain(
            player_name="Marcus Allen",
            position="HB",
            records=[record],
        )


def test_reject_wrong_position() -> None:
    record = ProgressionRecord(
        player_name="Marcus Allen",
        position="WR",
        starting_overall=81,
        ending_overall=82,
        attribute_changes={"SPD": 5},
    )

    with pytest.raises(ValueError):
        ProgressionChain(
            player_name="Marcus Allen",
            position="HB",
            records=[record],
        )


def test_reject_broken_sequence() -> None:
    first = make_record(
        81,
        82,
        {"SPD": 5},
    )
    second = make_record(
        83,
        84,
        {"SPD": 2},
    )

    with pytest.raises(ValueError):
        ProgressionChain(
            player_name="Marcus Allen",
            position="HB",
            records=[first, second],
        )


def test_reject_broken_sequence_when_adding() -> None:
    chain = ProgressionChain(
        player_name="Marcus Allen",
        position="HB",
        records=[
            make_record(
                81,
                82,
                {"SPD": 5},
            )
        ],
    )

    with pytest.raises(ValueError):
        chain.add_record(
            make_record(
                83,
                84,
                {"SPD": 2},
            )
        )


def test_unknown_attribute_total_is_zero() -> None:
    chain = ProgressionChain(
        player_name="Marcus Allen",
        position="HB",
        records=[
            make_record(
                81,
                82,
                {"SPD": 5},
            )
        ],
    )

    assert chain.attribute_total("THP") == 0