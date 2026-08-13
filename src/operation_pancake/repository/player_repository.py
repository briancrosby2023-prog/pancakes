"""Repository for storing and retrieving Operation Pancake player cards."""

from operation_pancake.models.player_card import PlayerCard


class PlayerRepository:
    """In-memory repository for validated player cards."""

    def __init__(self) -> None:
        self._players: dict[tuple[str, str, int, str | None], PlayerCard] = {}

    @staticmethod
    def _key(player: PlayerCard) -> tuple[str, str, int, str | None]:
        """Create a stable key for a player card."""
        return player.card_key

    def add(self, player: PlayerCard) -> None:
        """Add a player card to the repository."""
        key = self._key(player)
        qb_id = player.metadata.get("qb_id")

        if key in self._players:
            raise ValueError("Player card already exists in repository.")

        if qb_id is not None and self.by_metadata("qb_id", qb_id):
            raise ValueError(f"QB_ID already exists in repository: {qb_id}")

        self._players[key] = player

    def get(
        self,
        name: str,
        position: str,
        overall: int,
        program: str | None = None,
    ) -> PlayerCard | None:
        """Return a player card matching name, position, and overall."""
        normalized_name = name.strip().casefold()
        normalized_position = position.strip().upper()
        normalized_program = program.strip().casefold() if program else None

        if program is not None:
            return self._players.get(
                (normalized_name, normalized_position, overall, normalized_program)
            )

        matches = [
            player
            for key, player in self._players.items()
            if key[:3] == (normalized_name, normalized_position, overall)
        ]

        if len(matches) > 1:
            raise ValueError(
                "Multiple player cards match; specify the program."
            )

        return matches[0] if matches else None

    def by_metadata(self, field_name: str, value: object) -> list[PlayerCard]:
        """Return player cards whose preserved metadata field matches a value."""
        return [
            player
            for player in self._players.values()
            if player.metadata.get(field_name) == value
        ]

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
