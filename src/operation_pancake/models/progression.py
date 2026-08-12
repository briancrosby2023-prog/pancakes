"""Progression research model for Operation Pancake."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class ProgressionRecord:
    """A validated player-card progression or upgrade observation."""

    player_name: str
    position: str
    starting_overall: int
    ending_overall: int

    attribute_changes: dict[str, int] = field(default_factory=dict)

    source: str | None = None
    source_record: str | None = None
    confidence: str = "validated"
    notes: str | None = None

    def __post_init__(self) -> None:
        """Reject invalid progression research records."""
        if not self.player_name.strip():
            raise ValueError("Player name cannot be empty.")

        if not self.position.strip():
            raise ValueError("Player position cannot be empty.")

        if not 0 <= self.starting_overall <= 99:
            raise ValueError("Starting overall must be between 0 and 99.")

        if not 0 <= self.ending_overall <= 99:
            raise ValueError("Ending overall must be between 0 and 99.")

        if self.ending_overall < self.starting_overall:
            raise ValueError("Ending overall cannot be below starting overall.")

        for attribute, change in self.attribute_changes.items():
            if not attribute.strip():
                raise ValueError("Attribute names cannot be empty.")

            if not isinstance(change, int):
                raise TypeError(
                    f"Attribute change {attribute!r} must be an integer."
                )