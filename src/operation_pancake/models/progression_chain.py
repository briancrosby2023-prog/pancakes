"""Progression-chain model for Operation Pancake research."""

from dataclasses import dataclass, field

from operation_pancake.models.progression import ProgressionRecord


@dataclass
class ProgressionChain:
    """Ordered collection of progression records for one player/card chain."""

    player_name: str
    position: str
    records: list[ProgressionRecord] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Validate the progression chain."""
        if not self.player_name.strip():
            raise ValueError("Player name cannot be empty.")

        if not self.position.strip():
            raise ValueError("Player position cannot be empty.")

        for record in self.records:
            self._validate_record(record)

        self._validate_sequence()

    def _validate_record(self, record: ProgressionRecord) -> None:
        """Ensure a record belongs to this progression chain."""
        if not isinstance(record, ProgressionRecord):
            raise TypeError("Progression chains may contain only ProgressionRecord objects.")

        if record.player_name != self.player_name:
            raise ValueError(
                "Progression record player name does not match progression chain."
            )

        if record.position != self.position:
            raise ValueError(
                "Progression record position does not match progression chain."
            )

    def _validate_sequence(self) -> None:
        """Ensure records form a continuous progression sequence."""
        for previous, current in zip(self.records, self.records[1:], strict=False):
            if current.starting_overall != previous.ending_overall:
                raise ValueError(
                    "Progression records must form a continuous overall sequence."
                )

    def add_record(self, record: ProgressionRecord) -> None:
        """Add a validated progression record to the chain."""
        self._validate_record(record)

        if self.records:
            previous = self.records[-1]
            if record.starting_overall != previous.ending_overall:
                raise ValueError(
                    "Progression record must begin at the previous ending overall."
                )

        self.records.append(record)

    @property
    def starting_overall(self) -> int | None:
        """Return the first overall in the chain."""
        if not self.records:
            return None
        return self.records[0].starting_overall

    @property
    def ending_overall(self) -> int | None:
        """Return the final overall in the chain."""
        if not self.records:
            return None
        return self.records[-1].ending_overall

    @property
    def overall_gain(self) -> int:
        """Return total overall gain across the chain."""
        if not self.records:
            return 0
        return self.records[-1].ending_overall - self.records[0].starting_overall

    @property
    def attribute_totals(self) -> dict[str, int]:
        """Return cumulative attribute changes across the entire chain."""
        totals: dict[str, int] = {}

        for record in self.records:
            for attribute, change in record.attribute_changes.items():
                totals[attribute] = totals.get(attribute, 0) + change

        return totals

    def attribute_total(self, attribute: str) -> int:
        """Return cumulative change for one attribute."""
        return self.attribute_totals.get(attribute, 0)

    def __len__(self) -> int:
        """Return number of progression steps in the chain."""
        return len(self.records)