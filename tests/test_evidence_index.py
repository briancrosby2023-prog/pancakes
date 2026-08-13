from __future__ import annotations

import json
from pathlib import Path

import pytest

from operation_pancake.evidence.catalog import build_evidence_index
from operation_pancake.evidence.index import EvidenceIndex
from operation_pancake.evidence.models import ExternalSourceAdapter, SourceRecord, StagedRecord

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def index() -> EvidenceIndex:
    return build_evidence_index(ROOT)


def test_catalog_registers_known_center_partial_separately(index: EvidenceIndex) -> None:
    source = index.sources["SRC-C-RAW-003"]
    assert source.original_filename == "raw str centers2(2).pdf"
    assert source.item_count == 14
    assert source.extraction_status == "PARTIAL"
    assert source.category == "CUT_CENTER_CARDS"
    assert source.source_id != "SRC-RATE-001"


def test_all_canonical_cards_have_source_links(index: EvidenceIndex) -> None:
    audit = index.audit()
    assert audit["canonical_record_count"] == 145
    assert audit["canonical_records_missing_source_provenance"] == []


def test_card_reverse_lookup_includes_field_provenance(index: EvidenceIndex) -> None:
    result = index.record_provenance("player_card", "QB-0074")
    assert result["sources"]
    assert {field["field_name"] for field in result["fields"]} >= {"player", "overall", "THP"}
    assert result["research_artifacts"]


def test_source_reverse_lookup_exposes_unprocessed_work(index: EvidenceIndex) -> None:
    result = index.source_impact("SRC-C-RAW-003")
    assert result["unprocessed"]
    assert result["queue"][0]["status"] == "OPEN"


def test_structured_search_is_deterministic(index: EvidenceIndex) -> None:
    first = index.search("raw str centers2(2)")
    assert first == index.search("raw str centers2(2)")
    assert "SRC-C-RAW-003" in {item["source_id"] for item in first["sources"]}
    assert index.search(position="QB")["sources"]
    assert index.search("Brady Small")["records"]


def test_research_artifacts_are_indexed_without_becoming_canonical(index: EvidenceIndex) -> None:
    artifacts = [r for (kind, _), r in index.records.items() if kind == "research_artifact"]
    assert artifacts
    assert all(item["research_only"] and not item["canonical"] for item in artifacts)


def test_progression_evidence_preserves_card_sources(index: EvidenceIndex) -> None:
    progressions = [
        record_id for kind, record_id in index.records if kind == "progression_evidence"
    ]
    assert progressions
    result = index.record_provenance("progression_evidence", progressions[0])
    assert len(result["sources"]) == 2


def test_staging_cannot_silently_promote_or_overwrite() -> None:
    index = EvidenceIndex()
    index.add_source(SourceRecord("SRC-X", "name", "file", "API", "external", "EXTERNAL_WEB"))
    staged = StagedRecord("STG-1", "SRC-X", None, None, {}, {}, "NEEDS_REVIEW")
    index.stage(staged)
    with pytest.raises(ValueError, match="already exists"):
        index.stage(staged)
    promoted = StagedRecord("STG-2", "SRC-X", None, None, {}, {}, "VALID", promoted=True)
    with pytest.raises(ValueError, match="cannot already"):
        index.stage(promoted)


def test_staging_rejects_unindexed_sources() -> None:
    with pytest.raises(KeyError, match="Unknown source"):
        EvidenceIndex().stage(StagedRecord("STG-1", "MISSING", None, None, {}, {}, "NEW"))


def test_external_adapter_contract_is_staging_only() -> None:
    class Adapter(ExternalSourceAdapter):
        source_type = "API"

        def stage(self, raw: dict[str, object], retrieved_at: str) -> StagedRecord:
            return StagedRecord("STG-API-1", "SRC-API", "42", retrieved_at, raw, {}, "NEW")

    result = Adapter().stage({"overall": 80}, "2026-08-13T00:00:00Z")
    assert result.promoted is False
    assert result.raw_values == {"overall": 80}


def test_conflicts_preserve_both_values() -> None:
    assert EvidenceIndex.conflicts({"overall": 80}, {"overall": 79}) == {"overall": (79, 80)}


def test_partial_source_requires_remaining_description() -> None:
    with pytest.raises(ValueError, match="must state"):
        SourceRecord(
            "S", "name", "file", "PDF", "cards", "LOCAL_REPOSITORY", extraction_status="PARTIAL"
        )


def test_generated_artifacts_are_deterministic(tmp_path: Path) -> None:
    # Build twice from the repository; compare serialization without writing into canonical data.
    first = build_evidence_index(ROOT).as_dict()
    second = build_evidence_index(ROOT).as_dict()
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)


def test_committed_artifacts_match_generator(index: EvidenceIndex) -> None:
    expected = json.loads(json.dumps(index.as_dict()))
    assert json.loads((ROOT / "data/evidence/source_index.json").read_text()) == expected
    assert json.loads((ROOT / "data/evidence/ingestion_audit.json").read_text()) == index.audit()
