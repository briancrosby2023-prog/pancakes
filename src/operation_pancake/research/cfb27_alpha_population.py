"""Construct the non-destructive CFB27 Alpha research population.

The persisted acquisition state remains untouched. Alpha uses CFB27 game
terminology. Historical structured-endpoint labels are retained as provenance
but never define the Alpha research position.
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

# CFB.FAN's older structured ``position`` field used Madden-style base labels
# for these slots while CFB27/game-facing terminology is MIKE/LEDG/REDG.
# SAM and WILL already arrive natively and require no translation.
LEGACY_STRUCTURED_TO_CFB27 = {"MLB": "MIKE", "LE": "LEDG", "RE": "REDG"}


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _bare_card_id(card_id: str) -> str:
    return card_id.split(":", 1)[-1]


def _alpha_position(position: str | None) -> str | None:
    return LEGACY_STRUCTURED_TO_CFB27.get(position, position)


def _canonicalize_complete_card(original: dict) -> dict:
    """Return an Alpha-only copy using CFB27 terminology with provenance."""
    card = dict(original)
    source_position = card.get("position")
    canonical = _alpha_position(source_position)
    if canonical != source_position:
        card["position"] = canonical
        card["metadata"] = {
            **(card.get("metadata") or {}),
            "alpha_canonical_source": "CFB_FAN",
            "alpha_canonical_taxonomy": "CFB27_GAME",
            "canonical_position": canonical,
            "secondary_structured_position": source_position,
            "secondary_position_non_blocking": True,
        }
    return card


def _structured_records(
    root: Path, target_ids: set[str]
) -> dict[str, tuple[dict, str, str]]:
    """Load only structured snapshots capable of resolving target cards.

    Persisted population keys are source-qualified (``CFB_FAN:27-*``), while
    the acquisition checkpoint and bulk parser use endpoint IDs (``27-*``).
    Reconcile those namespaces explicitly.
    """
    checkpoint = _load(root / "data/external/cfb_fan_full_vector_checkpoint.json")
    target_by_bare = {_bare_card_id(card_id): card_id for card_id in target_ids}
    bare_targets = set(target_by_bare)
    records: dict[str, tuple[dict, str, str]] = {}
    for batch in checkpoint.get("batches", {}).values():
        requested = set(batch.get("requested_ids", ()))
        if bare_targets.isdisjoint(requested):
            continue
        snapshot = batch.get("snapshot")
        if not snapshot:
            continue
        path = root / snapshot
        if not path.exists():
            continue
        for bare_id, record in parse_bulk_payload(path.read_bytes()).items():
            persisted_id = target_by_bare.get(bare_id)
            if persisted_id is not None:
                records[persisted_id] = (
                    record,
                    snapshot,
                    batch.get("retrieved_at") or "UNKNOWN",
                )
    return records


def build_alpha_population(root: Path) -> dict:
    """Return Alpha-effective cards plus an auditable promotion summary."""
    state = _load(root / "data/external/cfb_fan_population_state.json")
    target_ids = {
        card_id
        for card_id, card in state["cards"].items()
        if card.get("extraction_status") != "COMPLETE"
    }
    structured = _structured_records(root, target_ids)
    cards: dict[str, dict] = {}
    promoted = 0
    canonicalized_complete = 0
    residual_reasons: dict[str, int] = {}

    for card_id, original in state["cards"].items():
        card = dict(original)
        if card.get("extraction_status") == "COMPLETE":
            canonical = _canonicalize_complete_card(card)
            canonicalized_complete += canonical.get("position") != card.get("position")
            cards[card_id] = canonical
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
            "alpha_complete_position_canonicalizations": canonicalized_complete,
            "alpha_complete": complete,
            "alpha_partial": len(cards) - complete,
            "residual_reasons": dict(sorted(residual_reasons.items())),
            "canonical_source": "CFB_FAN",
            "canonical_taxonomy": "CFB27_GAME",
            "mutates_persisted_state": False,
        },
    }
