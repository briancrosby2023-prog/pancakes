from __future__ import annotations

from pathlib import Path

import pytest

from operation_pancake.evidence.knowledge import (
    consensus,
    detect_conflicts,
    meta_vs_pancake,
    normalize_claim,
    normalize_source,
    research_queue,
    threshold_cards,
)
from operation_pancake.production.engine import load_population

ROOT = Path(__file__).resolve().parents[1]
NOW = "2026-08-20T12:00:00+00:00"


def source(
    source_id: str, *, publisher: str | None = None, tier: int = 3, kind: str = "WEB"
) -> dict:
    return normalize_source(
        {
            "source_id": source_id,
            "name": source_id,
            "url": f"https://example.test/{source_id}",
            "tier": tier,
            "source_type": kind,
            "publisher_id": publisher or source_id,
        }
    )


def claim(src: dict, **changes: object) -> dict:
    raw = {
        "subject": "CUT27 QB",
        "predicate": "THP",
        "value": "important",
        "game": "CFB27",
        "source_id": src["source_id"],
        "publication_date": "2026-07-13",
        "evidence_timestamp": NOW,
        "confidence": "MEDIUM",
        "status": "PROVISIONAL",
        "fact_type": "COMPETITIVE PREFERENCE",
        "position": "QB",
        **changes,
    }
    return normalize_claim(raw, {src["source_id"]: src})


def test_current_cut27_is_distinct_from_historical() -> None:
    src = source("S")
    assert claim(src)["game"] == "CFB27"
    assert claim(src, game="CFB26")["game"] == "CFB26"


def test_creator_claim_preserves_source_and_date() -> None:
    row = claim(source("CREATOR"))
    assert row["source_id"] == "CREATOR" and row["publication_date"] == "2026-07-13"


def test_video_timestamp_preserved_when_available() -> None:
    row = claim(source("V", kind="VIDEO"), video_timestamp="03:14")
    assert row["video_timestamp"] == "03:14"


def test_numerical_threshold_requires_explicit_number() -> None:
    src = source("S")
    with pytest.raises(ValueError, match="numerical"):
        claim(src, criterion_type="MINIMUM THRESHOLD", status="STRONG EVIDENCE")


def test_explicit_source_threshold_is_preserved() -> None:
    row = claim(
        source("S"),
        value="85+",
        criterion_type="MINIMUM THRESHOLD",
        threshold=85,
        status="STRONG EVIDENCE",
        scope="SOURCE-SPECIFIC THRESHOLD",
    )
    assert row["threshold"] == 85 and row["scope"] == "SOURCE-SPECIFIC THRESHOLD"


def test_one_source_is_anecdotal() -> None:
    src = source("S")
    assert consensus([claim(src)], {"S": src}, now=NOW)["level"] == "ANECDOTAL"


def test_independent_corroboration_is_counted() -> None:
    a, b = source("A"), source("B")
    rows = [claim(a, value="85+"), claim(b, value="85+")]
    assert consensus(rows, {"A": a, "B": b}, now=NOW)["independent_source_count"] == 2


def test_repost_does_not_create_false_independence() -> None:
    video = source("VIDEO", publisher="creator")
    report = source("REPORT", publisher="creator")
    rows = [claim(video), claim(report)]
    result = consensus(rows, {"VIDEO": video, "REPORT": report}, now=NOW)
    assert result["independent_source_count"] == 1 and result["level"] == "ANECDOTAL"


def test_scheme_specific_threshold_remains_scoped() -> None:
    row = claim(
        source("S"),
        value="85+",
        criterion_type="MINIMUM THRESHOLD",
        threshold=85,
        status="STRONG EVIDENCE",
        scheme="OPTION",
    )
    assert row["scheme"] == "OPTION"


def test_contradictory_thresholds_remain_visible() -> None:
    a, b = source("A"), source("B")
    rows = [
        claim(
            a,
            value="85+",
            threshold=85,
            criterion_type="MINIMUM THRESHOLD",
            status="STRONG EVIDENCE",
        ),
        claim(
            b,
            value="90+",
            threshold=90,
            criterion_type="MINIMUM THRESHOLD",
            status="STRONG EVIDENCE",
        ),
    ]
    assert detect_conflicts(rows)


def test_ability_preference_is_not_ea_fact() -> None:
    row = claim(
        source("S"), predicate="Dot!", value="preferred", criterion_type="ABILITY REQUIREMENT"
    )
    assert row["fact_type"] == "COMPETITIVE PREFERENCE"


def test_ea_fact_is_not_competitive_preference() -> None:
    ea = source("EA", tier=1)
    row = claim(
        ea,
        predicate="ability_mechanic",
        value="Ability EVOs can change abilities",
        status="VERIFIED",
        fact_type="EA FACT",
    )
    assert row["fact_type"] == "EA FACT" and row.get("criterion_type") is None


def test_exact_roster_card_is_not_guessed() -> None:
    observation = {
        "player": "Lanorris Sellers",
        "canonical_card_id": None,
        "identity_status": "UNRESOLVED EXACT VERSION",
    }
    assert observation["canonical_card_id"] is None


def test_historical_threshold_cannot_become_current() -> None:
    historical = claim(
        source("H"),
        game="CFB26",
        value="85+",
        threshold=85,
        criterion_type="MINIMUM THRESHOLD",
        status="STRONG EVIDENCE",
    )
    assert [row for row in [historical] if row["game"] == "CFB27"] == []


def test_supported_threshold_can_query_canonical_cards() -> None:
    card = load_population(ROOT)[0]
    attribute, value = next(iter(card["native_ratings"].items()))
    row = claim(
        source("S"),
        predicate=attribute,
        value=f"{value}+",
        threshold=value,
        criterion_type="MINIMUM THRESHOLD",
        status="STRONG EVIDENCE",
    )
    assert threshold_cards([card], [row])[0]["card_id"] == card["card_id"]


def test_unknown_threshold_creates_no_classification() -> None:
    assert threshold_cards(load_population(ROOT)[:5], []) == []


def test_meta_efficient_requires_supported_criteria() -> None:
    supported_meta: list[dict] = []
    assert threshold_cards(load_population(ROOT)[:5], supported_meta) == []


def test_market_conclusion_remains_separate() -> None:
    card = load_population(ROOT)[0]
    attribute, value = next(iter(card["native_ratings"].items()))
    row = claim(
        source("S"),
        predicate=attribute,
        value=f"{value}+",
        threshold=value,
        criterion_type="MINIMUM THRESHOLD",
        status="STRONG EVIDENCE",
    )
    result = threshold_cards([card], [row])[0]
    assert result["price_status"] == "PRICE EVIDENCE REQUIRED"


def test_meta_comparison_never_changes_coefficients() -> None:
    row = claim(
        source("S"), predicate="throw_release", criterion_type="ANIMATION/TRAIT REQUIREMENT"
    )
    assert meta_vs_pancake([row], {"THP"})[0]["coefficient_changed"] is False


def test_research_queue_and_answer_evidence_are_deterministic() -> None:
    questions = [
        {"question_id": "B", "status": "OPEN", "impact": "META"},
        {"question_id": "A", "status": "OPEN", "impact": "ROSTER"},
        {"question_id": "C", "status": "RESOLVED", "impact": "ROSTER"},
    ]
    assert [row["question_id"] for row in research_queue(questions)] == ["A", "B"]
    row = claim(source("S"))
    assert row["confidence"] == "MEDIUM" and row["provenance"].startswith("https://")
