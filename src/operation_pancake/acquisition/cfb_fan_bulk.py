"""Restartable acquisition from CFB.FAN's public CFB27 bulk endpoint."""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Callable
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ENDPOINT = "https://cfb.fan/api/27/player-items/"
PARSER_VERSION = "cfb-fan-player-items-v2-cfb27-game-positions"
REQUESTS_PER_MINUTE = 12

ATTRIBUTE_ABBREVIATIONS = {
    "acceleration": "ACC", "agility": "AGI", "awareness": "AWR",
    "ballCarrierVision": "BCV", "blockShedding": "BSH", "breakSack": "BSK",
    "breakTackle": "BTK", "carrying": "CAR", "catchInTraffic": "CIT",
    "catching": "CTH", "changeOfDirection": "COD", "deepRouteRunning": "DRR",
    "deepThrowAccuracy": "DAC", "finesseMoves": "FMV", "hitPower": "POW",
    "impactBlocking": "IBL", "injury": "INJ", "jukeMove": "JKM", "jumping": "JMP",
    "kickAccuracy": "KAC", "kickPower": "KPW", "kickReturn": "RET", "leadBlock": "LBK",
    "manCoverage": "MCV", "mediumRouteRunning": "MRR", "mediumThrowAccuracy": "MAC",
    "passBlock": "PBK", "passBlockFinesse": "PBF", "passBlockPower": "PBP",
    "playAction": "PAC", "playRecognition": "PRC", "powerMoves": "PMV", "press": "PRS",
    "pursuit": "PUR", "release": "RLS", "runBlock": "RBK", "runBlockFinesse": "RBF",
    "runBlockPower": "RBP", "shortRouteRunning": "SRR", "shortThrowAccuracy": "SAC",
    "spectacularCatch": "SPC", "speed": "SPD", "spinMove": "SPM", "stamina": "STA",
    "stiffArm": "SFA", "strength": "STR", "tackle": "TAK", "throwAccuracy": "THA",
    "throwPower": "THP", "throwUnderPressure": "TUP", "throwingOnTheRun": "RUN",
    "toughness": "TGH", "trucking": "TRK", "zoneCoverage": "ZCV",
}


def parse_bulk_payload(content: bytes) -> dict[str, dict]:
    """Return API records keyed by canonical ``27-*`` ID."""
    payload = json.loads(content)
    if not isinstance(payload.get("data"), list):
        raise ValueError("CFB.FAN bulk response has no data list")
    records = {}
    for item in payload["data"]:
        external_id = item.get("externalId")
        if not isinstance(external_id, int):
            raise ValueError("CFB.FAN bulk record has no numeric externalId")
        records[f"27-{external_id}"] = item
    return records


def cfb27_position(record: dict) -> str | None:
    """Return the game-facing CFB27 position, falling back only for old payloads."""
    game = (record.get("gamePosition") or {}).get("abbreviation")
    return game or (record.get("position") or {}).get("abbreviation")


def ratings_from_record(record: dict) -> dict[str, int]:
    """Extract observed ratings; absent fields stay absent and zero is retained."""
    ratings = {}
    for field, abbreviation in ATTRIBUTE_ABBREVIATIONS.items():
        value = record.get(field)
        if isinstance(value, int) and not isinstance(value, bool):
            ratings[abbreviation] = value
    return dict(sorted(ratings.items()))


def identity_conflicts(existing: dict, record: dict) -> dict[str, dict]:
    expected = {
        "player_name": " ".join(filter(None, (record.get("firstName"), record.get("lastName")))),
        "position": cfb27_position(record),
        "overall": record.get("overall"),
        "program": (record.get("program") or {}).get("name"),
        "archetype": (record.get("archetype") or {}).get("nameWithoutPosition"),
    }
    return {
        field: {"existing": existing.get(field), "structured": value}
        for field, value in expected.items()
        if value is not None and existing.get(field) != value
    }


def rating_conflicts(existing: dict, ratings: dict[str, int]) -> dict[str, dict]:
    return {
        name: {"existing": value, "structured": ratings[name]}
        for name, value in existing.get("displayed_ratings", {}).items()
        if name in ratings and ratings[name] != value
    }


def promote_record(existing: dict, record: dict, snapshot: str, retrieved_at: str) -> dict:
    """Promote a validated partial record without ever downgrading a full record."""
    if existing.get("extraction_status") == "COMPLETE":
        return existing
    ratings = ratings_from_record(record)
    if not ratings:
        raise ValueError("Cannot promote a record without observed ratings")
    promoted = dict(existing)
    promoted.update(
        displayed_ratings=ratings,
        extraction_status="COMPLETE",
        validation_status="VALIDATED_PUBLIC_STRUCTURED_VECTOR",
        raw_snapshot_reference=snapshot,
        retrieval_timestamp=retrieved_at,
        team_school=(record.get("team") or {}).get("school"),
        release_date=record.get("releaseDate"),
        position=cfb27_position(record) or existing.get("position"),
    )
    promoted["metadata"] = {
        **existing.get("metadata", {}),
        "structured_endpoint": ENDPOINT,
        "structured_parser_version": PARSER_VERSION,
        "attribute_fields_observed": len(ratings),
    }
    return promoted


def priority_key(card: dict) -> tuple:
    """Implement the packet's acquisition order using CFB27 terminology."""
    position = card.get("position")
    group = {
        "LT": 3, "LG": 3, "C": 3, "RG": 3, "RT": 3,
        "SAM": 4, "MIKE": 4, "WILL": 4,
        "LEDG": 5, "REDG": 5, "DT": 6, "TE": 7,
        "CB": 8, "FS": 8, "SS": 8, "QB": 9, "WR": 10, "HB": 10,
    }.get(position, 11)
    high_ovr = 0 if (card.get("overall") or 0) >= 85 else 1
    upgradeable = 0 if card.get("metadata", {}).get("has_power_up") else 1
    return (high_ovr, upgradeable, group, -(card.get("overall") or 0), card["external_card_id"])


class CfbFanBulkAdapter:
    """Fetch deterministic ID batches, persist raw bytes, and resume from checkpoints."""

    def __init__(self, root: Path, fetcher: Callable[[str], bytes] | None = None) -> None:
        self.root = root
        self.raw_dir = root / "data/external/raw/cfb_fan_player_items"
        self.checkpoint_path = root / "data/external/cfb_fan_full_vector_checkpoint.json"
        self.fetcher = fetcher or self._fetch
        self._last_request = 0.0

    def _fetch(self, url: str) -> bytes:
        delay = 60 / REQUESTS_PER_MINUTE
        elapsed = time.monotonic() - self._last_request
        if self._last_request and elapsed < delay:
            time.sleep(delay - elapsed)
        request = Request(url, headers={"User-Agent": "OperationPancakePilot/1.0"})
        with urlopen(request, timeout=30) as response:
            if response.status != 200:
                raise PermissionError(f"HTTP {response.status}")
            content = response.read()
        self._last_request = time.monotonic()
        return content

    def _checkpoint(self) -> dict:
        if not self.checkpoint_path.exists():
            return {"schema_version": 1, "batches": {}}
        return json.loads(self.checkpoint_path.read_text(encoding="utf-8"))

    def _save_checkpoint(self, checkpoint: dict) -> None:
        self.checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
        self.checkpoint_path.write_text(
            json.dumps(checkpoint, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )

    def acquire_batch(self, card_ids: list[str]) -> dict[str, dict]:
        ids = sorted({card_id.removeprefix("27-") for card_id in card_ids}, key=int)
        query = urlencode({"ids": ",".join(ids)})
        url = f"{ENDPOINT}?{query}"
        batch_key = hashlib.sha256(url.encode()).hexdigest()[:16]
        checkpoint = self._checkpoint()
        prior = checkpoint.get("batches", {}).get(batch_key)
        if prior and (self.root / prior["snapshot"]).exists():
            return parse_bulk_payload((self.root / prior["snapshot"]).read_bytes())
        content = self.fetcher(url)
        digest = hashlib.sha256(content).hexdigest()
        snapshot = self.raw_dir / f"{digest}.json"
        snapshot.parent.mkdir(parents=True, exist_ok=True)
        if not snapshot.exists():
            snapshot.write_bytes(content)
        records = parse_bulk_payload(content)
        checkpoint.setdefault("batches", {})[batch_key] = {
            "url": url,
            "requested_ids": [f"27-{item}" for item in ids],
            "returned_ids": sorted(records),
            "snapshot": str(snapshot.relative_to(self.root)).replace("\\", "/"),
            "sha256": digest,
            "retrieved_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
        }
        self._save_checkpoint(checkpoint)
        return records
