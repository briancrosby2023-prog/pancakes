"""Run the bounded OP-X-013 validation and partial-card pilot."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from operation_pancake.acquisition.cfb_fan_bulk import (
    ATTRIBUTE_ABBREVIATIONS,
    ENDPOINT,
    CfbFanBulkAdapter,
    identity_conflicts,
    priority_key,
    promote_record,
    rating_conflicts,
    ratings_from_record,
)


def _save(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def validation_sample(cards: list[dict], size: int = 20) -> list[dict]:
    """Select a deterministic sample spanning positions before filling by OVR."""
    chosen = []
    seen_positions = set()
    ordered = sorted(
        cards,
        key=lambda row: (
            row.get("position", ""),
            -(row.get("overall") or 0),
            row["external_card_id"],
        ),
    )
    for card in ordered:
        if card.get("position") not in seen_positions:
            chosen.append(card)
            seen_positions.add(card.get("position"))
        if len(chosen) == size:
            return chosen
    for card in sorted(
        cards, key=lambda row: (-(row.get("overall") or 0), row["external_card_id"])
    ):
        if card not in chosen:
            chosen.append(card)
        if len(chosen) == size:
            break
    return chosen


def snapshot_for(checkpoint: dict, external_id: str) -> str:
    for batch in checkpoint["batches"].values():
        if external_id in batch["returned_ids"]:
            return batch["snapshot"]
    raise KeyError(external_id)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--pilot-size",
        type=int,
        default=30,
        help="Bounded count of currently partial records to attempt (OP-X-013 used 30).",
    )
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    state_path = root / "data/external/cfb_fan_population_state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    cards = list(state["cards"].values())
    full = [card for card in cards if card.get("extraction_status") == "COMPLETE"]
    partial = [card for card in cards if card.get("extraction_status") != "COMPLETE"]
    sample = validation_sample(full)
    pilot = sorted(partial, key=priority_key)[: args.pilot_size]
    requested = [card["external_card_id"] for card in sample + pilot]
    retrieved_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    checkpoint, records = CfbFanBulkAdapter(root).acquire(requested, retrieved_at)

    validation = []
    for card in sample:
        external_id = card["external_card_id"]
        record = records.get(external_id)
        if record is None:
            validation.append({"external_card_id": external_id, "status": "MISSING_FROM_RESPONSE"})
            continue
        identities = identity_conflicts(card, record)
        ratings = rating_conflicts(card, ratings_from_record(record))
        validation.append(
            {
                "external_card_id": external_id,
                "player_name": card["player_name"],
                "position": card["position"],
                "overall": card["overall"],
                "program": card["program"],
                "archetype": card["archetype"],
                "existing_fields": len(card.get("displayed_ratings", {})),
                "structured_fields": len(ratings_from_record(record)),
                "identity_conflicts": identities,
                "rating_conflicts": ratings,
                "status": "EXACT_EXISTING_FIELDS" if not identities and not ratings else "CONFLICT",
            }
        )

    pilot_results = []
    for card in pilot:
        external_id = card["external_card_id"]
        record = records.get(external_id)
        if record is None:
            pilot_results.append(
                {"external_card_id": external_id, "status": "MISSING_FROM_RESPONSE"}
            )
            continue
        identities = identity_conflicts(card, record)
        ratings = ratings_from_record(record)
        listing_conflicts = rating_conflicts(card, ratings)
        complete = len(ratings) == len(ATTRIBUTE_ABBREVIATIONS)
        if identities or listing_conflicts or not complete:
            conflict_id = f"OP-X-013:{external_id}"
            state["conflicts"][conflict_id] = {
                "type": "STRUCTURED_VECTOR_VALIDATION_CONFLICT",
                "source": ENDPOINT,
                "identity_conflicts": identities,
                "rating_conflicts": listing_conflicts,
                "observed_fields": len(ratings),
                "resolution": "PRESERVE_EXISTING_RECORD",
            }
            status = "PRESERVED_CONFLICT"
        else:
            key = f"CFB_FAN:{external_id}"
            state["cards"][key] = promote_record(
                card, record, snapshot_for(checkpoint, external_id), retrieved_at
            )
            status = "PROMOTED_TO_COMPLETE"
        pilot_results.append(
            {
                "external_card_id": external_id,
                "player_name": card["player_name"],
                "position": card["position"],
                "overall": card["overall"],
                "structured_fields": len(ratings),
                "status": status,
            }
        )

    promoted_count = sum(row["status"] == "PROMOTED_TO_COMPLETE" for row in pilot_results)
    state["resume_cursor"] = f"full-vector-priority-promoted-{promoted_count}"
    _save(state_path, state)
    output = root / "data/research/cfb27_op_x_013"
    _save(output / "existing_full_validation.json", validation)
    _save(output / "partial_pilot.json", pilot_results)
    after = list(state["cards"].values())
    summary = {
        "endpoint": ENDPOINT,
        "population": len(after),
        "full_before": len(full),
        "partial_before": len(partial),
        "full_after": sum(card.get("extraction_status") == "COMPLETE" for card in after),
        "partial_after": sum(card.get("extraction_status") != "COMPLETE" for card in after),
        "validation_statuses": Counter(row["status"] for row in validation),
        "pilot_statuses": Counter(row["status"] for row in pilot_results),
        "attribute_count": len(ATTRIBUTE_ABBREVIATIONS),
        "attribute_schema": dict(
            sorted((abbr, field) for field, abbr in ATTRIBUTE_ABBREVIATIONS.items())
        ),
        "cards_per_request": 50,
        "mass_requests_remaining": (
            sum(card.get("extraction_status") != "COMPLETE" for card in after) + 49
        )
        // 50,
        "estimated_seconds_at_12_requests_per_minute": ((len(partial) + 49) // 50) * 5,
        "raw_evidence": "data/external/raw/cfb_fan_player_items/<sha256>.json",
        "resume_cursor": state["resume_cursor"],
        "validation_positions": Counter(row.get("position") for row in validation),
        "validation_programs": len({row.get("program") for row in validation}),
        "validation_archetypes": len({row.get("archetype") for row in validation}),
    }
    _save(output / "discovery_and_cost_summary.json", summary)
    print(json.dumps(summary, indent=2, default=dict))


if __name__ == "__main__":
    main()
