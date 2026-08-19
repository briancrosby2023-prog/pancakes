import pytest

from operation_pancake.research.cfb27_e15_te import (
    HISTORICAL_TE_EVIDENCE,
    M19_POSSESSION_WEIGHTS,
    M19_VERTICAL_WEIGHTS,
    candidate_score,
    research_status,
    weighted_score,
)


def _ratings_for(*weight_sets):
    attributes = {attribute for weights in weight_sets for attribute, _ in weights}
    return {attribute: 80 for attribute in attributes}


def test_weighted_score_is_normalized():
    ratings = _ratings_for(M19_POSSESSION_WEIGHTS)
    assert weighted_score(ratings, M19_POSSESSION_WEIGHTS) == 80


def test_prr_blend_is_between_frozen_parent_scores():
    ratings = _ratings_for(M19_POSSESSION_WEIGHTS, M19_VERTICAL_WEIGHTS)
    ratings["CIT"] = 95
    ratings["SPD"] = 90
    possession = candidate_score("Gritty Possession", ratings)
    vertical = candidate_score("Vertical Threat", ratings)
    physical = candidate_score("Physical Route Runner", ratings)
    assert min(possession, vertical) <= physical <= max(possession, vertical)


def test_historical_metrics_are_not_promoted_to_current_exact_accuracy():
    status = research_status("Gritty Possession")
    assert status["metric"] == "CROSS_OVR_PAIR_ORDERING"
    assert status["blind_pair_correct"] == 82
    assert status["blind_pair_total"] == 83
    assert status["current_alpha_exact_ovr_accuracy"] is None
    assert status["requires_current_alpha_validation"] is True


def test_vertical_prior_preserves_known_partial_falsification():
    status = research_status("Vertical Threat")
    assert status["blind_pair_correct"] == 124
    assert status["blind_pair_total"] == 133
    assert status["status"] == "PREDICTIVE_BUT_PARTIALLY_FALSIFIED"


def test_pure_blocker_remains_insufficient_historical_sample():
    status = research_status("Pure Blocker")
    assert status["blind_pair_rate"] is None
    assert status["status"] == "INSUFFICIENT_HISTORICAL_SAMPLE"


def test_unknown_archetype_is_not_silently_mapped():
    with pytest.raises(ValueError, match="unsupported CFB27 TE archetype"):
        research_status("Possession")


def test_missing_rating_is_explicit():
    ratings = _ratings_for(M19_POSSESSION_WEIGHTS)
    ratings.pop("CIT")
    with pytest.raises(ValueError, match="missing TE candidate attributes"):
        candidate_score("Gritty Possession", ratings)


def test_historical_registry_covers_four_observed_te_archetypes():
    assert set(HISTORICAL_TE_EVIDENCE) == {
        "Gritty Possession",
        "Vertical Threat",
        "Physical Route Runner",
        "Pure Blocker",
    }
