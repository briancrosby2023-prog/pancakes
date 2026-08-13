"""Import validated position databases into the canonical repository."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from operation_pancake.importers.workbook_importer import (
    WorkbookImporter,
    WorkbookRecord,
)
from operation_pancake.models.player_card import PlayerCard
from operation_pancake.repository.canonical_repository import CanonicalRepository

CardMapper = Callable[[WorkbookRecord], PlayerCard]


@dataclass(frozen=True, slots=True)
class PositionImportFailure:
    """One position-database row that could not be imported."""

    source_record: str
    error_type: str
    message: str


@dataclass(slots=True)
class PositionImportResult:
    """Results from importing one position database."""

    position: str
    sheet_name: str
    total_rows: int = 0
    imported_count: int = 0
    failures: list[PositionImportFailure] = field(default_factory=list)

    @property
    def failure_count(self) -> int:
        """Return number of rows rejected during import."""
        return len(self.failures)

    @property
    def is_valid(self) -> bool:
        """Return whether every source row imported successfully."""
        return self.failure_count == 0


def import_position_database(
    workbook_path: str | Path,
    sheet_name: str,
    position: str,
    mapper: CardMapper,
    repository: CanonicalRepository,
) -> PositionImportResult:
    """Import one position workbook sheet into the canonical repository."""
    importer = WorkbookImporter(workbook_path)
    records = importer.records(sheet_name)

    result = PositionImportResult(
        position=position.strip().upper(),
        sheet_name=sheet_name,
        total_rows=len(records),
    )

    for record in records:
        try:
            card = mapper(record)

            if card.position.strip().upper() != result.position:
                raise ValueError(
                    "Mapped player position does not match requested "
                    f"position: {result.position}"
                )

            repository.add_player(card)

        except (TypeError, ValueError, KeyError) as exc:
            result.failures.append(
                PositionImportFailure(
                    source_record=record.source_record,
                    error_type=type(exc).__name__,
                    message=str(exc),
                )
            )
            continue

        result.imported_count += 1

    return result