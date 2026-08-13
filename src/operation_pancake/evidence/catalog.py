"""Build and persist the Operation Pancake evidence index."""

from __future__ import annotations

import json
import re
from pathlib import Path

from openpyxl import load_workbook

from operation_pancake.evidence.index import EvidenceIndex
from operation_pancake.evidence.models import (
    EvidenceLink,
    FieldProvenance,
    ReconciliationItem,
    SourceRecord,
)

WORKBOOK = Path("data/canonical/canonical_v1.9.xlsx")
INVENTORY = Path("data/research/progression_audit/progression_inventory.json")


def _status(raw: str) -> tuple[str, str | None]:
    upper = raw.upper()
    if upper.startswith("COMPLETE"):
        return "COMPLETE", None
    if upper.startswith("PARTIAL"):
        return "PARTIAL", "Source registry identifies remaining evidence as unprocessed."
    if upper.startswith("REGISTERED"):
        return "UNPROCESSED", "Registered source has not been extracted."
    if upper.startswith("DUPLICATE"):
        return "NEEDS_REVIEW", "Duplicate/cross-check relationship requires reconciliation."
    if upper.startswith("EXTRACTED"):
        remaining = None if "COMPLETE" in upper else "Only the stated subset has been extracted."
        return ("COMPLETE" if remaining is None else "PARTIAL"), remaining
    return "NEEDS_REVIEW", "Legacy status requires review."


def _source_type(raw: str) -> str:
    upper = raw.upper()
    return next(
        (kind for kind in ("PDF", "IMAGE", "WORKBOOK", "CSV", "WEB", "API") if kind in upper),
        "OTHER",
    )


def _slug(value: str) -> str:
    return re.sub(r"[^A-Z0-9]+", "-", value.upper()).strip("-")


def build_evidence_index(root: Path) -> EvidenceIndex:
    """Build a deterministic index from authoritative repository evidence."""
    index = EvidenceIndex()
    workbook_path = root / WORKBOOK
    workbook = load_workbook(workbook_path, read_only=True, data_only=True)
    rows = list(workbook["Source_Registry"].iter_rows(min_row=5, values_only=True))
    for row in rows:
        if not row[0]:
            continue
        source_id, filename, raw_type, domain, raw_status, url, notes, use = row[:8]
        extraction, remaining = _status(str(raw_status or ""))
        position = tuple(p for p in ("QB", "TE", "C") if re.search(rf"\b{p}\b", str(domain)))
        index.add_source(
            SourceRecord(
                source_id=str(source_id),
                source_name=str(domain),
                original_filename=str(filename),
                source_type=_source_type(str(raw_type)),
                category=str(domain),
                origin="LOCAL_REPOSITORY",
                positions=position,
                extraction_status=extraction,
                extraction_remaining=remaining,
                validation_status="WORKBOOK_REGISTERED",
                canonical_ingestion_status=str(use or "UNKNOWN"),
                research_use_status="USED" if "research" in str(use).lower() else "AVAILABLE",
                notes="; ".join(x for x in (str(notes or ""), str(url or "")) if x),
                provenance="REPOSITORY_CONFIRMED",
            )
        )

    # This known File Library item is intentionally distinct from the EA roster reference.
    index.add_source(
        SourceRecord(
            source_id="SRC-C-RAW-003",
            source_name="Partial raw Center CUT card source",
            original_filename="raw str centers2(2).pdf",
            source_type="PDF",
            category="CUT_CENTER_CARDS",
            origin="CHATGPT_FILE_LIBRARY",
            discovered_date="2026-08-13",
            positions=("C",),
            item_count=14,
            extraction_status="PARTIAL",
            extraction_remaining=(
                "Pages/cards beyond the known 14-page partial set remain unavailable or "
                "unvalidated."
            ),
            validation_status="NEEDS_REVIEW",
            canonical_ingestion_status="NOT_INGESTED",
            research_use_status="HISTORICAL_CENTER_EVIDENCE",
            provenance="HISTORICALLY_RECOVERED",
            notes="Known 14-page partial source; not the EA base-roster reference dataset.",
        )
    )

    inventory = json.loads((root / INVENTORY).read_text(encoding="utf-8"))
    cards_by_id = {card["card_id"]: card for card in inventory["canonical_cards"]}
    for card in inventory["canonical_cards"]:
        card_id = card["card_id"]
        source_id = card["source_id"]
        index.add_record("player_card", card_id, {**card, "canonical": True})
        index.add_link(
            EvidenceLink(
                link_id=f"LINK-CARD-{card_id}",
                source_id=source_id,
                target_type="player_card",
                target_id=card_id,
                relationship="CANONICAL_SOURCE",
                locator=card.get("source_locator"),
            )
        )
        fields = {"player": card["player"], "overall": card["overall"], **card["attributes"]}
        for field, value in fields.items():
            index.add_field_provenance(
                FieldProvenance(
                    provenance_id=f"PROV-{card_id}-{field}",
                    target_type="player_card",
                    target_id=card_id,
                    field_name=field,
                    value=value,
                    source_id=source_id,
                    locator=card.get("source_locator"),
                    extraction_method="CANONICAL_WORKBOOK_IMPORT",
                    validation_status=card["validation_status"],
                    confidence="validated",
                    provenance_status="DIRECTLY_OBSERVED",
                    version="canonical_v1.9",
                )
            )

    for number, candidate in enumerate(inventory["progression_candidates"], start=1):
        candidate_id = f"PROG-CAND-{number:04d}"
        index.add_record("progression_evidence", candidate_id, {**candidate, "canonical": False})
        for card_id in (candidate["lower_card_id"], candidate["upper_card_id"]):
            card = cards_by_id[card_id]
            index.add_link(
                EvidenceLink(
                    link_id=f"LINK-{candidate_id}-{card_id}",
                    source_id=card["source_id"],
                    target_type="progression_evidence",
                    target_id=candidate_id,
                    relationship="SUPPORTING_CARD_SOURCE",
                    locator=card.get("source_locator"),
                    notes=f"Evidence card {card_id}",
                )
            )

    research_root = root / "data/research"
    for path in sorted(research_root.rglob("*")):
        if path.suffix.lower() not in {".json", ".csv"}:
            continue
        relative = path.relative_to(root).as_posix()
        artifact_id = f"ART-{_slug(relative)}"
        text = path.read_text(encoding="utf-8")
        referenced_cards = sorted(set(re.findall(r"(?:QB|TE|C)-\d{4}", text)))
        index.add_record(
            "research_artifact",
            artifact_id,
            {
                "path": relative,
                "canonical": False,
                "research_only": True,
                "referenced_card_ids": referenced_cards,
            },
        )
        for source_id in sorted(set(re.findall(r"SRC-[A-Z0-9-]+", text)) & index.sources.keys()):
            index.add_link(
                EvidenceLink(
                    link_id=f"LINK-{artifact_id}-{source_id}",
                    source_id=source_id,
                    target_type="research_artifact",
                    target_id=artifact_id,
                    relationship="CITED_OR_EMBEDDED_SOURCE",
                )
            )

    for source in index.sources.values():
        if source.extraction_status in {"PARTIAL", "UNPROCESSED", "NEEDS_REVIEW"}:
            issue = (
                "PARTIALLY_EXTRACTED"
                if source.extraction_status == "PARTIAL"
                else "NEEDS_VALIDATION"
            )
            index.add_queue_item(
                ReconciliationItem(
                    item_id=f"REC-{source.source_id}",
                    source_id=source.source_id,
                    affected_type="source",
                    affected_id=source.source_id,
                    issue_type=issue,
                    status="OPEN",
                    priority="HIGH" if source.source_id == "SRC-C-RAW-003" else "MEDIUM",
                    notes=source.extraction_remaining or "Source requires review.",
                    created_at="2026-08-13",
                )
            )
    return index


def write_evidence_artifacts(root: Path) -> EvidenceIndex:
    """Write deterministic index and audit JSON artifacts."""
    index = build_evidence_index(root)
    output = root / "data/evidence"
    output.mkdir(parents=True, exist_ok=True)
    (output / "source_index.json").write_text(
        json.dumps(index.as_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (output / "ingestion_audit.json").write_text(
        json.dumps(index.audit(), indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return index
