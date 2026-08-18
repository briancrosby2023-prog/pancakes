"""Forensic classification for CFB27 structured-ingestion position conflicts.

The audit is deliberately non-destructive: source labels are preserved and no
position aliases are applied to canonical records.  It exists to determine
whether an alias is scientifically justified before normalization is allowed.
"""

from __future__ import annotations

from collections import Counter


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
    """Classify evidence without declaring any taxonomy pair equivalent."""
    identities = conflict.get("identity_conflicts", {})
    ratings = conflict.get("rating_conflicts", {})
    pair = _pair(conflict)
    if pair is None:
        return "NON_POSITION_CONFLICT"
    other_identity = {key: value for key, value in identities.items() if key != "position"}
    if other_identity or ratings:
        return "POSITION_PLUS_OTHER_CONFLICT"
    return "POSITION_ONLY_ALIAS_CANDIDATE"


def audit_position_conflicts(state: dict) -> dict:
    """Summarize OP-X-013 conflicts while preserving every original label."""
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
        {"existing": existing, "structured": structured, "count": count}
        for (existing, structured), count in sorted(
            pairs.items(), key=lambda item: (-item[1], item[0][0], item[0][1])
        )
    ]
    position_only = classes["POSITION_ONLY_ALIAS_CANDIDATE"]
    return {
        "total_op_x_013_conflicts": len(conflicts),
        "position_conflict_cards": position_conflict_cards,
        "classification_counts": dict(sorted(classes.items())),
        "position_pairs": pair_rows,
        "other_identity_conflict_fields": dict(sorted(other_identity_fields.items())),
        "rating_conflict_cards": rating_conflict_cards,
        "position_only_alias_candidates": position_only,
        "all_conflicts_position_only": bool(conflicts) and position_only == len(conflicts),
        "normalization_decision": "PRESERVE_SOURCE_LABELS_PENDING_REVIEW",
        "evidence_rule": (
            "A position-only mismatch is an alias candidate, not proof of equivalence; "
            "canonical normalization requires pair-level source review."
        ),
    }
