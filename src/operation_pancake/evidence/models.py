"""Durable evidence-domain models with explicit lifecycle states."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

SOURCE_TYPES = (
    "PDF",
    "IMAGE",
    "SCREENSHOT",
    "WORKBOOK",
    "CSV",
    "WEB",
    "API",
    "MANUAL_OBSERVATION",
    "HISTORICAL_RESEARCH",
    "OTHER",
)
ORIGINS = (
    "CHATGPT_FILE_LIBRARY",
    "CURRENT_CHAT_UPLOAD",
    "LOCAL_REPOSITORY",
    "EXTERNAL_WEB",
    "USER_OBSERVATION",
    "DERIVED_RESEARCH",
)
EXTRACTION_STATUSES = (
    "UNPROCESSED",
    "PARTIAL",
    "COMPLETE",
    "NEEDS_REVIEW",
    "BLOCKED",
    "SUPERSEDED",
)
PROVENANCE_STATUSES = (
    "DIRECTLY_OBSERVED",
    "HISTORICALLY_RECOVERED",
    "REPOSITORY_CONFIRMED",
    "DERIVED",
    "EXTERNAL_REFERENCE",
    "UNKNOWN",
)
ISSUE_TYPES = (
    "SOURCE_EXISTS_NOT_INDEXED",
    "INDEXED_NOT_EXTRACTED",
    "PARTIALLY_EXTRACTED",
    "EXTRACTED_NOT_CANONICAL",
    "CANONICAL_MISSING_PROVENANCE",
    "POSSIBLE_DUPLICATE",
    "CONFLICTING_EVIDENCE",
    "NEEDS_VALIDATION",
    "RESEARCH_ONLY",
    "EXTERNAL_UPDATE_AVAILABLE",
)


@dataclass(frozen=True, slots=True)
class SourceRecord:
    """One source independent of any card or research record."""

    source_id: str
    source_name: str
    original_filename: str
    source_type: str
    category: str
    origin: str
    discovered_date: str | None = None
    positions: tuple[str, ...] = ()
    player_card_coverage: tuple[str, ...] = ()
    item_count: int | None = None
    extraction_status: str = "UNPROCESSED"
    extraction_remaining: str | None = None
    validation_status: str = "NEEDS_REVIEW"
    canonical_ingestion_status: str = "NOT_INGESTED"
    research_use_status: str = "NOT_USED"
    duplicate_of: str | None = None
    superseded_by: str | None = None
    notes: str | None = None
    provenance: str = "UNKNOWN"

    def __post_init__(self) -> None:
        if not self.source_id.strip() or not self.source_name.strip():
            raise ValueError("Source ID and name are required.")
        if self.source_type not in SOURCE_TYPES:
            raise ValueError(f"Unsupported source type: {self.source_type}")
        if self.origin not in ORIGINS:
            raise ValueError(f"Unsupported source origin: {self.origin}")
        if self.extraction_status not in EXTRACTION_STATUSES:
            raise ValueError(f"Unsupported extraction status: {self.extraction_status}")
        if self.provenance not in PROVENANCE_STATUSES:
            raise ValueError(f"Unsupported provenance: {self.provenance}")
        if self.extraction_status == "PARTIAL" and not self.extraction_remaining:
            raise ValueError("PARTIAL sources must state what remains unprocessed.")


@dataclass(frozen=True, slots=True)
class EvidenceLink:
    """Many-to-many link from a source to a domain or research record."""

    link_id: str
    source_id: str
    target_type: str
    target_id: str
    relationship: str
    locator: str | None = None
    notes: str | None = None


@dataclass(frozen=True, slots=True)
class FieldProvenance:
    """Evidence for one value without overwriting competing observations."""

    provenance_id: str
    target_type: str
    target_id: str
    field_name: str
    value: Any
    source_id: str
    locator: str | None
    extraction_method: str
    validation_status: str
    confidence: str
    provenance_status: str
    recorded_at: str | None = None
    version: str | None = None

    def __post_init__(self) -> None:
        if self.provenance_status not in PROVENANCE_STATUSES:
            raise ValueError(f"Unsupported provenance: {self.provenance_status}")


@dataclass(frozen=True, slots=True)
class ReconciliationItem:
    """One durable evidence migration or conflict task."""

    item_id: str
    source_id: str | None
    affected_type: str | None
    affected_id: str | None
    issue_type: str
    status: str
    priority: str
    notes: str
    resolution: str | None = None
    created_at: str | None = None
    resolved_at: str | None = None

    def __post_init__(self) -> None:
        if self.issue_type not in ISSUE_TYPES:
            raise ValueError(f"Unsupported reconciliation issue: {self.issue_type}")


@dataclass(frozen=True, slots=True)
class StagedRecord:
    """Noncanonical extracted record awaiting validation and promotion."""

    staged_id: str
    source_id: str
    external_identifier: str | None
    retrieved_at: str | None
    raw_values: dict[str, Any]
    mapped_values: dict[str, Any]
    validation_status: str
    canonical_mapping: str | None = None
    conflicts: dict[str, tuple[Any, Any]] = field(default_factory=dict)
    promoted: bool = False


class ExternalSourceAdapter:
    """Contract for future web/API sources; adapters produce staging records only."""

    source_type: str

    def stage(self, raw: dict[str, Any], retrieved_at: str) -> StagedRecord:
        raise NotImplementedError
