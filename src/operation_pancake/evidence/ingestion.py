"""Validated, idempotent bulk evidence-manifest ingestion."""

from __future__ import annotations

import json
import re
from copy import deepcopy
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from operation_pancake.evidence.index import EvidenceIndex
from operation_pancake.evidence.models import (
    EXTRACTION_STATUSES,
    ORIGINS,
    PROVENANCE_STATUSES,
    SOURCE_TYPES,
)
from operation_pancake.models.player_card import PlayerCard

RESULT_CLASSES = ("NEW", "UPDATE", "MATCH", "DUPLICATE", "CONFLICT", "UNRESOLVED", "REJECTED")
DISPOSITIONS = (
    "CANONICAL_CARD",
    "HISTORICAL_CARD",
    "REFERENCE_DATA",
    "PROGRESSION_EVIDENCE",
    "RESEARCH_ONLY",
)
RECORD_TYPES = (
    "player",
    "card",
    "progression_observation",
    "experiment",
    "research_artifact",
    "market_observation",
)
SUPPORTED_POSITIONS = (
    "QB",
    "HB",
    "FB",
    "WR",
    "TE",
    "LT",
    "LG",
    "C",
    "RG",
    "RT",
    "LE",
    "RE",
    "DT",
    "LOLB",
    "MLB",
    "ROLB",
    "CB",
    "FS",
    "SS",
    "K",
    "P",
)
ATTRIBUTE_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]{1,9}$")


@dataclass(slots=True)
class IngestionState:
    """Persistent non-workbook overlay produced by accepted manifests."""

    manifest_ids: list[str] = field(default_factory=list)
    sources: dict[str, dict[str, Any]] = field(default_factory=dict)
    records: dict[str, dict[str, Any]] = field(default_factory=dict)
    provenance: dict[str, dict[str, Any]] = field(default_factory=dict)
    conflicts: dict[str, dict[str, Any]] = field(default_factory=dict)
    reconciliation: dict[str, dict[str, Any]] = field(default_factory=dict)
    reports: dict[str, dict[str, Any]] = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path) -> IngestionState:
        if not path.exists():
            return cls()
        return cls(**json.loads(path.read_text(encoding="utf-8")))

    def as_dict(self) -> dict[str, Any]:
        return {
            "manifest_ids": sorted(self.manifest_ids),
            "sources": dict(sorted(self.sources.items())),
            "records": dict(sorted(self.records.items())),
            "provenance": dict(sorted(self.provenance.items())),
            "conflicts": dict(sorted(self.conflicts.items())),
            "reconciliation": dict(sorted(self.reconciliation.items())),
            "reports": dict(sorted(self.reports.items())),
        }


class ManifestValidationError(ValueError):
    """Raised when a manifest cannot safely enter staging."""


def _require(mapping: dict[str, Any], fields: tuple[str, ...], context: str) -> None:
    missing = [name for name in fields if mapping.get(name) in (None, "")]
    if missing:
        raise ManifestValidationError(f"{context} missing required fields: {', '.join(missing)}")


def validate_manifest(manifest: dict[str, Any]) -> None:
    """Validate structure and values without changing repository state."""
    _require(manifest, ("manifest_id", "schema_version", "origin"), "manifest")
    if manifest["origin"] not in ORIGINS:
        raise ManifestValidationError(f"Unsupported origin: {manifest['origin']}")
    for source in manifest.get("sources", []):
        _require(source, ("source_id", "source_name", "original_filename", "source_type"), "source")
        if source["source_type"] not in SOURCE_TYPES:
            raise ManifestValidationError(f"Unsupported source type: {source['source_type']}")
        if source.get("extraction_status", "UNPROCESSED") not in EXTRACTION_STATUSES:
            raise ManifestValidationError("Unsupported extraction status")
    manifest_sources = {item["source_id"] for item in manifest.get("sources", [])}
    for record in manifest.get("records", []):
        _require(record, ("record_id", "record_type", "disposition", "validation_status"), "record")
        if record["record_type"] not in RECORD_TYPES:
            raise ManifestValidationError(f"Unsupported record type: {record['record_type']}")
        if record["disposition"] not in DISPOSITIONS:
            raise ManifestValidationError(f"Unsupported disposition: {record['disposition']}")
        values = record.get("values", {})
        position = values.get("position")
        if position is not None and position not in SUPPORTED_POSITIONS:
            raise ManifestValidationError(f"Unsupported position: {position}")
        overall = values.get("overall")
        if overall is not None and (not isinstance(overall, int) or not 0 <= overall <= 99):
            raise ManifestValidationError(f"Invalid OVR: {overall!r}")
        for name, value in values.get("attributes", {}).items():
            if not ATTRIBUTE_PATTERN.fullmatch(name):
                raise ManifestValidationError(f"Invalid attribute name: {name}")
            if value == "UNKNOWN":
                continue
            if not isinstance(value, int) or not 0 <= value <= 99:
                raise ManifestValidationError(f"Invalid attribute value for {name}: {value!r}")
        for link in record.get("source_links", []):
            _require(link, ("source_id", "locator"), "source link")
            if link["source_id"] not in manifest_sources and not link.get("catalog_source"):
                raise ManifestValidationError(
                    f"Source {link['source_id']} must be declared or marked catalog_source"
                )
        for provenance in record.get("provenance", []):
            _require(
                provenance,
                ("provenance_id", "field_name", "source_id", "locator", "provenance_status"),
                "provenance",
            )
            if provenance["provenance_status"] not in PROVENANCE_STATUSES:
                raise ManifestValidationError("Unsupported provenance status")


class BulkManifestIngestor:
    """Classify and persist recovered evidence without modifying the canonical workbook."""

    def __init__(self, index: EvidenceIndex, state: IngestionState | None = None) -> None:
        self.index = index
        self.state = state or IngestionState()

    def ingest(
        self, manifest: dict[str, Any], *, dry_run: bool = True, promote: bool = False
    ) -> dict[str, Any]:
        validate_manifest(manifest)
        working = deepcopy(self.state)
        actions: list[dict[str, Any]] = []
        completion_changes: list[dict[str, str]] = []
        closed: list[str] = []

        for source in manifest.get("sources", []):
            actions.append(self._process_source(source, working, completion_changes))
        for record in manifest.get("records", []):
            actions.extend(self._process_record(record, working, promote))
        for item in manifest.get("reconciliation_items", []):
            actions.append(self._process_queue_item(item, working))
        for conflict in manifest.get("conflicts", []):
            actions.append(self._process_explicit_conflict(conflict, working))
        for resolution in manifest.get("reconciliation_resolutions", []):
            action, item_id = self._process_resolution(resolution, working)
            actions.append(action)
            if item_id:
                closed.append(item_id)

        counts = {result: sum(a["result"] == result for a in actions) for result in RESULT_CLASSES}
        report = {
            "manifest_id": manifest["manifest_id"],
            "dry_run": dry_run,
            "sources_processed": len(manifest.get("sources", [])),
            "records_staged": len(manifest.get("records", [])),
            "records_promoted": sum(a.get("promoted", False) for a in actions),
            "result_counts": counts,
            "actions": actions,
            "queue_items_closed": sorted(closed),
            "queue_items_remaining": self._queue_remaining(working),
            "source_completion_changes": completion_changes,
        }
        if not dry_run:
            if manifest["manifest_id"] not in working.manifest_ids:
                working.manifest_ids.append(manifest["manifest_id"])
            report_id = f"INGEST-{manifest['manifest_id']}"
            working.reports[report_id] = {**report, "dry_run": False}
            self.state = working
        return report

    def _process_source(
        self,
        incoming: dict[str, Any],
        state: IngestionState,
        completion_changes: list[dict[str, str]],
    ) -> dict[str, Any]:
        source_id = incoming["source_id"]
        existing = state.sources.get(source_id)
        catalog = self.index.sources.get(source_id)
        normalized = deepcopy(incoming)
        normalized["coverage"] = self._coverage(incoming.get("coverage", {}))
        if existing == normalized:
            return {"kind": "source", "id": source_id, "result": "MATCH"}
        if existing:
            state.sources[source_id] = normalized
            old = existing.get("coverage", {}).get("status")
            new = normalized["coverage"]["status"]
            if old != new:
                completion_changes.append({"source_id": source_id, "from": old, "to": new})
            return {"kind": "source", "id": source_id, "result": "UPDATE"}
        if catalog:
            catalog_view = {
                "source_name": catalog.source_name,
                "original_filename": catalog.original_filename,
                "source_type": catalog.source_type,
            }
            mismatches = {
                key: (catalog_view[key], incoming[key])
                for key in catalog_view
                if incoming.get(key) != catalog_view[key]
            }
            if mismatches:
                conflict_id = f"CONFLICT-SOURCE-{source_id}"
                state.conflicts[conflict_id] = {
                    "conflict_id": conflict_id,
                    "affected_type": "source",
                    "affected_id": source_id,
                    "differences": mismatches,
                }
                return {"kind": "source", "id": source_id, "result": "CONFLICT"}
            state.sources[source_id] = normalized
            return {"kind": "source", "id": source_id, "result": "MATCH"}
        state.sources[source_id] = normalized
        return {"kind": "source", "id": source_id, "result": "NEW"}

    @staticmethod
    def _coverage(coverage: dict[str, Any]) -> dict[str, Any]:
        expected = set(coverage.get("expected_items", []))
        processed = set(coverage.get("processed_items", []))
        unresolved = set(coverage.get("unresolved_items", []))
        if expected and processed >= expected and not unresolved:
            status = "COMPLETE"
        elif processed or unresolved:
            status = "PARTIAL"
        else:
            status = "UNPROCESSED"
        return {
            **coverage,
            "expected_items": sorted(expected),
            "processed_items": sorted(processed),
            "unresolved_items": sorted(unresolved),
            "cards_identified": sorted(set(coverage.get("cards_identified", []))),
            "cards_extracted": sorted(set(coverage.get("cards_extracted", []))),
            "status": status,
        }

    def _process_record(
        self, record: dict[str, Any], state: IngestionState, promote: bool
    ) -> list[dict[str, Any]]:
        record_id = record["record_id"]
        key = f"{record['record_type']}:{record_id}"
        known_sources = set(self.index.sources) | set(state.sources)
        unknown_sources = sorted(
            link["source_id"]
            for link in record.get("source_links", [])
            if link["source_id"] not in known_sources
        )
        if unknown_sources:
            return [
                {
                    "kind": "record",
                    "id": record_id,
                    "result": "REJECTED",
                    "reason": f"Unknown sources: {', '.join(unknown_sources)}",
                    "promoted": False,
                }
            ]
        unknown_provenance_sources = sorted(
            item["source_id"]
            for item in record.get("provenance", [])
            if item["source_id"] not in known_sources
        )
        if unknown_provenance_sources:
            return [
                {
                    "kind": "record",
                    "id": record_id,
                    "result": "REJECTED",
                    "reason": (
                        f"Unknown provenance sources: {', '.join(unknown_provenance_sources)}"
                    ),
                    "promoted": False,
                }
            ]
        result = "NEW"
        existing = state.records.get(key)
        canonical = self.index.records.get(("player_card", record_id))
        values = deepcopy(record.get("values", {}))
        identity = self._card_identity(values) if record["record_type"] == "card" else None
        if identity and not existing and not canonical:
            duplicate_id = self._find_card_identity(identity, state)
            if duplicate_id:
                return [
                    {
                        "kind": "record",
                        "id": record_id,
                        "result": "DUPLICATE",
                        "duplicate_of": duplicate_id,
                        "promoted": False,
                    }
                ]
        unresolved = list(record.get("unresolved_fields", []))
        unknowns = [
            name for name, value in values.get("attributes", {}).items() if value == "UNKNOWN"
        ]
        unresolved = sorted(set(unresolved + unknowns))
        if canonical:
            compared = {name: values[name] for name in ("player", "overall") if name in values}
            compared.update(values.get("attributes", {}))
            canonical_values = {"player": canonical["player"], "overall": canonical["overall"]}
            canonical_values.update(canonical["attributes"])
            conflicts = EvidenceIndex.conflicts(compared, canonical_values)
            conflicts = {field: pair for field, pair in conflicts.items() if pair[1] != "UNKNOWN"}
            if conflicts:
                result = "CONFLICT"
                for field_name, (old, new) in sorted(conflicts.items()):
                    conflict_id = f"CONFLICT-{record_id}-{field_name}"
                    state.conflicts[conflict_id] = {
                        "conflict_id": conflict_id,
                        "affected_type": "card_field",
                        "affected_id": record_id,
                        "field_name": field_name,
                        "existing_value": old,
                        "incoming_value": new,
                        "existing_provenance": self.index.record_provenance(
                            "player_card", record_id
                        )["fields"],
                        "incoming_provenance": record.get("provenance", []),
                        "status": "OPEN",
                    }
            else:
                result = "MATCH"
        elif existing == record:
            result = "MATCH"
        elif existing:
            if existing.get("values") == values:
                result = "DUPLICATE"
            else:
                result = "UPDATE"
        if unresolved and result not in {"CONFLICT", "REJECTED"}:
            result = "UNRESOLVED"

        promoted = False
        if promote and record["disposition"] == "CANONICAL_CARD":
            if record["validation_status"] != "VALIDATED" or unresolved or result == "CONFLICT":
                result = "REJECTED"
            else:
                PlayerCard(
                    name=values["player"],
                    position=values["position"],
                    overall=values["overall"],
                    archetype=values.get("archetype"),
                    program=values.get("program"),
                    attributes=values.get("attributes", {}),
                )
                promoted = True
        state.records[key] = {
            **deepcopy(record),
            "unresolved_fields": unresolved,
            "promoted": promoted,
        }
        actions = [{"kind": "record", "id": record_id, "result": result, "promoted": promoted}]
        for provenance in record.get("provenance", []):
            provenance_id = provenance["provenance_id"]
            prior = state.provenance.get(provenance_id)
            if prior == provenance:
                provenance_result = "MATCH"
            elif prior:
                provenance_result = "CONFLICT"
            else:
                state.provenance[provenance_id] = deepcopy(provenance)
                provenance_result = "NEW"
            actions.append({"kind": "provenance", "id": provenance_id, "result": provenance_result})
        return actions

    @staticmethod
    def _card_identity(values: dict[str, Any]) -> tuple[str, str, int, str] | None:
        required = (values.get("player"), values.get("position"), values.get("overall"))
        if any(value in (None, "") for value in required):
            return None
        return (
            str(values["player"]).strip().casefold(),
            str(values["position"]).upper(),
            int(values["overall"]),
            str(values.get("program") or "").strip().casefold(),
        )

    def _find_card_identity(
        self, identity: tuple[str, str, int, str], state: IngestionState
    ) -> str | None:
        for (kind, record_id), values in self.index.records.items():
            if (
                kind == "player_card"
                and self._card_identity(
                    {
                        "player": values.get("player"),
                        "position": values.get("position"),
                        "overall": values.get("overall"),
                        "program": values.get("program"),
                    }
                )
                == identity
            ):
                return record_id
        for key, record in state.records.items():
            if (
                record.get("record_type") == "card"
                and self._card_identity(record["values"]) == identity
            ):
                return key
        return None

    def _process_resolution(
        self, resolution: dict[str, Any], state: IngestionState
    ) -> tuple[dict[str, Any], str | None]:
        _require(resolution, ("item_id", "status", "resolution"), "reconciliation resolution")
        item_id = resolution["item_id"]
        existing = state.reconciliation.get(item_id)
        base = self.index.queue.get(item_id)
        if not existing and not base:
            return {"kind": "reconciliation", "id": item_id, "result": "REJECTED"}, None
        payload = asdict(base) if base else deepcopy(existing)
        payload.update(resolution)
        state.reconciliation[item_id] = payload
        closed = item_id if resolution["status"] == "RESOLVED" else None
        return {"kind": "reconciliation", "id": item_id, "result": "UPDATE"}, closed

    def _process_queue_item(self, item: dict[str, Any], state: IngestionState) -> dict[str, Any]:
        _require(
            item,
            ("item_id", "issue_type", "status", "priority", "notes"),
            "reconciliation item",
        )
        item_id = item["item_id"]
        existing = state.reconciliation.get(item_id)
        base = self.index.queue.get(item_id)
        if existing == item:
            result = "MATCH"
        elif existing or base:
            current = existing or asdict(base)
            if current == item:
                result = "MATCH"
            else:
                result = "UPDATE"
        else:
            result = "NEW"
        state.reconciliation[item_id] = deepcopy(item)
        return {"kind": "reconciliation", "id": item_id, "result": result}

    @staticmethod
    def _process_explicit_conflict(
        conflict: dict[str, Any], state: IngestionState
    ) -> dict[str, Any]:
        _require(
            conflict,
            ("conflict_id", "affected_id", "existing_value", "incoming_value", "status"),
            "conflict",
        )
        conflict_id = conflict["conflict_id"]
        existing = state.conflicts.get(conflict_id)
        if existing == conflict:
            result = "MATCH"
        elif existing:
            result = "UPDATE"
        else:
            result = "CONFLICT"
        state.conflicts[conflict_id] = deepcopy(conflict)
        return {"kind": "conflict", "id": conflict_id, "result": result}

    def _queue_remaining(self, state: IngestionState) -> int:
        statuses = {item_id: item.status for item_id, item in self.index.queue.items()}
        statuses.update({item_id: item["status"] for item_id, item in state.reconciliation.items()})
        return sum(status != "RESOLVED" for status in statuses.values())

    def coverage_report(self) -> dict[str, Any]:
        sources = [self._effective_source(source_id) for source_id in self._source_ids()]
        incomplete_records = [
            {"record_key": key, "unresolved_fields": item.get("unresolved_fields", [])}
            for key, item in sorted(self.state.records.items())
            if item.get("unresolved_fields")
        ]
        incomplete_records.extend(
            {
                "record_key": f"{kind}:{record_id}",
                "unresolved_fields": [values["unextracted_cut_fields"]],
            }
            for (kind, record_id), values in sorted(self.index.records.items())
            if values.get("unextracted_cut_fields")
        )
        historical_players = {
            item["values"].get("player")
            for item in self.state.records.values()
            if item.get("disposition") == "HISTORICAL_CARD"
            and item.get("unresolved_fields")
            and item["values"].get("player")
        }

        historical_players.update(
            values.get("player")
            for (kind, _), values in self.index.records.items()
            if kind == "historical_center_observation"
            and values.get("unextracted_cut_fields")
            and values.get("player")
        )
        return {
            "partial_sources": [s for s in sources if s.get("extraction_status") == "PARTIAL"],
            "positions_with_incomplete_evidence": sorted(
                {
                    position
                    for source in sources
                    if source.get("extraction_status") in {"PARTIAL", "UNPROCESSED", "NEEDS_REVIEW"}
                    for position in source.get("positions", [])
                }
            ),
            "unresolved_source_items": [
                {
                    "source_id": s["source_id"],
                    "items": s.get("coverage", {}).get("unresolved_items", []),
                }
                for s in sources
                if s.get("coverage", {}).get("unresolved_items")
            ],
            "incomplete_records": incomplete_records,
            "historical_players_without_rating_vectors": sorted(historical_players),
            "conflicts": list(self.state.as_dict()["conflicts"].values()),
            "canonical_cards_with_multiple_sources": self._canonical_multi_source_cards(),
            "closable_reconciliation": self._closable_reconciliation(),
        }

    def search(self, query: str) -> dict[str, list[dict[str, Any]]]:
        """Search persisted manifest records, targets, sources, and conflicts."""
        needles = re.findall(r"[a-z0-9]+", query.casefold())

        def matches(payload: dict[str, Any]) -> bool:
            text = json.dumps(payload, sort_keys=True).casefold()
            return all(needle in text for needle in needles)

        return {
            "records": [
                {"record_key": key, **record}
                for key, record in sorted(self.state.records.items())
                if matches(record)
            ],
            "reconciliation": [
                item for item in self.state.as_dict()["reconciliation"].values() if matches(item)
            ],
            "sources": [
                {"source_id": source_id, **source}
                for source_id, source in sorted(self.state.sources.items())
                if matches(source)
            ],
            "conflicts": [
                item for item in self.state.as_dict()["conflicts"].values() if matches(item)
            ],
        }

    def promoted_cards(self) -> list[PlayerCard]:
        """Materialize explicitly promoted cards for the canonical repository layer."""
        cards = []
        for record in self.state.records.values():
            if not record.get("promoted"):
                continue
            values = record["values"]
            cards.append(
                PlayerCard(
                    name=values["player"],
                    position=values["position"],
                    overall=values["overall"],
                    archetype=values.get("archetype"),
                    program=values.get("program"),
                    attributes=values.get("attributes", {}),
                    source=record["source_links"][0]["source_id"],
                    source_record=record["record_id"],
                    confidence="validated",
                )
            )
        return cards

    def _canonical_multi_source_cards(self) -> list[dict[str, Any]]:
        source_sets: dict[str, set[str]] = {}
        for link in self.index.links.values():
            if link.target_type == "player_card":
                source_sets.setdefault(link.target_id, set()).add(link.source_id)
        return [
            {"card_id": card_id, "source_ids": sorted(source_ids)}
            for card_id, source_ids in sorted(source_sets.items())
            if len(source_ids) > 1
        ]

    def _closable_reconciliation(self) -> list[str]:
        complete_sources = {
            source_id
            for source_id, source in self.state.sources.items()
            if source.get("coverage", {}).get("status") == "COMPLETE"
        }
        return sorted(
            item_id
            for item_id, item in self.index.queue.items()
            if item.status != "RESOLVED" and item.source_id in complete_sources
        )

    def _source_ids(self) -> set[str]:
        return set(self.index.sources) | set(self.state.sources)

    def _effective_source(self, source_id: str) -> dict[str, Any]:
        if source_id in self.state.sources:
            item = deepcopy(self.state.sources[source_id])
            item["source_id"] = source_id
            item["extraction_status"] = item.get("coverage", {}).get(
                "status", item.get("extraction_status")
            )
            return item
        return asdict(self.index.sources[source_id])


def load_manifest(path: Path) -> dict[str, Any]:
    """Load a JSON manifest with an explicit file-type boundary."""
    if path.suffix.lower() != ".json":
        raise ManifestValidationError("Only JSON manifests are supported.")
    return json.loads(path.read_text(encoding="utf-8"))


def save_state(path: Path, state: IngestionState) -> None:
    """Persist deterministic ingestion state."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state.as_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def save_report(path: Path, report: dict[str, Any]) -> None:
    """Persist one deterministic report as an evidence artifact."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
