from __future__ import annotations

from pathlib import Path

import pytest

from operation_pancake.evidence.index import EvidenceIndex
from operation_pancake.evidence.knowledge import (
    apply_release_knowledge,
    consensus,
    detect_conflicts,
    is_stale,
    meta_vs_pancake,
    normalize_claim,
    normalize_source,
    register_with_evidence_index,
    research_queue,
    resolve_question,
    supersede,
    threshold_cards,
)
from operation_pancake.production.engine import load_population

ROOT = Path(__file__).resolve().parents[1]
NOW = "2026-08-20T12:00:00+00:00"


def source(
    source_id: str = "EA", tier: int = 1, source_type: str = "WEB", publisher: str | None = None
) -> dict:
    return normalize_source(
        {
            "source_id": source_id,
            "name": source_id,
            "url": f"https://example.test/{source_id}",
            "tier": tier,
            "source_type": source_type,
            "publisher_id": publisher or source_id,
        }
    )


def claim(src: dict, **changes: object) -> dict:
    raw = {
        "subject": "Season 1",
        "predicate": "release_method",
        "value": "FIELD PASS / SEASON REWARD",
        "game": "CFB27",
        "source_id": src["source_id"],
        "evidence_timestamp": "2026-08-20T00:00:00+00:00",
        "status": "VERIFIED",
        "confidence": "HIGH",
        "fact_type": "EA FACT",
        **changes,
    }
    return normalize_claim(raw, {src["source_id"]: src})


def test_primary_ea_claim_keeps_provenance() -> None:
    row = claim(source())
    assert row["source_tier"] == 1 and row["provenance"].startswith("https://")


def test_cfb_fan_claim_is_independent() -> None:
    cfb = source("CFB", 2)
    row = claim(cfb, status="STRONG EVIDENCE", fact_type="OBSERVATION")
    assert row["source_id"] == "CFB" and row["source_tier"] == 2


def test_creator_opinion_cannot_become_ea_fact() -> None:
    creator = source("CREATOR", 3)
    with pytest.raises(ValueError, match="cannot become"):
        claim(creator)


def test_video_claim_preserves_timestamp() -> None:
    video = source("VIDEO", 3, "VIDEO")
    row = claim(video, status="PROVISIONAL", fact_type="OPINION", video_timestamp="04:05")
    assert row["video_timestamp"] == "04:05"


def test_nonvideo_rejects_video_timestamp() -> None:
    with pytest.raises(ValueError, match="video"):
        claim(source(), video_timestamp="00:10")


def test_conflicting_claims_remain_visible() -> None:
    a, b = source("A", 2), source("B", 2)
    rows = [
        claim(a, status="STRONG EVIDENCE", fact_type="OBSERVATION"),
        claim(b, value="PACKS", status="STRONG EVIDENCE", fact_type="OBSERVATION"),
    ]
    assert len(detect_conflicts(rows)) == 1
    assert consensus(rows, {"A": a, "B": b}, now=NOW)["level"] == "CONTESTED"


def test_newer_verified_can_supersede_older() -> None:
    src = source()
    old = claim(src, claim_id="old")
    new = claim(src, claim_id="new", evidence_timestamp="2026-08-20T01:00:00+00:00")
    rows = supersede([old, new], "old", "new")
    assert next(row for row in rows if row["claim_id"] == "old")["status"] == "SUPERSEDED"


def test_historical_evidence_is_stale() -> None:
    src = source("HIST", 1)
    row = claim(src, game="CFB26", evidence_timestamp="2025-08-01T00:00:00+00:00")
    assert is_stale(row, now=NOW)


def test_unknown_question_creates_open_request() -> None:
    q = {
        "question_id": "Q1",
        "question": "How?",
        "subject": "card",
        "predicate": "release_method",
        "impact": "RELEASE",
    }
    result = resolve_question(q, [], now=NOW)
    assert result["status"] == "OPEN" and result["answer"] == "UNKNOWN"


def test_resolved_evidence_closes_request_and_exposes_confidence() -> None:
    row = claim(source())
    q = {
        "question_id": "Q1",
        "question": "How?",
        "subject": "Season 1",
        "predicate": "release_method",
    }
    result = resolve_question(q, [row], now=NOW)
    assert result["status"] == "RESOLVED" and result["confidence"] == "HIGH"


def test_threshold_requires_supported_status() -> None:
    src = source("EXPERT", 3)
    with pytest.raises(ValueError, match="supporting evidence"):
        claim(
            src,
            predicate="THP",
            value="minimum 90",
            status="PROVISIONAL",
            fact_type="OPINION",
            criterion_type="MINIMUM THRESHOLD",
            threshold=90,
        )


def test_one_creator_is_anecdotal() -> None:
    src = source("ONE", 3)
    row = claim(src, status="PROVISIONAL", fact_type="OPINION")
    assert consensus([row], {"ONE": src}, now=NOW)["level"] == "ANECDOTAL"


def test_independent_sources_increase_consensus() -> None:
    sources = {key: source(key, 3) for key in ("A", "B", "C")}
    rows = [claim(src, status="PROVISIONAL", fact_type="OPINION") for src in sources.values()]
    assert consensus(rows, sources, now=NOW)["level"] == "COMMON"


def test_scheme_criterion_remains_scheme_specific() -> None:
    src = source("EXPERT", 3)
    row = claim(
        src,
        predicate="SPD",
        value="speed matters",
        status="PROVISIONAL",
        fact_type="OPINION",
        criterion_type="SCHEME REQUIREMENT",
        scheme="OPTION",
    )
    assert (
        row["scheme"] == "OPTION"
        and meta_vs_pancake([row], {"SPD"})[0]["classification"] == "SCHEME-SPECIFIC DIFFERENCE"
    )


def test_meta_never_changes_coefficients() -> None:
    src = source("EXPERT", 3)
    row = claim(
        src,
        predicate="THP",
        value="important",
        status="PROVISIONAL",
        fact_type="OPINION",
        criterion_type="MUST HAVE",
    )
    assert meta_vs_pancake([row], {"THP"})[0]["coefficient_changed"] is False


def test_supported_threshold_card_search_works() -> None:
    card = load_population(ROOT)[0]
    attribute, value = next(iter(card["native_ratings"].items()))
    src = source()
    criterion = claim(
        src,
        predicate=attribute,
        value=f"minimum {value}",
        criterion_type="MINIMUM THRESHOLD",
        threshold=value,
    )
    assert threshold_cards([card], [criterion])[0]["card_id"] == card["card_id"]


def test_unsupported_threshold_produces_no_classification() -> None:
    assert threshold_cards(load_population(ROOT)[:3], []) == []


def test_reveal_consumes_supported_release_knowledge() -> None:
    row = claim(source())
    updated = apply_release_knowledge({"release_method": "UNKNOWN"}, row)
    assert updated["release_method"] == "FIELD PASS / SEASON REWARD"
    assert updated["knowledge_claim_ids"] == [row["claim_id"]]


def test_existing_evidence_index_is_extended() -> None:
    src = source()
    row = claim(src)
    index = EvidenceIndex()
    register_with_evidence_index(index, [src], [row])
    assert ("knowledge_claim", row["claim_id"]) in index.records
    assert index.record_provenance("knowledge_claim", row["claim_id"])["sources"]


def test_research_queue_is_deterministic() -> None:
    questions = [
        {"question_id": "B", "status": "OPEN", "impact": "META"},
        {"question_id": "A", "status": "OPEN", "impact": "BUY/SELL"},
        {"question_id": "C", "status": "RESOLVED", "impact": "BUY/SELL"},
    ]
    assert [row["question_id"] for row in research_queue(questions)] == ["A", "B"]
