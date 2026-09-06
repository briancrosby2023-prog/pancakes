"""Reconcile Pancake CFB27 exact card IDs to the current public CFB.FAN universe."""
from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from run_cfb27_population_v3 import parse_listing

from operation_pancake.acquisition.cfb_fan_bulk import (
    CfbFanBulkAdapter,
    cfb27_position,
    identity_conflicts,
    rating_conflicts,
    ratings_from_record,
)

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "data/external/cfb_fan_population_state.json"
DISCOVERY = ROOT / "data/external/cfb_fan_current_discovery.json"
REPORT = ROOT / "data/research/cfb27_delta_refresh/report.json"
RAW = ROOT / "data/external/raw/cfb_fan_current_listings"
BASE = "https://cfb.fan/players/?page={}"
DELAY = 5.0


def save(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def fetch(url: str) -> bytes:
    req = Request(url, headers={"User-Agent": "OperationPancakeResearch/1.0"})
    with urlopen(req, timeout=30) as response:
        return response.read()


def discover_current() -> dict[str, dict]:
    RAW.mkdir(parents=True, exist_ok=True)
    cards: dict[str, dict] = {}
    pages: dict[str, dict] = {}
    empty_streak = 0
    page = 1
    while True:
        url = BASE.format(page)
        try:
            content = fetch(url)
        except HTTPError as exc:
            if exc.code == 404 and cards:
                break
            raise
        digest = hashlib.sha256(content).hexdigest()
        rel = Path("data/external/raw/cfb_fan_current_listings") / f"{digest}.html"
        target = ROOT / rel
        if not target.exists():
            target.write_bytes(content)
        parsed = parse_listing(content.decode("utf-8"), rel.as_posix(), 27)
        pages[str(page)] = {
            "url": url,
            "sha256": digest,
            "snapshot": rel.as_posix(),
            "cards": len(parsed),
        }
        for card in parsed:
            cards[card["external_card_id"]] = card
        empty_streak = empty_streak + 1 if not parsed else 0
        if page % 25 == 0:
            save(DISCOVERY, {"season": 27, "pages": pages, "cards": cards, "complete": False})
            print(f"discovery page={page} unique={len(cards)}", flush=True)
        if empty_streak >= 2:
            break
        page += 1
        time.sleep(DELAY)
    save(DISCOVERY, {"season": 27, "pages": pages, "cards": cards, "complete": True})
    return cards


def structured_card(listing: dict, record: dict, snapshot: str, retrieved_at: str) -> dict:
    ratings = ratings_from_record(record)
    if not ratings:
        raise ValueError("structured record has no observed ratings")
    card = dict(listing)
    card.update(
        player_name=" ".join(filter(None, (record.get("firstName"), record.get("lastName")))),
        position=cfb27_position(record),
        overall=record.get("overall"),
        program=(record.get("program") or {}).get("name"),
        archetype=(record.get("archetype") or {}).get("nameWithoutPosition"),
        team_school=(record.get("team") or {}).get("school"),
        release_date=record.get("releaseDate"),
        displayed_ratings=ratings,
        retrieval_timestamp=retrieved_at,
        raw_snapshot_reference=snapshot,
        extraction_status="COMPLETE",
        validation_status="VALIDATED_PUBLIC_STRUCTURED_VECTOR",
    )
    card["metadata"] = {
        **listing.get("metadata", {}),
        "structured_endpoint": "https://cfb.fan/api/27/player-items/",
        "attribute_fields_observed": len(ratings),
        "delta_refresh": True,
    }
    return card


def main() -> None:
    retrieved_at = (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )
    state = json.loads(STATE.read_text(encoding="utf-8"))
    old_ids = {card["external_card_id"] for card in state["cards"].values()}
    current = discover_current()
    current_ids = set(current)
    missing = sorted(current_ids - old_ids)
    adapter = CfbFanBulkAdapter(ROOT)
    checkpoint, records = adapter.acquire(missing, retrieved_at)
    accepted: list[str] = []
    rejected: dict[str, str] = {}
    for external_id in missing:
        record = records.get(external_id)
        if record is None:
            rejected[external_id] = "NOT_RETURNED_BY_STRUCTURED_ENDPOINT"
            continue
        listing = current[external_id]
        identity = identity_conflicts(listing, record)
        ratings = rating_conflicts(listing, ratings_from_record(record))
        identity.pop("position", None)
        if identity or ratings:
            rejected[external_id] = json.dumps(
                {"identity": identity, "ratings": ratings}, sort_keys=True
            )
            continue
        batch = next(
            (
                value
                for value in checkpoint["batches"].values()
                if external_id in value["returned_ids"]
            ),
            None,
        )
        if batch is None:
            rejected[external_id] = "NO_PROVENANCE_BATCH"
            continue
        card = structured_card(listing, record, batch["snapshot"], retrieved_at)
        state["cards"][f"CFB_FAN:{external_id}"] = card
        accepted.append(external_id)
    save(STATE, state)
    refreshed_ids = {card["external_card_id"] for card in state["cards"].values()}
    duplicates = len(state["cards"]) - len(refreshed_ids)
    report = {
        "retrieved_at": retrieved_at,
        "old_canonical_count": len(old_ids),
        "current_cfb_fan_count": len(current_ids),
        "missing_before_refresh": len(missing),
        "missing_ids_discovered": missing,
        "fetched": len(records),
        "accepted": accepted,
        "rejected_conflicted": rejected,
        "final_canonical_count": len(refreshed_ids),
        "cfb_fan_ids_still_missing": sorted(current_ids - refreshed_ids),
        "old_ids_lost": sorted(old_ids - refreshed_ids),
        "duplicates": duplicates,
    }
    save(REPORT, report)
    print(json.dumps(report, indent=2, sort_keys=True))
    if report["cfb_fan_ids_still_missing"] or report["old_ids_lost"] or duplicates:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
