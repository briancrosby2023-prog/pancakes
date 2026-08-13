import json
from pathlib import Path

import pytest

from operation_pancake.evidence.catalog import build_evidence_index
from operation_pancake.evidence.ingestion import BulkManifestIngestor, load_manifest

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "data/evidence/manifests/historical_progression_inventory_v1.json"
NAMED = {
    "Junior Seau": [81, 84, 86, 87],
    "Bo Jackson": [80, 83, 86],
    "Chris Peal": [81, 86, 87],
    "Peyton Bowen": [83, 85, 86],
    "Michael Crabtree": [78, 80, 83, 85],
}


@pytest.fixture(scope="module")
def ingested():
    ingestor = BulkManifestIngestor(build_evidence_index(ROOT))
    report = ingestor.ingest(load_manifest(MANIFEST), dry_run=False)
    return ingestor, report


def test_manifest_ingests_historical_progression_without_promotion(ingested) -> None:
    ingestor, report = ingested
    assert report["records_staged"] == 13
    assert report["records_promoted"] == 0
    assert len(ingestor.state.records) == 13
    assert all(not record["promoted"] for record in ingestor.state.records.values())


def test_named_chains_preserve_states_without_fake_vectors(ingested) -> None:
    ingestor, _ = ingested
    for player, states in NAMED.items():
        match = next(
            record
            for record in ingestor.state.records.values()
            if record.get("values", {}).get("player") == player
            and record["record_type"] == "progression_observation"
        )
        assert match["values"]["known_states"] == states
        assert match["values"]["missing_vectors"] == states
        assert "attributes" not in match["values"]


def test_crabtree_findings_preserve_only_reported_totals(ingested) -> None:
    ingestor, _ = ingested
    result = ingestor.state.records["research_artifact:HIST-RESEARCH-CRABTREE-DELTAS"]
    assert result["values"]["constant_fields"] == {"AWR": 80}
    assert result["values"]["reported_total_changes"]["ACC"] == 8
    assert result["values"]["intermediate_vectors_synthesized"] is False


def test_harrington_conflict_keeps_stronger_validated_chain(ingested) -> None:
    ingestor, _ = ingested
    conflict = ingestor.state.conflicts["CONFLICT-HARRINGTON-HISTORICAL-CHAIN"]
    assert conflict["incoming_value"]["states"] == [80, 84, 86]
    assert conflict["existing_value"]["states"] == [79, 81, 84, 86]
    assert conflict["status"] == "RESOLVED_STRONGER_EVIDENCE_CONTROLS"
    record = ingestor.state.records["progression_observation:HIST-PROG-JOEY-HARRINGTON-OLD"]
    assert record["values"]["canonical_links"] == ["QB-0074", "QB-0038", "QB-0013", "QB-0003"]
    assert record["values"]["excluded_comparison_link"] == "QB-0054"


def test_te_target_cross_references_existing_cards_without_duplication(ingested) -> None:
    ingestor, _ = ingested
    record = ingestor.state.records["progression_observation:RECOVERY-PROG-TE-80-85"]
    refs = record["values"]["existing_te_cross_references"]
    assert refs["Peter Clarke"] == ["TE-0049"]
    assert refs["Jalen Hoffman"] == ["TE-0048", "TE-0038"]
    assert refs["Eli Finley"] == ["TE-0020", "TE-0011"]
    assert refs["Ozzie Newsome"] == ["TE-0037", "TE-0013"]


def test_screenshot_archive_has_twelve_deterministic_targets(ingested) -> None:
    ingestor, _ = ingested
    coverage = ingestor.state.sources["SRC-IMG-ARCH"]["coverage"]
    assert len(coverage["expected_items"]) == 12
    assert coverage["expected_items"] == coverage["unresolved_items"]
    assert coverage["cards_extracted"] == []
    targets = [key for key in ingestor.state.reconciliation if key.startswith("REC-PROG-")]
    assert len(targets) == 12


@pytest.mark.parametrize(
    "query",
    [
        "Junior Seau progression",
        "Bo Jackson progression",
        "Chris Peal progression",
        "Peyton Bowen progression",
        "Michael Crabtree progression",
        "Joey Harrington progression",
        "WR 76 83 progression",
        "TE 80 85 progression",
    ],
)
def test_named_and_unnamed_progression_search(ingested, query) -> None:
    ingestor, _ = ingested
    result = ingestor.search(query)
    assert result["records"] or result["reconciliation"], query


def test_repeated_manifest_is_idempotent(ingested) -> None:
    ingestor, _ = ingested
    before = {
        "sources": len(ingestor.state.sources),
        "records": len(ingestor.state.records),
        "conflicts": len(ingestor.state.conflicts),
        "queue": len(ingestor.state.reconciliation),
    }
    ingestor.ingest(load_manifest(MANIFEST), dry_run=False)
    after = {
        "sources": len(ingestor.state.sources),
        "records": len(ingestor.state.records),
        "conflicts": len(ingestor.state.conflicts),
        "queue": len(ingestor.state.reconciliation),
    }
    assert before == after


def test_manifest_is_deterministic_json() -> None:
    first = load_manifest(MANIFEST)
    second = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert first == second


def test_reconciliation_audit_distinguishes_rediscovered_targets() -> None:
    audit = json.loads((ROOT / "data/evidence/ingestion_audit.json").read_text())
    assert audit["queue_before_manifest_ingestion"] == 8
    assert audit["open_reconciliation_count"] == 20
    assert audit["manifest_ingestion"] == {
        "conflicts_preserved": 1,
        "existing_targets_merged": 1,
        "manifests_ingested": 1,
        "new_progression_recovery_targets": 12,
        "records_promoted": 0,
        "records_staged": 13,
    }
