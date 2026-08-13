"""Validation reporting for canonical Operation Pancake workbook imports."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from operation_pancake.importers.player_card_mapper import map_te_card
from operation_pancake.importers.workbook_importer import WorkbookImporter
from operation_pancake.models.player_card import PlayerCard


@dataclass(frozen=True, slots=True)
class ImportFailure:
    """One workbook row that could not be imported."""

    source_record: str
    error_type: str
    message: str


@dataclass(slots=True)
class ImportValidationReport:
    """Results from validating one canonical workbook sheet."""

    sheet_name: str
    total_rows: int = 0
    imported_cards: list[PlayerCard] = field(default_factory=list)
    failures: list[ImportFailure] = field(default_factory=list)
    duplicate_card_ids: set[str] = field(default_factory=set)

    @property
    def imported_count(self) -> int:
        """Return number of successfully imported cards."""
        return len(self.imported_cards)

    @property
    def failure_count(self) -> int:
        """Return number of rejected workbook rows."""
        return len(self.failures)

    @property
    def is_valid(self) -> bool:
        """Return whether every row imported with no duplicate card IDs."""
        return not self.failures and not self.duplicate_card_ids


def validate_te_cards(
    workbook_path: str | Path,
    sheet_name: str = "TE_Cards",
) -> ImportValidationReport:
    """Validate canonical TE cards without modifying the workbook."""
    importer = WorkbookImporter(workbook_path)
    records = importer.records(sheet_name)

    report = ImportValidationReport(
        sheet_name=sheet_name,
        total_rows=len(records),
    )

    seen_card_ids: set[str] = set()

    for record in records:
        try:
            card = map_te_card(record)
        except (TypeError, ValueError, KeyError) as exc:
            report.failures.append(
                ImportFailure(
                    source_record=record.source_record,
                    error_type=type(exc).__name__,
                    message=str(exc),
                )
            )
            continue

        card_id = card.metadata.get("card_id")

        if isinstance(card_id, str) and card_id:
            if card_id in seen_card_ids:
                report.duplicate_card_ids.add(card_id)
            else:
                seen_card_ids.add(card_id)

        report.imported_cards.append(card)

    return report