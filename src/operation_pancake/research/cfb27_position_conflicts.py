"""Forensic classification for CFB27 structured-ingestion position labels.

Operation Pancake Alpha treats the CFB27/CFB.FAN listing label as canonical.
Structured/secondary position nomenclature is retained as provenance but does
not by itself block a valid CFB.FAN rating vector.
"""

from __future__ import annotations

from collections import Counter

from operation_pancake.research.cfb27_alpha_policy import alpha_policy_metadata


def _pair(conflict: dict) -> tuple[str, str] | None:
    position = conflict.get("identity_conflicts", {}).get("position")
    if not isinstance(position, dict):
        return None
    existing = position.get("existing")
    structured = position.get("structured")
    if not isinstance(existing, str) or not isinstance(structured, str):
        return None
    return existing, structured


def classify_conflict(conflict: dict) -> str:
    """Classify conflicts under the Alpha canonical-source policy."""
    identities = conflict.get("identity_conflicts", {})
    ratings = conflict.get("rating_conflicts", {})
    pair = _pair(conflict)
    if pair is None:
        return "NON_POSITION_CONFLICT"
    other_identity = {key: value for key, value in identities.items() if key != "position"}
    if other_identity or ratings:
        return "POSITION_PLUS_OTHER_CONFLICT"
    return "SECONDARY_POSITION_NON_BLOCKING"


def audit_position_conflicts(state: dict) -> dict:
    """Summarize OP-X-013 conflicts without rewriting original evidence."""
    conflicts = {
        key: value
        for key, value in state.get("conflicts", {}).items()
        if key.startswith("OP-X-013:")
    }
    classes: Counter[str] = Counter()
    pairs: Counter[tuple[str, str]] = Counter()
    other_identity_fields: Counter[str] = Counter()
    rating_conflict_cards = 0
    position_conflict_cards = 0

    for conflict in conflicts.values():
        classes[classify_conflict(conflict)] += 1
        pair = _pair(conflict)
        if pair is not None:
            position_conflict_cards += 1
            pairs[pair] += 1
        identities = conflict.get("identity_conflicts", {})
        other_identity_fields.update(key for key in identities if key != "position")
        if conflict.get("rating_conflicts"):
            rating_conflict_cards += 1

    pair_rows = [
        {"canonical": existing, "secondary": structured, "count": count}
        for (existing, structured), count in sorted(
            pairs.items(), key=lambda item: (-item[1], item[0][0], item[0][1])
        )
    ]
    non_blocking = classes["SECONDARY_POSITION_NON_BLOCKING"]
    return {
        "alpha_policy": alpha_policy_metadata(),
        "total_op_x_013_conflicts": len(conflicts),
        "position_conflict_cards": position_conflict_cards,
        "classification_counts": dict(sorted(classes.items())),
        "position_pairs": pair_rows,
        "other_identity_conflict_fields": dict(sorted(other_identity_fields.items())),
        "rating_conflict_cards": rating_conflict_cards,
        "secondary_position_non_blocking": non_blocking,
        "all_conflicts_position_only": bool(conflicts) and non_blocking == len(conflicts),
        "alpha_decision": "CFB_FAN_CFB27_POSITION_CANONICAL",
        "evidence_rule": (
            "Preserve the CFB.FAN/CFB27 listing position as canonical; retain a different "
            "structured position label as provenance only. Other identity or rating conflicts "
            "remain blocking and must be investigated separately."
        ),
    }
