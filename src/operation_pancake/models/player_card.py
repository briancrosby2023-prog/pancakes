"""Canonical player-card model for Operation Pancake."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class PlayerCard:
    """A validated real player card from the canonical research dataset."""

    name: str
    position: str
    overall: int
    archetype: str | None = None
    program: str | None = None

    attributes: dict[str, int] = field(default_factory=dict)

    source: str | None = None
    source_record: str | None = None
    confidence: str = "validated"

    notes: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Reject invalid production player records."""
        if not self.name.strip():
            raise ValueError("Player name cannot be empty.")

        if not self.position.strip():
            raise ValueError("Player position cannot be empty.")

        if not 0 <= self.overall <= 99:
            raise ValueError("Overall must be between 0 and 99.")

        for attribute, value in self.attributes.items():
            if not attribute.strip():
                raise ValueError("Attribute names cannot be empty.")

            if not isinstance(value, int):
                raise TypeError(
                    f"Attribute {attribute!r} must be an integer; "
                    f"received {type(value).__name__}."
                )

            if not 0 <= value <= 99:
                raise ValueError(
                    f"Attribute {attribute!r} must be between 0 and 99; "
                    f"received {value}."
                )

    @property
    def card_key(self) -> tuple[str, str, int, str | None]:
        """Stable identity used when detecting duplicate card records."""
        return (
            self.name.strip().casefold(),
            self.position.strip().upper(),
            self.overall,
            self.program.strip().casefold() if self.program else None,
        )

    def attribute(self, name: str) -> int | None:
        """Return an attribute value without guessing missing data."""
        return self.attributes.get(name.strip().upper())