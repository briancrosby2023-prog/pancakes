"""Map canonical workbook rows into validated Operation Pancake player cards."""

from __future__ import annotations

from typing import Any

from operation_pancake.importers.workbook_importer import WorkbookRecord
from operation_pancake.models.player_card import PlayerCard

IDENTITY_FIELDS = {
    "Card_ID",
    "QB_ID",
    "Player",
    "OVR",
    "Program",
    "Archetype",
    "Source_ID",
    "Source_Page",
    "Source_Locator",
    "Population_Scope",
    "Model_Role",
    "Unique_Profile_Key",
    "Duplicate_Note",
    "Frozen_Score_Check",
    "Frozen_Score_Formula",
    "Formula_Delta",
    "Validation_Status",
    "Notes",
}

QB_ATTRIBUTE_FIELDS = {
    "SPD",
    "ACC",
    "AGI",
    "AWR",
    "STR",
    "TGH",
    "THP",
    "TAC",
    "SAC",
    "MAC",
    "DAC",
    "RUN",
    "TUP",
    "PAC",
    "BSK",
}

QB_METADATA_FIELDS = {
    "QB_ID": "qb_id",
    "Source_ID": "source_id",
    "Source_Locator": "source_locator",
    "Population_Scope": "population_scope",
    "Model_Role": "model_role",
    "Unique_Profile_Key": "unique_profile_key",
    "Duplicate_Note": "duplicate_note",
    "Frozen_Score_Check": "frozen_score_check",
    "Frozen_Score_Formula": "frozen_score_formula",
    "Formula_Delta": "formula_delta",
}


def _optional_text(value: Any) -> str | None:
    """Normalize optional workbook text without inventing missing values."""
    if value is None:
        return None

    text = str(value).strip()
    return text or None


def _required_text(value: Any, field_name: str) -> str:
    """Return required workbook text or reject the record."""
    text = _optional_text(value)

    if text is None:
        raise ValueError(f"Required workbook field is missing: {field_name}")

    return text


def _rating(value: Any, field_name: str) -> int:
    """Convert a workbook rating to an integer without silently guessing."""
    if isinstance(value, bool):
        raise TypeError(f"{field_name} must be an integer rating.")

    if isinstance(value, int):
        rating = value
    elif isinstance(value, float) and value.is_integer():
        rating = int(value)
    else:
        raise TypeError(f"{field_name} must be an integer rating.")

    if not 0 <= rating <= 99:
        raise ValueError(f"{field_name} must be between 0 and 99.")

    return rating


def map_te_card(record: WorkbookRecord) -> PlayerCard:
    """Map one canonical TE_Cards workbook row into a PlayerCard."""
    values = record.values

    name = _required_text(values.get("Player"), "Player")
    overall = _rating(values.get("OVR"), "OVR")

    attributes: dict[str, int] = {}

    for field_name, value in values.items():
        if field_name in IDENTITY_FIELDS or value is None:
            continue

        attributes[field_name.strip().upper()] = _rating(value, field_name)

    source_id = _optional_text(values.get("Source_ID"))
    source_page = _optional_text(values.get("Source_Page"))

    source_parts = [
        part
        for part in (source_id, source_page)
        if part is not None
    ]

    source = " | ".join(source_parts) if source_parts else None

    metadata = {
        "card_id": _optional_text(values.get("Card_ID")),
        "workbook_sheet": record.sheet_name,
        "workbook_row": record.row_number,
    }

    return PlayerCard(
        name=name,
        position="TE",
        overall=overall,
        archetype=_optional_text(values.get("Archetype")),
        program=_optional_text(values.get("Program")),
        attributes=attributes,
        source=source,
        source_record=record.source_record,
        confidence=_optional_text(values.get("Validation_Status")) or "unverified",
        notes=_optional_text(values.get("Notes")),
        metadata=metadata,
    )


def map_qb_card(record: WorkbookRecord) -> PlayerCard:
    """Map one canonical QB_Cards workbook row into a PlayerCard."""
    values = record.values

    qb_id = _required_text(values.get("QB_ID"), "QB_ID")
    name = _required_text(values.get("Player"), "Player")
    overall = _rating(values.get("OVR"), "OVR")

    attributes: dict[str, int] = {}

    for field_name in QB_ATTRIBUTE_FIELDS:
        value = values.get(field_name)
        if value is None:
            continue

        attributes[field_name] = _rating(value, field_name)

    source_id = _optional_text(values.get("Source_ID"))
    source_locator = _optional_text(values.get("Source_Locator"))

    source_parts = [
        part
        for part in (source_id, source_locator)
        if part is not None
    ]

    source = " | ".join(source_parts) if source_parts else None

    metadata = {
        metadata_name: values.get(workbook_name)
        for workbook_name, metadata_name in QB_METADATA_FIELDS.items()
    }
    metadata.update(
        {
            "qb_id": qb_id,
            "workbook_sheet": record.sheet_name,
            "workbook_row": record.row_number,
        }
    )

    return PlayerCard(
        name=name,
        position="QB",
        overall=overall,
        archetype=_optional_text(values.get("Archetype")),
        program=_optional_text(values.get("Program")),
        attributes=attributes,
        source=source,
        source_record=record.source_record,
        confidence=_optional_text(values.get("Validation_Status")) or "unverified",
        notes=_optional_text(values.get("Notes")),
        metadata=metadata,
    )
