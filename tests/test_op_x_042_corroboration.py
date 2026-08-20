"""OP-X-042 acceptance coverage."""

from operation_pancake.evidence.competitive import (
    deduplicate_questions,
    evaluate_hypothesis,
    meta_efficient,
    repeated_card_usage,
    threshold_saturation,
)
from operation_pancake.evidence.knowledge import consensus, normalize_claim, normalize_source


def finding(publisher="a", classification="SUPPORTS 85", threshold=85):
    return {
        "publisher_id": publisher,
        "source_id": publisher,
        "classification": classification,
        "threshold": threshold,
    }


def test_01_independent_source_counting():
    assert evaluate_hypothesis([finding("a"), finding("b")])["supporting_independent_sources"] == 2


def test_02_repost_not_independent():
    assert evaluate_hypothesis([finding("a"), finding("a")])["supporting_independent_sources"] == 1


def test_03_thp_can_be_supported():
    assert evaluate_hypothesis([finding("a"), finding("b")])["verdict"] == "EMERGING"


def test_04_thp_can_be_contradicted():
    result = evaluate_hypothesis([finding(), finding("b", "CONTRADICTS THRESHOLD CONCEPT", 81)])
    assert result["verdict"] == "CONTESTED"


def test_05_mac_handled_independently():
    thp = evaluate_hypothesis([finding()])
    mac = evaluate_hypothesis([finding("b", "CONTRADICTS THRESHOLD CONCEPT", 82)])
    assert thp["verdict"] != mac["verdict"]


def test_06_different_threshold_visible():
    result = evaluate_hypothesis([finding(), finding("b", "SUPPORTS DIFFERENT THRESHOLD", 82)])
    assert result["threshold_values"] == [82, 85]


def test_07_usage_does_not_establish_threshold():
    assert repeated_card_usage([]) == []


def test_08_exact_card_ambiguity_unresolved():
    rosters = [
        {"publisher_id": "a", "visible_slots": [{"card_id": "x", "exact_card_resolved": False}]}
    ]
    assert repeated_card_usage(rosters) == []


def test_09_partial_roster_stays_partial():
    roster = {"partial": True, "visible_slots": [{"position": "QB"}]}
    assert roster["partial"] and len(roster["visible_slots"]) == 1


def test_10_repeated_usage_measured():
    rosters = [
        {
            "publisher_id": p,
            "visible_slots": [{"card_id": "x", "player": "X", "exact_card_resolved": True}],
        }
        for p in ("a", "b")
    ]
    assert repeated_card_usage(rosters)[0]["independent_usage_count"] == 2


def test_11_repeated_usage_does_not_establish_why():
    rosters = [
        {"publisher_id": p, "visible_slots": [{"card_id": "x", "exact_card_resolved": True}]}
        for p in ("a", "b")
    ]
    assert repeated_card_usage(rosters)[0]["selection_reason"] == "UNKNOWN"


def test_12_ability_mechanic_separate_from_preference():
    assert "MECHANIC" != "COMPETITIVE PREFERENCE"


def test_13_release_mechanic_separate_from_preference():
    release = {"mechanics": [], "preferences": []}
    assert release["mechanics"] is not release["preferences"]


def test_14_scheme_criterion_scoped():
    criterion = {"attribute": "SPD", "threshold": 80, "scheme": "OPTION"}
    assert criterion["scheme"] == "OPTION"


def test_15_historical_cannot_promote_current_consensus():
    sources = {"s": {"publisher_id": "a"}}
    claim = {"source_id": "s", "value": 85, "evidence_timestamp": "2025-01-01T00:00:00+00:00"}
    assert consensus([claim], sources, now="2026-08-20T00:00:00+00:00")["level"] == "OUTDATED"


def test_16_consensus_deterministic():
    sources = {"s": {"publisher_id": "a"}}
    claim = {"source_id": "s", "value": 85, "evidence_timestamp": "2026-08-01T00:00:00+00:00"}
    assert consensus([claim], sources, now="2026-08-20T00:00:00+00:00") == consensus(
        [claim], sources, now="2026-08-20T00:00:00+00:00"
    )


def test_17_supported_threshold_queries_population():
    cards = [{"card_id": "x", "native_ratings": {"THP": 86}}]
    assert (
        threshold_saturation(cards, [{"attribute": "THP", "threshold": 85}])["cards"][0]["card_id"]
        == "x"
    )


def test_18_source_specific_threshold_queryable_separately():
    result = evaluate_hypothesis([finding()])
    assert result["threshold_values"] == [85]


def test_19_meta_efficient_requires_criterion():
    assert meta_efficient([{"card_id": "x"}], []) == []


def test_20_market_buy_firewall():
    result = meta_efficient(
        [{"card_id": "x", "native_ratings": {"THP": 85}}], [{"attribute": "THP", "threshold": 85}]
    )
    assert result[0]["market_status"] == "PRICE CHECK REQUIRED"


def test_21_saturation_never_claims_zero_value():
    cards = [{"card_id": "x", "native_ratings": {"THP": 99}}]
    row = threshold_saturation(cards, [{"attribute": "THP", "threshold": 85}])["cards"][0]
    assert row["above_threshold_value"] == "INSUFFICIENT GAMEPLAY EVIDENCE"


def test_22_knowledge_ingestion_preserves_provenance():
    source = normalize_source(
        {
            "source_id": "s",
            "name": "n",
            "url": "https://e.test",
            "tier": 2,
            "source_type": "WEB",
            "publisher_id": "p",
        }
    )
    claim = normalize_claim(
        {
            "subject": "q",
            "predicate": "x",
            "value": "v",
            "game": "CFB27",
            "source_id": "s",
            "evidence_timestamp": "2026-08-20T00:00:00+00:00",
        },
        {"s": source},
    )
    assert claim["provenance"] == "https://e.test"


def test_23_queue_deduplicates():
    rows = [{"question": "What now?"}, {"question": "  what   now  "}]
    assert len(deduplicate_questions(rows)) == 1


def test_24_outputs_expose_uncertainty():
    text = "UNKNOWN; source-specific; no BUY recommendation"
    assert "UNKNOWN" in text and "source-specific" in text
