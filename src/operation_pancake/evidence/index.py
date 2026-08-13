"""In-memory evidence index with structured search and reverse lookup."""

from __future__ import annotations

import re
from dataclasses import asdict
from typing import Any, Iterable

from operation_pancake.evidence.models import (
    EvidenceLink,
    FieldProvenance,
    ReconciliationItem,
    SourceRecord,
    StagedRecord,
)


class EvidenceIndex:
    """Repository-side source catalog and reconciliation service."""

    def __init__(self) -> None:
        self.sources: dict[str, SourceRecord] = {}
        self.records: dict[tuple[str, str], dict[str, Any]] = {}
        self.links: dict[str, EvidenceLink] = {}
        self.field_provenance: dict[str, FieldProvenance] = {}
        self.queue: dict[str, ReconciliationItem] = {}
        self.staged: dict[str, StagedRecord] = {}

    def add_source(self, source: SourceRecord) -> None:
        if source.source_id in self.sources:
            raise ValueError(f"Source ID already exists: {source.source_id}")
        self.sources[source.source_id] = source

    def add_record(self, target_type: str, target_id: str, values: dict[str, Any]) -> None:
        key = (target_type, target_id)
        if key in self.records:
            raise ValueError(f"Record already exists: {target_type}/{target_id}")
        self.records[key] = dict(values)

    def add_link(self, link: EvidenceLink) -> None:
        if link.link_id in self.links:
            raise ValueError(f"Evidence link already exists: {link.link_id}")
        if link.source_id not in self.sources:
            raise KeyError(f"Unknown source: {link.source_id}")
        self.links[link.link_id] = link

    def add_field_provenance(self, item: FieldProvenance) -> None:
        if item.provenance_id in self.field_provenance:
            raise ValueError(f"Field provenance already exists: {item.provenance_id}")
        if item.source_id not in self.sources:
            raise KeyError(f"Unknown source: {item.source_id}")
        self.field_provenance[item.provenance_id] = item

    def add_queue_item(self, item: ReconciliationItem) -> None:
        if item.item_id in self.queue:
            raise ValueError(f"Queue item already exists: {item.item_id}")
        self.queue[item.item_id] = item

    def stage(self, record: StagedRecord) -> None:
        if record.staged_id in self.staged:
            raise ValueError(f"Staged record already exists: {record.staged_id}")
        if record.source_id not in self.sources:
            raise KeyError(f"Unknown source: {record.source_id}")
        if record.promoted:
            raise ValueError("New staged records cannot already be canonically promoted.")
        self.staged[record.staged_id] = record

    @staticmethod
    def conflicts(
        staged_values: dict[str, Any], canonical_values: dict[str, Any]
    ) -> dict[str, tuple[Any, Any]]:
        return {
            field: (canonical_values[field], value)
            for field, value in staged_values.items()
            if field in canonical_values and canonical_values[field] != value
        }

    def search(self, query: str = "", **filters: object) -> dict[str, list[dict[str, Any]]]:
        """Search structured sources, records, links, and unresolved queue items."""
        needles = re.findall(r"[a-z0-9]+", query.casefold())

        def matches(payload: dict[str, Any]) -> bool:
            haystack = " ".join(str(value) for value in payload.values()).casefold()
            if needles and not all(needle in haystack for needle in needles):
                return False
            for field, expected in filters.items():
                lookup_field = (
                    "positions" if field == "position" and "positions" in payload else field
                )
                actual = payload.get(lookup_field)
                if isinstance(actual, (list, tuple)):
                    if str(expected).casefold() not in {str(value).casefold() for value in actual}:
                        return False
                elif str(actual).casefold() != str(expected).casefold():
                    return False
            return True

        sources = [asdict(item) for item in self.sources.values()]
        records = [
            {"target_type": kind, "target_id": target_id, **values}
            for (kind, target_id), values in self.records.items()
        ]
        queue = [asdict(item) for item in self.queue.values()]
        return {
            "sources": sorted(
                (item for item in sources if matches(item)), key=lambda x: x["source_id"]
            ),
            "records": sorted(
                (item for item in records if matches(item)),
                key=lambda x: (x["target_type"], x["target_id"]),
            ),
            "reconciliation": sorted(
                (item for item in queue if matches(item)), key=lambda x: x["item_id"]
            ),
        }

    def source_impact(self, source_id: str) -> dict[str, Any]:
        source = self.sources[source_id]
        links = sorted(
            (asdict(link) for link in self.links.values() if link.source_id == source_id),
            key=lambda item: item["link_id"],
        )
        research_ids = sorted(
            link["target_id"] for link in links if link["target_type"] == "research_artifact"
        )
        return {
            "source": asdict(source),
            "links": links,
            "research_artifacts": research_ids,
            "unprocessed": source.extraction_remaining,
            "queue": sorted(
                (asdict(item) for item in self.queue.values() if item.source_id == source_id),
                key=lambda item: item["item_id"],
            ),
        }

    def record_provenance(self, target_type: str, target_id: str) -> dict[str, Any]:
        key = (target_type, target_id)
        if key not in self.records:
            raise KeyError(f"Unknown record: {target_type}/{target_id}")
        links = sorted(
            (
                asdict(link)
                for link in self.links.values()
                if link.target_type == target_type and link.target_id == target_id
            ),
            key=lambda item: item["link_id"],
        )
        fields = sorted(
            (
                asdict(item)
                for item in self.field_provenance.values()
                if item.target_type == target_type and item.target_id == target_id
            ),
            key=lambda item: (item["field_name"], item["provenance_id"]),
        )
        research_artifacts = sorted(
            artifact_id
            for (kind, artifact_id), values in self.records.items()
            if kind == "research_artifact" and target_id in values.get("referenced_card_ids", ())
        )
        return {
            "record": self.records[key],
            "sources": links,
            "fields": fields,
            "research_artifacts": research_artifacts,
        }

    def audit(self) -> dict[str, Any]:
        statuses = {
            status: sum(source.extraction_status == status for source in self.sources.values())
            for status in ("COMPLETE", "PARTIAL", "UNPROCESSED", "NEEDS_REVIEW")
        }
        canonical = [
            (key, values) for key, values in self.records.items() if values.get("canonical")
        ]
        missing_provenance = [
            f"{kind}:{target_id}"
            for (kind, target_id), _ in canonical
            if not any(
                link.target_type == kind and link.target_id == target_id
                for link in self.links.values()
            )
        ]
        position_partial: dict[str, int] = {}
        for source in self.sources.values():
            if source.extraction_status == "PARTIAL":
                for position in source.positions:
                    position_partial[position] = position_partial.get(position, 0) + 1
        priorities = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
        open_queue = sorted(
            (asdict(item) for item in self.queue.values() if item.status != "RESOLVED"),
            key=lambda item: (priorities.get(item["priority"], 9), item["item_id"]),
        )
        return {
            "known_source_count": len(self.sources),
            "extraction_status_counts": statuses,
            "canonical_record_count": len(canonical),
            "canonical_records_missing_source_provenance": missing_provenance,
            "research_artifacts_with_missing_sources": sorted(
                item["target_id"]
                for item in (asdict(link) for link in self.links.values())
                if item["target_type"] == "missing_research_evidence"
            ),
            "positions_with_incomplete_ingestion": dict(sorted(position_partial.items())),
            "open_reconciliation_count": len(open_queue),
            "highest_priority_reconciliation": open_queue,
            "staged_count": len(self.staged),
            "staged_promoted_count": sum(item.promoted for item in self.staged.values()),
        }

    def as_dict(self) -> dict[str, Any]:
        """Serialize the complete index deterministically."""

        def values(items: Iterable[Any], key: str) -> list[dict[str, Any]]:
            return sorted((asdict(item) for item in items), key=lambda item: item[key])

        return {
            "sources": values(self.sources.values(), "source_id"),
            "records": sorted(
                (
                    {"target_type": kind, "target_id": target_id, **payload}
                    for (kind, target_id), payload in self.records.items()
                ),
                key=lambda item: (item["target_type"], item["target_id"]),
            ),
            "links": values(self.links.values(), "link_id"),
            "field_provenance": values(self.field_provenance.values(), "provenance_id"),
            "reconciliation_queue": values(self.queue.values(), "item_id"),
            "staged_records": values(self.staged.values(), "staged_id"),
        }
