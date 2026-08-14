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
PARSER_VERSION = "cfb-fan-player-items-v1"
REQUESTS_PER_MINUTE = 12

ATTRIBUTE_ABBREVIATIONS = {
    "acceleration": "ACC",
    "agility": "AGI",
    "awareness": "AWR",
    "ballCarrierVision": "BCV",
    "blockShedding": "BSH",
    "breakSack": "BSK",
    "breakTackle": "BTK",
    "carrying": "CAR",
    "catchInTraffic": "CIT",
    "catching": "CTH",
    "changeOfDirection": "COD",
    "deepRouteRunning": "DRR",
    "deepThrowAccuracy": "DAC",
    "finesseMoves": "FMV",
    "hitPower": "POW",
    "impactBlocking": "IBL",
    "injury": "INJ",
    "jukeMove": "JKM",
    "jumping": "JMP",
    "kickAccuracy": "KAC",
    "kickPower": "KPW",
    "kickReturn": "RET",
    "leadBlock": "LBK",
    "manCoverage": "MCV",
    "mediumRouteRunning": "MRR",
    "mediumThrowAccuracy": "MAC",
    "passBlock": "PBK",
    "passBlockFinesse": "PBF",
    "passBlockPower": "PBP",
    "playAction": "PAC",
    "playRecognition": "PRC",
    "powerMoves": "PMV",
    "press": "PRS",
    "pursuit": "PUR",
    "release": "RLS",
    "runBlock": "RBK",
    "runBlockFinesse": "RBF",
    "runBlockPower": "RBP",
    "shortRouteRunning": "SRR",
    "shortThrowAccuracy": "SAC",
    "spectacularCatch": "SPC",
    "speed": "SPD",
    "spinMove": "SPM",
    "stamina": "STA",
    "stiffArm": "SFA",
    "strength": "STR",
    "tackle": "TAK",
    "throwAccuracy": "THA",
    "throwPower": "THP",
    "throwUnderPressure": "TUP",
    "throwingOnTheRun": "RUN",
    "toughness": "TGH",
    "trucking": "TRK",
    "zoneCoverage": "ZCV",
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


def ratings_from_record(record: dict) -> dict[str, int]:
    """Extract observed ratings; absent fields stay absent and zero is retained."""
    ratings = {}
    for field, abbreviation in ATTRIBUTE_ABBREVIATIONS.items():
        value = record.get(field)
        if isinstance(value, int) and not isinstance(value, bool):
            ratings[abbreviation] = value
    return dict(sorted(ratings.items()))


def identity_conflicts(existing: dict, record: dict) -> dict[str, dict]:
    position = (record.get("position") or {}).get("abbreviation")
    expected = {
        "player_name": " ".join(filter(None, (record.get("firstName"), record.get("lastName")))),
        "position": position,
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
    )
    promoted["metadata"] = {
        **existing.get("metadata", {}),
        "structured_endpoint": ENDPOINT,
        "structured_parser_version": PARSER_VERSION,
        "attribute_fields_observed": len(ratings),
    }
    return promoted


def priority_key(card: dict) -> tuple:
    """Implement the packet's acquisition order without excluding any card."""
    position = card.get("position")
    group = {
        "LT": 3,
        "LG": 3,
        "C": 3,
        "RG": 3,
        "RT": 3,
        "MLB": 4,
        "MIKE": 4,
        "LOLB": 4,
        "ROLB": 4,
        "LE": 5,
        "RE": 5,
        "LEDG": 5,
        "REDG": 5,
        "DT": 6,
        "TE": 7,
        "CB": 8,
        "FS": 8,
        "SS": 8,
        "QB": 9,
        "WR": 10,
        "HB": 10,
    }.get(position, 11)
    high_ovr = 0 if (card.get("overall") or 0) >= 85 else 1
    upgradeable = 0 if card.get("metadata", {}).get("has_power_up") else 1
    return (high_ovr, upgradeable, group, -(card.get("overall") or 0), card["external_card_id"])


class CfbFanBulkAdapter:
    """Bounded, checkpointed client for public multi-ID responses."""

    def __init__(
        self, root: Path, batch_size: int = 50, fetcher: Callable[[str], bytes] | None = None
    ):
        self.root = root
        self.batch_size = batch_size
        self.fetcher = fetcher or self._fetch
        self.raw_root = root / "data/external/raw/cfb_fan_player_items"
        self.checkpoint_path = root / "data/external/cfb_fan_full_vector_checkpoint.json"
        self._last_request = 0.0

    @staticmethod
    def _fetch(url: str) -> bytes:
        last_error = None
        for attempt in range(3):
            try:
                request = Request(url, headers={"User-Agent": "OperationPancakeResearch/1.0"})
                with urlopen(request, timeout=30) as response:
                    if response.status != 200:
                        raise RuntimeError(f"HTTP {response.status}")
                    return response.read()
            except Exception as exc:  # noqa: BLE001 - bounded retry, persisted by caller
                last_error = exc
                if attempt < 2:
                    time.sleep(2**attempt)
        raise RuntimeError(f"Bulk acquisition failed after 3 attempts: {last_error}")

    def acquire(self, external_ids: list[str], retrieved_at: str) -> tuple[dict, dict[str, dict]]:
        checkpoint = (
            json.loads(self.checkpoint_path.read_text())
            if self.checkpoint_path.exists()
            else {"batches": {}, "failures": []}
        )
        records = {}
        self.raw_root.mkdir(parents=True, exist_ok=True)
        for offset in range(0, len(external_ids), self.batch_size):
            batch = external_ids[offset : offset + self.batch_size]
            key = hashlib.sha256(",".join(batch).encode()).hexdigest()[:16]
            if key in checkpoint["batches"]:
                content = (self.root / checkpoint["batches"][key]["snapshot"]).read_bytes()
            else:
                numeric_ids = ",".join(x.removeprefix("27-") for x in batch)
                url = f"{ENDPOINT}?{urlencode({'ids': numeric_ids})}"
                try:
                    delay = 60 / REQUESTS_PER_MINUTE
                    elapsed = time.monotonic() - self._last_request
                    if self._last_request and elapsed < delay:
                        time.sleep(delay - elapsed)
                    content = self.fetcher(url)
                    self._last_request = time.monotonic()
                except Exception as exc:
                    checkpoint["failures"].append({"batch": batch, "error": str(exc)})
                    self._save(checkpoint)
                    continue
                digest = hashlib.sha256(content).hexdigest()
                relative = Path("data/external/raw/cfb_fan_player_items") / f"{digest}.json"
                target = self.root / relative
                if not target.exists():
                    target.write_bytes(content)
                parsed = parse_bulk_payload(content)
                checkpoint["batches"][key] = {
                    "requested_ids": batch,
                    "returned_ids": sorted(parsed),
                    "url": url,
                    "sha256": digest,
                    "snapshot": relative.as_posix(),
                    "retrieved_at": retrieved_at,
                }
                self._save(checkpoint)
            records.update(parse_bulk_payload(content))
        return checkpoint, records

    def _save(self, payload: dict) -> None:
        self.checkpoint_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
