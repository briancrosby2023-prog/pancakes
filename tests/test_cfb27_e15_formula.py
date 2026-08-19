from operation_pancake.research.cfb27_e15_formula import (
    LinearFormulaCandidate,
    classify_candidate,
    compare_rounding_rules,
    rank_candidates,
    score_candidate,
)


def _cards():
    return [
        {
            "external_card_id": f"C-{index:02d}",
            "position": "C",
            "archetype": "Test",
            "overall": value,
            "displayed_ratings": {"AWR": value, "STR": value},
        }
        for index, value in enumerate(range(70, 90))
    ]


def test_exact_candidate_scores_and_classifies_exact():
    candidate = LinearFormulaCandidate("equal", (("AWR", 1), ("STR", 1)))
    result = score_candidate(candidate, _cards(), position="C", archetype="Test")
    assert result["scored_cards"] == 20
    assert result["exact_match_count"] == 20
    assert result["exact_match_rate"] == 1.0
    assert result["mean_absolute_error"] == 0.0
    assert classify_candidate(result) == "EXACT"


def test_missing_candidate_attribute_is_preserved_as_skip():
    cards = _cards()[:1]
    cards[0]["displayed_ratings"].pop("STR")
    candidate = LinearFormulaCandidate("equal", (("AWR", 1), ("STR", 1)))
    result = score_candidate(candidate, cards, position="C", archetype="Test")
    assert result["scored_cards"] == 0
    assert result["skipped_cards"] == [{"card_id": "C-00", "missing_attributes": ["STR"]}]
    assert classify_candidate(result) == "UNDERDETERMINED"


def test_rounding_rules_are_compared_without_changing_weights():
    cards = [
        {
            "external_card_id": "C-1",
            "position": "C",
            "archetype": "Test",
            "overall": 71,
            "displayed_ratings": {"AWR": 70, "STR": 71},
        }
    ]
    candidate = LinearFormulaCandidate("half", (("AWR", 1), ("STR", 1)))
    results = compare_rounding_rules(candidate, cards, position="C", archetype="Test")
    by_rule = {row["rounding"]: row for row in results}
    assert by_rule["HALF_UP"]["exact_match_count"] == 1
    assert by_rule["CEIL"]["exact_match_count"] == 1
    assert by_rule["FLOOR"]["exact_match_count"] == 0


def test_contradiction_rejects_otherwise_exact_candidate():
    candidate = LinearFormulaCandidate("equal", (("AWR", 1), ("STR", 1)))
    result = score_candidate(candidate, _cards(), position="C", archetype="Test")
    assert classify_candidate(result, contradictions=1) == "REJECTED"


def test_candidate_ranking_is_deterministic():
    rows = [
        {"candidate": "b", "exact_match_rate": 0.9, "mean_absolute_error": 0.1, "maximum_absolute_error": 1},
        {"candidate": "a", "exact_match_rate": 0.9, "mean_absolute_error": 0.1, "maximum_absolute_error": 1},
        {"candidate": "best", "exact_match_rate": 1.0, "mean_absolute_error": 0.0, "maximum_absolute_error": 0},
    ]
    assert [row["candidate"] for row in rank_candidates(rows)] == ["best", "a", "b"]
