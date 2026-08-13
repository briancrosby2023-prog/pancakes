"""Canonical repository for validated Operation Pancake research data."""

from __future__ import annotations

from operation_pancake.models.player_card import PlayerCard
from operation_pancake.models.progression_chain import ProgressionChain
from operation_pancake.repository.player_repository import PlayerRepository
from operation_pancake.repository.progression_repository import ProgressionRepository


class CanonicalRepository:
    """Central repository for validated canonical Operation Pancake data."""

    def __init__(self) -> None:
        self.players = PlayerRepository()
        self.progressions = ProgressionRepository()

    def add_player(self, player: PlayerCard) -> None:
        """Add a validated player card to the canonical repository."""
        self.players.add(player)

    def add_progression(self, progression: ProgressionChain) -> None:
        """Add a validated progression chain to the canonical repository."""
        self.progressions.add(progression)

    def players_by_position(self, position: str) -> list[PlayerCard]:
        """Return canonical players matching a position."""
        return self.players.by_position(position)

    def progression_for_player(
        self,
        player_name: str,
        position: str,
    ) -> ProgressionChain | None:
        """Return the progression chain for a player, if one exists."""
        return self.progressions.get(player_name, position)

    @property
    def player_count(self) -> int:
        """Return the number of canonical player cards."""
        return len(self.players)

    @property
    def progression_count(self) -> int:
        """Return the number of canonical progression chains."""
        return len(self.progressions)

    def __len__(self) -> int:
        """Return total number of canonical records."""
        return self.player_count + self.progression_count