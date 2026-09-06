"""Small, evidence-first helpers for competitive-meta campaigns."""

from __future__ import annotations

from typing import Any

FINDING_CLASSES = {
    "SUPPORTS 85",
    "SUPPORTS DIFFERENT THRESHOLD",
    "CONTRADICTS THRESHOLD CONCEPT",
    "PREFERENCE WITHOUT NUMBER",
    "IRRELEVANT",
}


def evaluate_hypothesis(findings: list[dict[str, Any]]) -> dict[str, Any]:
    """Count publisher independence and retain all conflicting threshold values."""
    relevant = [row for row in findings if row["classification"] != "IRRELEVANT"]
    if any(row["classification"] not in FINDING_CLASSES for row in findings):
        raise ValueError("unsupported finding classification")
    support = {row["publisher_id"] for row in relevant if row["classification"] == "SUPPORTS 85"}
    contradict = {
        row["publisher_id"]
        for row in relevant
        if row["classification"]
        in {"SUPPORTS DIFFERENT THRESHOLD", "CONTRADICTS THRESHOLD CONCEPT"}
    }
    thresholds = sorted({row["threshold"] for row in relevant if row.get("threshold") is not None})
    if support and contradict:
        verdict = "CONTESTED"
    elif len(support) >= 2:
        verdict = "EMERGING"
    elif support:
        verdict = "SOURCE-SPECIFIC / ANECDOTAL"
    else:
        verdict = "UNSUPPORTED"
    return {
        "supporting_independent_sources": len(support),
        "supporting_publishers": sorted(support),
        "contradicting_sources": len(contradict),
        "contradicting_publishers": sorted(contradict),
        "threshold_values": thresholds,
        "verdict": verdict,
        "findings": findings,
    }


def repeated_card_usage(rosters: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Count exact cards across publishers; usage never manufactures a reason."""
    seen: dict[str, set[str]] = {}
    labels: dict[str, str] = {}
    for roster in rosters:
        publisher = roster["publisher_id"]
        for slot in roster.get("visible_slots", []):
            card_id = slot.get("card_id")
            if card_id and slot.get("exact_card_resolved"):
                seen.setdefault(card_id, set()).add(publisher)
                labels[card_id] = slot.get("player", card_id)
    return [
        {
            "card_id": card_id,
            "player": labels[card_id],
            "independent_usage_count": len(publishers),
            "publishers": sorted(publishers),
            "selection_reason": "UNKNOWN",
            "causal_inference": False,
        }
        for card_id, publishers in sorted(seen.items())
        if len(publishers) > 1
    ]


def deduplicate_questions(questions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deduplicate research questions by normalized text, preserving first provenance."""
    result, keys = [], set()
    for row in questions:
        key = " ".join(row["question"].casefold().split()).rstrip("?")
        if key not in keys:
            keys.add(key)
            result.append(row)
    return result


def threshold_saturation(
    cards: list[dict[str, Any]], criteria: list[dict[str, Any]]
) -> dict[str, Any]:
    """Classify rating excess without declaring value above a threshold worthless."""
    if not criteria:
        return {"status": "INSUFFICIENT GAMEPLAY EVIDENCE", "cards": []}
    rows = []
    for card in cards:
        ratings = card.get("native_ratings", {})
        if all(ratings.get(c["attribute"], -1) >= c["threshold"] for c in criteria):
            rows.append(
                {
                    "card_id": card["card_id"],
                    "classification": "THRESHOLD CLEARED",
                    "excess": {
                        c["attribute"]: ratings[c["attribute"]] - c["threshold"] for c in criteria
                    },
                    "above_threshold_value": "INSUFFICIENT GAMEPLAY EVIDENCE",
                }
            )
    return {"status": "ANALYZED", "cards": rows}


def meta_efficient(
    cards: list[dict[str, Any]], criteria: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    if not criteria:
        return []
    return [
        {
            "card_id": row["card_id"],
            "classification": "META-EFFICIENT",
            "market_status": "PRICE CHECK REQUIRED",
        }
        for row in cards
        if all(
            row.get("native_ratings", {}).get(c["attribute"], -1) >= c["threshold"]
            for c in criteria
        )
    ]
