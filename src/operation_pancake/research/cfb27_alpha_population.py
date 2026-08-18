"""Construct the non-destructive CFB27 Alpha research population.

The persisted acquisition state remains untouched. For Alpha analysis, a
partial CFB.FAN listing card may consume its already-snapshotted structured
rating vector when the *only* disagreement is secondary position nomenclature.
The listing/game position remains canonical and the structured label is kept in
metadata for provenance.
"""

from __future__ import annotations

import json
from pathlib import Path

from operation_pancake.acquisition.cfb_fan_bulk import (
    identity_conflicts,
    parse_bulk_payload,
    promote_record,
    rating_conflicts,
    ratings_from_record,
)


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _structured_records(root: Path) -> dict[str, tuple[dict, str, str]]:
    checkpoint = _load(root / "data/external/cfb_fan_full_vector_checkpoint.json")
    records: dict[str, tuple[dict, str, str]] = {}
    for batch in checkpoint.get("batches", {}).values():
        snapshot = batch.get("snapshot")
        if not snapshot:
            continue
        path = root / snapshot
        if not path.exists():
            continue
        for card_id, record in parse_bulk_payload(path.read_bytes()).items():
            records[card_id] = (record, snapshot, batch.get("retrieved_at") or "UNKNOWN")
    return records


def build_alpha_population(root: Path) -> dict:
    """Return Alpha-effective cards plus an auditable promotion summary."""
    state = _load(root / "data/external/cfb_fan_population_state.json")
    structured = _structured_records(root)
    cards: dict[str, dict] = {}
    promoted = 0
    residual_reasons: dict[str, int] = {}

    for card_id, original in state["cards"].items():
        card = dict(original)
        if card.get("extraction_status") == "COMPLETE":
            cards[card_id] = card
            continue
        payload = structured.get(card_id)
        if payload is None:
            residual_reasons["NO_STRUCTURED_SNAPSHOT"] = residual_reasons.get(
                "NO_STRUCTURED_SNAPSHOT", 0
            ) + 1
            cards[card_id] = card
            continue
        record, snapshot, retrieved_at = payload
        identities = identity_conflicts(card, record)
        ratings = rating_conflicts(card, ratings_from_record(record))
        other_identity = {key: value for key, value in identities.items() if key != "position"}
        if other_identity:
            residual_reasons["OTHER_IDENTITY_CONFLICT"] = residual_reasons.get(
                "OTHER_IDENTITY_CONFLICT", 0
            ) + 1
            cards[card_id] = card
            continue
        if ratings:
            residual_reasons["RATING_CONFLICT"] = residual_reasons.get("RATING_CONFLICT", 0) + 1
            cards[card_id] = card
            continue
        promoted_card = promote_record(card, record, snapshot, retrieved_at)
        structured_position = (record.get("position") or {}).get("abbreviation")
        promoted_card["metadata"] = {
            **promoted_card.get("metadata", {}),
            "alpha_canonical_source": "CFB_FAN",
            "alpha_canonical_taxonomy": "CFB27_GAME",
            "canonical_position": card.get("position"),
            "secondary_structured_position": structured_position,
            "secondary_position_non_blocking": structured_position != card.get("position"),
        }
        promoted_card["position"] = card.get("position")
        cards[card_id] = promoted_card
        promoted += 1

    complete = sum(card.get("extraction_status") == "COMPLETE" for card in cards.values())
    return {
        "cards": cards,
        "summary": {
            "total": len(cards),
            "persisted_complete": sum(
                card.get("extraction_status") == "COMPLETE" for card in state["cards"].values()
            ),
            "alpha_position_only_promotions": promoted,
            "alpha_complete": complete,
            "alpha_partial": len(cards) - complete,
            "residual_reasons": dict(sorted(residual_reasons.items())),
            "canonical_source": "CFB_FAN",
            "canonical_taxonomy": "CFB27_GAME",
            "mutates_persisted_state": False,
        },
    }
