from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from operation_pancake.evidence.catalog import build_evidence_index
from operation_pancake.evidence.ingestion import (
    BulkManifestIngestor,
    IngestionState,
    ManifestValidationError,
    save_report,
    save_state,
    validate_manifest,
)

ROOT = Path(__file__).resolve().parents[1]


def manifest() -> dict:
    return {
        "manifest_id": "TEST-BULK-001",
        "schema_version": "1.0",
        "origin": "CHATGPT_FILE_LIBRARY",
        "sources": [
            {
                "source_id": "SRC-TEST-PDF-001",
                "source_name": "Recovered Center PDF",
                "original_filename": "recovered.pdf",
                "source_type": "PDF",
                "coverage": {
                    "expected_items": [1, 2],
                    "processed_items": [1],
                    "unresolved_items": [2],
                    "cards_identified": ["HIST-TEST-001"],
                    "cards_extracted": [],
                },
            }
        ],
        "records": [
            {
                "record_id": "HIST-TEST-001",
                "record_type": "card",
                "disposition": "HISTORICAL_CARD",
                "validation_status": "NEEDS_REVIEW",
                "values": {
                    "player": "Recovered Center",
                    "position": "C",
                    "overall": 82,
                    "program": "Core",
                    "attributes": {"STR": 85, "AWR": "UNKNOWN"},
                },
                "unresolved_fields": ["AWR"],
                "source_links": [{"source_id": "SRC-TEST-PDF-001", "locator": "page 1"}],
                "provenance": [
                    {
                        "provenance_id": "PROV-HIST-TEST-001-STR",
                        "field_name": "STR",
                        "source_id": "SRC-TEST-PDF-001",
                        "locator": "page 1 rating panel",
                        "provenance_status": "DIRECTLY_OBSERVED",
                    }
                ],
            },
            {
                "record_id": "PROG-TEST-001",
                "record_type": "progression_observation",
                "disposition": "PROGRESSION_EVIDENCE",
                "validation_status": "HISTORICAL",
                "values": {
                    "player": "Recovered Center",
                    "position": "C",
                    "lower_card_id": "HIST-TEST-001",
                    "upper_card_id": "HIST-TEST-002",
                },
                "source_links": [{"source_id": "SRC-TEST-PDF-001", "locator": "pages 1-2"}],
            },
        ],
        "reconciliation_resolutions": [],
    }


@pytest.fixture(scope="module")
def index():
    return build_evidence_index(ROOT)


def test_bulk_manifest_dry_run_is_deterministic_and_nonmutating(index) -> None:
    ingestor = BulkManifestIngestor(index)
    first = ingestor.ingest(manifest(), dry_run=True)
    second = ingestor.ingest(manifest(), dry_run=True)
    assert first == second
    assert ingestor.state == IngestionState()
    assert first["result_counts"]["NEW"] >= 2
    assert first["result_counts"]["UNRESOLVED"] == 1


def test_repeated_ingestion_is_idempotent(index) -> None:
    ingestor = BulkManifestIngestor(index)
    ingestor.ingest(manifest(), dry_run=False)
    first_state = json.dumps(ingestor.state.as_dict(), sort_keys=True)
    report = ingestor.ingest(manifest(), dry_run=False)
    second_state = json.dumps(ingestor.state.as_dict(), sort_keys=True)
    assert first_state != second_state  # the deterministic report is refreshed
    assert len(ingestor.state.sources) == 1
    assert len(ingestor.state.records) == 2
    assert len(ingestor.state.provenance) == 1
    assert report["result_counts"]["NEW"] == 0


def test_unknown_is_preserved_and_never_coerced(index) -> None:
    ingestor = BulkManifestIngestor(index)
    ingestor.ingest(manifest(), dry_run=False)
    record = ingestor.state.records["card:HIST-TEST-001"]
    assert record["values"]["attributes"]["AWR"] == "UNKNOWN"
    assert record["unresolved_fields"] == ["AWR"]


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda m: m["records"][0]["values"].update(overall=100), "Invalid OVR"),
        (lambda m: m["records"][0]["values"].update(position="CENTER"), "Unsupported position"),
        (
            lambda m: m["records"][0]["values"]["attributes"].update({"bad name": 4}),
            "Invalid attribute name",
        ),
    ],
)
def test_validation_gate_rejects_invalid_values(mutation, message) -> None:
    incoming = manifest()
    mutation(incoming)
    with pytest.raises(ManifestValidationError, match=message):
        validate_manifest(incoming)


def test_unknown_catalog_source_is_rejected(index) -> None:
    incoming = manifest()
    incoming["sources"] = []
    incoming["records"] = [deepcopy(incoming["records"][0])]
    incoming["records"][0]["source_links"][0] = {
        "source_id": "SRC-NOT-CATALOGED",
        "locator": "page 1",
        "catalog_source": True,
    }
    report = BulkManifestIngestor(index).ingest(incoming)
    assert report["result_counts"]["REJECTED"] == 1


def test_conflict_preserves_canonical_and_incoming_provenance(index) -> None:
    incoming = manifest()
    incoming["records"] = [deepcopy(incoming["records"][0])]
    record = incoming["records"][0]
    record["record_id"] = "QB-0074"
    record["values"] = {"player": "Darian Mensah", "position": "QB", "overall": 99}
    report = BulkManifestIngestor(index).ingest(incoming, dry_run=False)
    assert report["result_counts"]["CONFLICT"] == 1
    conflict = next(iter(BulkManifestIngestor(index).state.conflicts.values()), None)
    assert conflict is None  # a separate ingestor has no persisted state
    ingestor = BulkManifestIngestor(index)
    ingestor.ingest(incoming, dry_run=False)
    conflict = ingestor.state.conflicts["CONFLICT-QB-0074-overall"]
    assert conflict["existing_value"] != conflict["incoming_value"]
    assert conflict["existing_provenance"]


def test_source_coverage_moves_partial_to_complete(index) -> None:
    ingestor = BulkManifestIngestor(index)
    ingestor.ingest(manifest(), dry_run=False)
    complete = manifest()
    complete["manifest_id"] = "TEST-BULK-002"
    coverage = complete["sources"][0]["coverage"]
    coverage["processed_items"] = [1, 2]
    coverage["unresolved_items"] = []
    coverage["cards_extracted"] = ["HIST-TEST-001"]
    report = ingestor.ingest(complete, dry_run=False)
    assert report["source_completion_changes"] == [
        {"source_id": "SRC-TEST-PDF-001", "from": "PARTIAL", "to": "COMPLETE"}
    ]


def test_reconciliation_closure_and_partial_resolution(index) -> None:
    incoming = manifest()
    incoming["reconciliation_resolutions"] = [
        {
            "item_id": "REC-SRC-C-RAW-003",
            "status": "PARTIAL",
            "resolution": "Pages 4-8 processed; pages 9-14 remain.",
        }
    ]
    ingestor = BulkManifestIngestor(index)
    partial = ingestor.ingest(incoming, dry_run=False)
    assert partial["queue_items_closed"] == []
    incoming["manifest_id"] = "TEST-BULK-002"
    incoming["reconciliation_resolutions"][0].update(
        status="RESOLVED", resolution="All pages validated.", resolved_at="2026-08-13"
    )
    closed = ingestor.ingest(incoming, dry_run=False)
    assert closed["queue_items_closed"] == ["REC-SRC-C-RAW-003"]
    assert (
        ingestor.state.reconciliation["REC-SRC-C-RAW-003"]["resolution"] == "All pages validated."
    )


def test_screenshot_batch_and_pdf_page_provenance(index) -> None:
    incoming = manifest()
    incoming["sources"].append(
        {
            "source_id": "SRC-SCREEN-BATCH-001",
            "source_name": "July screenshots",
            "original_filename": "july-archive",
            "source_type": "SCREENSHOT",
            "coverage": {
                "expected_items": ["001.png", "002.png"],
                "processed_items": [],
                "unresolved_items": ["001.png", "002.png"],
            },
        }
    )
    report = BulkManifestIngestor(index).ingest(incoming)
    assert report["sources_processed"] == 2
    assert incoming["records"][1]["source_links"][0]["locator"] == "pages 1-2"


def test_historical_and_reference_records_never_auto_promote(index) -> None:
    ingestor = BulkManifestIngestor(index)
    report = ingestor.ingest(manifest(), dry_run=False, promote=True)
    assert report["records_promoted"] == 0


def test_validated_canonical_promotion_is_explicit(index) -> None:
    incoming = manifest()
    incoming["records"] = [deepcopy(incoming["records"][0])]
    record = incoming["records"][0]
    record["record_id"] = "RECOVERED-C-VALIDATED-001"
    record["disposition"] = "CANONICAL_CARD"
    record["validation_status"] = "VALIDATED"
    record["values"]["attributes"] = {"STR": 85, "AWR": 80}
    record["unresolved_fields"] = []
    ingestor = BulkManifestIngestor(index)
    report = ingestor.ingest(incoming, dry_run=False, promote=True)
    assert report["records_promoted"] == 1
    assert ingestor.promoted_cards()[0].name == "Recovered Center"


def test_duplicate_card_identity_is_not_staged_twice(index) -> None:
    ingestor = BulkManifestIngestor(index)
    ingestor.ingest(manifest(), dry_run=False)
    duplicate = manifest()
    duplicate["manifest_id"] = "TEST-DUPLICATE"
    duplicate["records"] = [deepcopy(duplicate["records"][0])]
    duplicate["records"][0]["record_id"] = "HIST-TEST-DUPLICATE"
    report = ingestor.ingest(duplicate, dry_run=False)
    assert report["result_counts"]["DUPLICATE"] == 1
    assert "card:HIST-TEST-DUPLICATE" not in ingestor.state.records


def test_coverage_report_lists_incomplete_historical_players(index) -> None:
    ingestor = BulkManifestIngestor(index)
    ingestor.ingest(manifest(), dry_run=False)
    coverage = ingestor.coverage_report()
    assert "Recovered Center" in coverage["historical_players_without_rating_vectors"]
    assert "Brady Small" in coverage["historical_players_without_rating_vectors"]
    assert coverage["unresolved_source_items"][0]["items"] == [2]


def test_state_and_ingestion_report_persist_deterministically(index, tmp_path) -> None:
    ingestor = BulkManifestIngestor(index)
    report = ingestor.ingest(manifest(), dry_run=False)
    state_path = tmp_path / "state.json"
    report_path = tmp_path / "report.json"
    save_state(state_path, ingestor.state)
    save_report(report_path, report)
    assert IngestionState.load(state_path).as_dict() == ingestor.state.as_dict()
    assert json.loads(report_path.read_text()) == report
