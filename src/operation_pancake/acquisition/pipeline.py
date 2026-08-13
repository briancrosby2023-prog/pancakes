"""Raw-snapshot-first external acquisition pipeline."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from operation_pancake.acquisition.adapters import ExternalCardAdapter
from operation_pancake.acquisition.models import ExternalCard, RawSnapshot
from operation_pancake.evidence.ingestion import BulkManifestIngestor

UPDATE_STATES = ("NEW_CARD", "UNCHANGED", "UPDATED_SOURCE", "POSSIBLE_CORRECTION", "CONFLICT")
CONFLICT_TYPES = (
    "RATING_MISMATCH",
    "OVR_MISMATCH",
    "ARCHETYPE_MISMATCH",
    "PROGRAM_MISMATCH",
    "CARD_TYPE_MISMATCH",
    "IDENTITY_AMBIGUITY",
)


@dataclass(slots=True)
class AcquisitionState:
    cards: dict[str, dict[str, Any]] = field(default_factory=dict)
    snapshots: dict[str, dict[str, Any]] = field(default_factory=dict)
    retrieval_history: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    market_observations: dict[str, dict[str, Any]] = field(default_factory=dict)
    conflicts: dict[str, dict[str, Any]] = field(default_factory=dict)
    failures: list[dict[str, Any]] = field(default_factory=list)
    resume_cursor: str | None = None

    @classmethod
    def load(cls, path: Path) -> AcquisitionState:
        return cls(**json.loads(path.read_text(encoding="utf-8"))) if path.exists() else cls()

    def as_dict(self) -> dict[str, Any]:
        payload = {
            "cards": dict(sorted(self.cards.items())),
            "snapshots": dict(sorted(self.snapshots.items())),
            "retrieval_history": dict(sorted(self.retrieval_history.items())),
            "market_observations": dict(sorted(self.market_observations.items())),
            "conflicts": dict(sorted(self.conflicts.items())),
            "failures": self.failures,
            "resume_cursor": self.resume_cursor,
        }
        return json.loads(json.dumps(payload, sort_keys=True))


def match_external_card(card: ExternalCard, candidates: list[dict[str, Any]]) -> dict[str, Any]:
    """Conservatively match external identity without collapsing program variants."""
    external_matches = [
        item
        for item in candidates
        if item.get("external_source", "").casefold() == card.external_source.casefold()
        and item.get("external_card_id") == card.external_card_id
    ]
    if len(external_matches) == 1:
        return {"status": "EXTERNAL_ID_MATCH", "matches": external_matches}
    exact = [
        item
        for item in candidates
        if (
            str(item.get("player", "")).strip().casefold(),
            str(item.get("position", "")).upper(),
            item.get("overall"),
            str(item.get("archetype") or "").strip().casefold(),
            str(item.get("program") or "").strip().casefold(),
            str(item.get("card_type") or "").strip().casefold(),
        )
        == card.conservative_identity
    ]
    if len(exact) == 1:
        return {"status": "CONSERVATIVE_MATCH", "matches": exact}
    broad = [
        item
        for item in candidates
        if str(item.get("player", "")).strip().casefold() == card.player_name.strip().casefold()
        and str(item.get("position", "")).upper() == card.position.upper()
        and item.get("overall") == card.overall
    ]
    if broad:
        return {"status": "IDENTITY_AMBIGUITY", "matches": broad}
    return {"status": "NEW_CARD", "matches": []}


def canonical_conflicts(card: ExternalCard, index) -> list[dict[str, Any]]:
    """Compare a conservatively matched external card without changing canonical data."""
    candidates = [
        {"card_id": record_id, **values}
        for (kind, record_id), values in index.records.items()
        if kind == "player_card"
    ]
    match = match_external_card(card, candidates)
    if match["status"] == "IDENTITY_AMBIGUITY":
        return [
            {
                "type": "IDENTITY_AMBIGUITY",
                "external_card_id": card.external_card_id,
                "candidate_card_ids": sorted(item["card_id"] for item in match["matches"]),
                "incoming_provenance": card.source_reference,
            }
        ]
    if match["status"] != "CONSERVATIVE_MATCH":
        return []
    canonical = match["matches"][0]
    conflicts = []
    for attribute, incoming in card.displayed_ratings.items():
        existing = canonical.get("attributes", {}).get(attribute)
        if incoming is not None and existing is not None and incoming != existing:
            conflicts.append(
                {
                    "type": "RATING_MISMATCH",
                    "card_id": canonical["card_id"],
                    "external_card_id": card.external_card_id,
                    "field": attribute,
                    "existing_value": existing,
                    "incoming_value": incoming,
                    "existing_provenance": canonical.get("source_id"),
                    "incoming_provenance": card.source_reference,
                }
            )
    return conflicts


class AcquisitionPipeline:
    def __init__(
        self, root: Path, ingestor: BulkManifestIngestor, state: AcquisitionState | None = None
    ) -> None:
        self.root = root
        self.ingestor = ingestor
        self.state = state or AcquisitionState()

    def acquire_fixture(
        self, adapter: ExternalCardAdapter, retrieved_at: str, *, dry_run: bool = True
    ) -> dict[str, Any]:
        working = AcquisitionState(**json.loads(json.dumps(self.state.as_dict())))
        results = []
        manifest_records = []
        for discovery in adapter.discover_cards():
            external_card_id = str(discovery["external_card_id"])
            try:
                content = adapter.fetch_card(discovery)
                snapshot = self._snapshot(adapter, discovery, content, retrieved_at, working)
                parsed = adapter.parse_card(snapshot, content)
                card = adapter.normalize_card(parsed, snapshot)
                classification = self._classify(card, working)
                canonical_issues = canonical_conflicts(card, self.ingestor.index)
                for number, conflict in enumerate(canonical_issues, start=1):
                    conflict_id = (
                        f"CANONICAL-CONFLICT-{card.external_source}-"
                        f"{card.external_card_id}-{number}"
                    )
                    working.conflicts[conflict_id] = {
                        "conflict_id": conflict_id,
                        **conflict,
                        "status": "OPEN",
                    }
                if canonical_issues:
                    classification = {
                        "external_card_id": card.external_card_id,
                        "status": "CONFLICT",
                        "conflict_ids": sorted(working.conflicts),
                    }
                results.append(classification)
                key = f"{card.external_source}:{card.external_card_id}"
                working.cards[key] = asdict(card)
                working.retrieval_history.setdefault(key, []).append(
                    {
                        "retrieved_at": retrieved_at,
                        "content_sha256": snapshot.content_sha256,
                        "classification": classification["status"],
                    }
                )
                for observation in card.market_observations:
                    working.market_observations[observation.observation_id] = asdict(observation)
                manifest_records.append(adapter.stage_card(card))
                working.resume_cursor = external_card_id
            except PermissionError as error:
                working.failures.append(
                    {
                        "external_card_id": external_card_id,
                        "status": "BLOCKED",
                        "reason": str(error),
                        "bypass_attempted": False,
                    }
                )
                results.append({"external_card_id": external_card_id, "status": "BLOCKED"})
        manifest = {
            "manifest_id": f"EXTERNAL-{adapter.source_name}-{retrieved_at.replace(':', '-')}",
            "schema_version": "1.0",
            "origin": "EXTERNAL_WEB",
            "sources": [
                {
                    "source_id": adapter.source_name,
                    "source_name": f"{adapter.source_name} external card source",
                    "original_filename": f"external://{adapter.source_name}",
                    "source_type": "OTHER",
                    "extraction_status": "PARTIAL",
                }
            ],
            "records": manifest_records,
            "reconciliation_resolutions": [],
        }
        staging_report = self.ingestor.ingest(manifest, dry_run=dry_run)
        report = {
            "adapter": adapter.source_name,
            "dry_run": dry_run,
            "results": results,
            "staging_report": staging_report,
            "failures": working.failures,
        }
        if not dry_run:
            self.state = working
        return report

    def _snapshot(self, adapter, discovery, content, retrieved_at, state) -> RawSnapshot:
        digest = hashlib.sha256(content).hexdigest()
        relative = Path("data/external/raw") / adapter.source_name.lower() / f"{digest}.bin"
        snapshot = RawSnapshot(
            source=adapter.source_name,
            retrieved_at=retrieved_at,
            external_identifiers={
                key: str(value) for key, value in discovery.items() if value is not None
            },
            content_sha256=digest,
            snapshot_location=relative.as_posix(),
            parser_version=adapter.parser_version,
            content_type="application/octet-stream",
        )
        state.snapshots[digest] = asdict(snapshot)
        if not (self.root / relative).exists():
            (self.root / relative).parent.mkdir(parents=True, exist_ok=True)
            (self.root / relative).write_bytes(content)
        return snapshot

    def _classify(self, card: ExternalCard, state: AcquisitionState) -> dict[str, Any]:
        key = f"{card.external_source}:{card.external_card_id}"
        existing = state.cards.get(key)
        if not existing:
            return {"external_card_id": card.external_card_id, "status": "NEW_CARD"}
        incoming = asdict(card)
        immutable = (
            "player_name",
            "position",
            "overall",
            "archetype",
            "program",
            "card_type",
            "displayed_ratings",
        )
        changes = {
            field: (existing.get(field), incoming.get(field))
            for field in immutable
            if existing.get(field) != incoming.get(field)
        }
        if changes:
            conflict_types = []
            mapping = {
                "overall": "OVR_MISMATCH",
                "archetype": "ARCHETYPE_MISMATCH",
                "program": "PROGRAM_MISMATCH",
                "card_type": "CARD_TYPE_MISMATCH",
                "displayed_ratings": "RATING_MISMATCH",
            }
            conflict_types.extend(mapping.get(field, "IDENTITY_AMBIGUITY") for field in changes)
            conflict_id = f"EXT-CONFLICT-{card.external_source}-{card.external_card_id}"
            state.conflicts[conflict_id] = {
                "conflict_id": conflict_id,
                "types": sorted(set(conflict_types)),
                "existing": existing,
                "incoming": incoming,
                "status": "OPEN",
            }
            return {
                "external_card_id": card.external_card_id,
                "status": "CONFLICT",
                "conflict_id": conflict_id,
            }
        if existing.get("raw_snapshot_reference") != incoming["raw_snapshot_reference"]:
            return {"external_card_id": card.external_card_id, "status": "UPDATED_SOURCE"}
        return {"external_card_id": card.external_card_id, "status": "UNCHANGED"}

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(self.state.as_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )


def population_targets(root: Path) -> list[dict[str, Any]]:
    """Convert formula gaps into source-neutral acquisition targets."""
    gaps = json.loads(
        (root / "data/research/repository_completeness_audit/formula_gap_map.json").read_text()
    )
    readiness = json.loads(
        (root / "data/research/repository_completeness_audit/readiness.json").read_text()
    )
    priority = {item["position"]: item["recovery_priority"] for item in readiness}
    targets = []
    for gap in gaps:
        position = gap["position"]
        target = {
            "position": position,
            "priority": priority[position],
            "needed_ovr_range": [80, 85] if position == "C" else "three distinct OVR levels",
            "needed_archetypes": 2,
            "minimum_desired_cards": 5,
            "reason": gap["smallest_material_evidence_set"],
        }
        targets.append(target)
    order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    return sorted(targets, key=lambda item: (order[item["priority"]], item["position"]))
