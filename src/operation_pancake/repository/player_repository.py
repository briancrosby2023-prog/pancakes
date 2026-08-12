"""Repository for storing and retrieving Operation Pancake player cards."""

from operation_pancake.models.player_card import PlayerCard


class PlayerRepository:
    """In-memory repository for validated player cards."""

    def __init__(self) -> None:
        self._players: dict[str, PlayerCard] = {}

    @staticmethod
    def _key(player: PlayerCard) -> str:
        """Create a stable key for a player card."""
        return f"{player.name.strip().lower()}|{player.position.strip().upper()}|{player.overall}"

    def add(self, player: PlayerCard) -> None:
        """Add a player card to the repository."""
        key = self._key(player)

        if key in self._players:
            raise ValueError("Player card already exists in repository.")

        self._players[key] = player

    def get(self, name: str, position: str, overall: int) -> PlayerCard | None:
        """Return a player card matching name, position, and overall."""
        key = f"{name.strip().lower()}|{position.strip().upper()}|{overall}"
        return self._players.get(key)

    def all(self) -> list[PlayerCard]:
        """Return all stored player cards."""
        return list(self._players.values())

    def by_position(self, position: str) -> list[PlayerCard]:
        """Return all player cards at a position."""
        normalized_position = position.strip().upper()
        return [
            player
            for player in self._players.values()
            if player.position.strip().upper() == normalized_position
        ]

    def __len__(self) -> int:
        """Return the number of stored player cards."""
        return len(self._players)