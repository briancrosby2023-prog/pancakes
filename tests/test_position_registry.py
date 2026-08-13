"""Tests for the Operation Pancake position database registry."""

from pathlib import Path

import pytest

from operation_pancake.importers.player_card_mapper import map_te_card
from operation_pancake.importers.position_registry import (
    PositionDatabaseConfig,
    PositionDatabaseRegistry,
    create_default_registry,
)


def make_config(
    position: str = "TE",
    path: str = "data/positions/te.xlsx",
    sheet_name: str = "TE_Cards",
) -> PositionDatabaseConfig:
    """Create a position database configuration for tests."""
    return PositionDatabaseConfig(
        position=position,
        workbook_path=Path(path),
        sheet_name=sheet_name,
        mapper=map_te_card,
    )


def test_config_normalizes_position() -> None:
    config = make_config(position=" te ")

    assert config.position == "TE"


def test_empty_position_is_rejected() -> None:
    with pytest.raises(ValueError):
        make_config(position="   ")


def test_empty_sheet_name_is_rejected() -> None:
    with pytest.raises(ValueError):
        make_config(sheet_name="   ")


def test_register_and_get_config() -> None:
    registry = PositionDatabaseRegistry()
    config = make_config()

    registry.register(config)

    assert registry.get("TE") == config
    assert registry.get("te") == config
    assert "TE" in registry
    assert "te" in registry
    assert len(registry) == 1


def test_duplicate_position_is_rejected() -> None:
    registry = PositionDatabaseRegistry()

    registry.register(make_config())

    with pytest.raises(ValueError):
        registry.register(make_config())


def test_require_returns_registered_config() -> None:
    registry = PositionDatabaseRegistry()
    config = make_config()

    registry.register(config)

    assert registry.require("te") == config


def test_require_unknown_position_raises_key_error() -> None:
    registry = PositionDatabaseRegistry()

    with pytest.raises(KeyError):
        registry.require("QB")


def test_positions_are_sorted() -> None:
    registry = PositionDatabaseRegistry()

    registry.register(make_config(position="TE"))
    registry.register(
        make_config(
            position="HB",
            path="data/positions/hb.xlsx",
            sheet_name="HB_Cards",
        )
    )

    assert registry.positions == ("HB", "TE")


def test_non_string_is_not_registered() -> None:
    registry = PositionDatabaseRegistry()
    registry.register(make_config())

    assert 42 not in registry


def test_default_registry_contains_te() -> None:
    registry = create_default_registry()

    config = registry.require("TE")

    assert registry.positions == ("TE",)
    assert config.position == "TE"
    assert config.workbook_path == Path("data/positions/te.xlsx")
    assert config.sheet_name == "TE_Cards"
    assert config.mapper is map_te_card


def test_default_registry_accepts_custom_data_root(
    tmp_path: Path,
) -> None:
    registry = create_default_registry(tmp_path)

    config = registry.require("TE")

    assert config.workbook_path == tmp_path / "positions" / "te.xlsx"