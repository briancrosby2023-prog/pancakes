"""Registry of position databases available to Operation Pancake."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from operation_pancake.importers.player_card_mapper import map_te_card
from operation_pancake.importers.position_database_importer import CardMapper


@dataclass(frozen=True, slots=True)
class PositionDatabaseConfig:
    """Configuration required to import one position database."""

    position: str
    workbook_path: Path
    sheet_name: str
    mapper: CardMapper

    def __post_init__(self) -> None:
        normalized_position = self.position.strip().upper()

        if not normalized_position:
            raise ValueError("Position cannot be empty.")

        if not self.sheet_name.strip():
            raise ValueError("Sheet name cannot be empty.")

        object.__setattr__(self, "position", normalized_position)


class PositionDatabaseRegistry:
    """Registry of configured Operation Pancake position databases."""

    def __init__(self) -> None:
        self._configs: dict[str, PositionDatabaseConfig] = {}

    def register(self, config: PositionDatabaseConfig) -> None:
        """Register one position database configuration."""
        position = config.position

        if position in self._configs:
            raise ValueError(
                f"Position database already registered: {position}"
            )

        self._configs[position] = config

    def get(self, position: str) -> PositionDatabaseConfig | None:
        """Return configuration for a position, if registered."""
        return self._configs.get(position.strip().upper())

    def require(self, position: str) -> PositionDatabaseConfig:
        """Return configuration for a position or raise an error."""
        normalized_position = position.strip().upper()
        config = self.get(normalized_position)

        if config is None:
            raise KeyError(
                f"No position database registered: {normalized_position}"
            )

        return config

    @property
    def positions(self) -> tuple[str, ...]:
        """Return registered positions in sorted order."""
        return tuple(sorted(self._configs))

    def __contains__(self, position: object) -> bool:
        """Return whether a position is registered."""
        if not isinstance(position, str):
            return False

        return position.strip().upper() in self._configs

    def __len__(self) -> int:
        """Return number of registered position databases."""
        return len(self._configs)


def create_default_registry(
    data_root: str | Path = "data",
) -> PositionDatabaseRegistry:
    """Create the registry for position databases currently supported."""
    root = Path(data_root)

    registry = PositionDatabaseRegistry()

    registry.register(
        PositionDatabaseConfig(
            position="TE",
            workbook_path=root / "positions" / "te.xlsx",
            sheet_name="TE_Cards",
            mapper=map_te_card,
        )
    )

    return registry