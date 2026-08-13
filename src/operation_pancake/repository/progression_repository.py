"""Repository for storing and retrieving Operation Pancake progression chains."""

from operation_pancake.models.progression_chain import ProgressionChain


class ProgressionRepository:
    """In-memory repository for validated progression chains."""

    def __init__(self) -> None:
        self._chains: dict[str, ProgressionChain] = {}

    @staticmethod
    def _key(player_name: str, position: str) -> str:
        """Create a stable key for a player's progression chain."""
        return f"{player_name.strip().lower()}|{position.strip().upper()}"

    def add(self, chain: ProgressionChain) -> None:
        """Add a progression chain to the repository."""
        key = self._key(chain.player_name, chain.position)

        if key in self._chains:
            raise ValueError("Progression chain already exists in repository.")

        self._chains[key] = chain

    def get(self, player_name: str, position: str) -> ProgressionChain | None:
        """Return a progression chain for a player."""
        key = self._key(player_name, position)
        return self._chains.get(key)

    def all(self) -> list[ProgressionChain]:
        """Return all stored progression chains."""
        return list(self._chains.values())

    def by_position(self, position: str) -> list[ProgressionChain]:
        """Return all progression chains at a position."""
        normalized_position = position.strip().upper()
        return [
            chain
            for chain in self._chains.values()
            if chain.position.strip().upper() == normalized_position
        ]

    def __len__(self) -> int:
        """Return the number of stored progression chains."""
        return len(self._chains)