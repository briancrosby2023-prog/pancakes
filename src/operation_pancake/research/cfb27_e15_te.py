"""Frozen Tight End architecture priors for OP-X-012E.15.

These candidates recover earlier Operation Pancake TE work without promoting
historical Madden weights to CFB27 facts. They are structural/ranking priors;
absolute displayed-OVR calibration must be measured separately on the current
canonical Alpha population.
"""

from __future__ import annotations

from typing import Mapping


# Madden 19 XML-derived TE weights, preserved as historical priors. CFB27 uses
# native archetype names, so the mappings below are hypotheses to test.
M19_POSSESSION_WEIGHTS: tuple[tuple[str, float], ...] = (
    ("SPD", 3), ("ACC", 4), ("AGI", 3), ("STR", 4), ("AWR", 9),
    ("BCV", 1), ("BTK", 2), ("TRK", 1), ("SFA", 2), ("CTH", 10),
    ("CIT", 14), ("SPC", 1), ("RLS", 2), ("SRR", 12), ("MRR", 6),
    ("IBL", 4), ("LBK", 2), ("PBK", 3), ("PBF", 2), ("PBP", 2),
    ("RBK", 5), ("RBF", 4), ("RBP", 4),
)

# Historical ELU carried weight 2 for Vertical Threat, but ELU was unavailable
# in the CFB27 TE evidence. The frozen Pancake v1.1 candidate omitted it and
# renormalized the remaining weights; weighted_score naturally does that.
M19_VERTICAL_WEIGHTS: tuple[tuple[str, float], ...] = (
    ("SPD", 7), ("ACC", 7), ("AGI", 4), ("JMP", 3), ("AWR", 9),
    ("BCV", 2), ("BTK", 3), ("TRK", 1), ("SFA", 2), ("CTH", 11),
    ("CIT", 8), ("SPC", 4), ("RLS", 3), ("SRR", 7), ("MRR", 9),
    ("DRR", 5), ("PBK", 2), ("PBF", 1), ("PBP", 1), ("RBK", 3),
    ("RBF", 3), ("RBP", 3),
)

M19_BLOCKING_WEIGHTS: tuple[tuple[str, float], ...] = (
    ("STR", 6), ("AWR", 9), ("BTK", 2), ("TRK", 1), ("SFA", 2),
    ("CTH", 3), ("CIT", 3), ("SRR", 5), ("MRR", 4), ("IBL", 9),
    ("LBK", 8), ("PBK", 8), ("PBF", 6), ("PBP", 6), ("RBK", 10),
    ("RBF", 9), ("RBP", 9),
)

PRR_VERTICAL_SHARE = 0.71
PRR_POSSESSION_SHARE = 0.29

# Historical validation evidence. These are pairwise ordering metrics, not
# current 512-card exact-OVR accuracy and must never be reported as such.
HISTORICAL_TE_EVIDENCE = {
    "Gritty Possession": {
        "candidate": "TE-MODEL-001 v1.1",
        "blind_pair_correct": 82,
        "blind_pair_total": 83,
        "blind_pair_rate": 82 / 83,
        "status": "HIGH_CONFIDENCE_RANKING_PRIOR",
    },
    "Vertical Threat": {
        "candidate": "TE-MODEL-002 v1.1",
        "blind_pair_correct": 124,
        "blind_pair_total": 133,
        "blind_pair_rate": 124 / 133,
        "status": "PREDICTIVE_BUT_PARTIALLY_FALSIFIED",
    },
    "Physical Route Runner": {
        "candidate": "TE-MODEL-003 v1.1",
        "blind_pair_correct": 365,
        "blind_pair_total": 365,
        "blind_pair_rate": 1.0,
        "status": "HIGH_CONFIDENCE_RANKING_PRIOR",
    },
    "Pure Blocker": {
        "candidate": "TE-MODEL-004 v1.1",
        "blind_pair_correct": 0,
        "blind_pair_total": 0,
        "blind_pair_rate": None,
        "status": "INSUFFICIENT_HISTORICAL_SAMPLE",
    },
}


def weighted_score(ratings: Mapping[str, int], weights: tuple[tuple[str, float], ...]) -> float:
    """Return a normalized structural score for a complete declared prior."""
    missing = [attribute for attribute, _ in weights if attribute not in ratings]
    if missing:
        raise ValueError(f"missing TE candidate attributes: {missing}")
    total_weight = sum(weight for _, weight in weights)
    return sum(float(ratings[attribute]) * weight for attribute, weight in weights) / total_weight


def candidate_score(archetype: str, ratings: Mapping[str, int]) -> float:
    """Score one CFB27 TE against the frozen archetype-specific ranking prior."""
    if archetype == "Gritty Possession":
        return weighted_score(ratings, M19_POSSESSION_WEIGHTS)
    if archetype == "Vertical Threat":
        return weighted_score(ratings, M19_VERTICAL_WEIGHTS)
    if archetype == "Physical Route Runner":
        vertical = weighted_score(ratings, M19_VERTICAL_WEIGHTS)
        possession = weighted_score(ratings, M19_POSSESSION_WEIGHTS)
        return PRR_VERTICAL_SHARE * vertical + PRR_POSSESSION_SHARE * possession
    if archetype == "Pure Blocker":
        return weighted_score(ratings, M19_BLOCKING_WEIGHTS)
    raise ValueError(f"unsupported CFB27 TE archetype: {archetype}")


def research_status(archetype: str) -> dict:
    """Return evidence metadata while keeping historical and current claims separate."""
    if archetype not in HISTORICAL_TE_EVIDENCE:
        raise ValueError(f"unsupported CFB27 TE archetype: {archetype}")
    return {
        **HISTORICAL_TE_EVIDENCE[archetype],
        "archetype": archetype,
        "metric": "CROSS_OVR_PAIR_ORDERING",
        "current_alpha_exact_ovr_accuracy": None,
        "requires_current_alpha_validation": True,
    }
