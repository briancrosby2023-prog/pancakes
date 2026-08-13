"""External adapter lifecycle and responsible access policy."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Iterable

from operation_pancake.acquisition.models import ExternalCard, MarketObservation, RawSnapshot


@dataclass(frozen=True, slots=True)
class AccessPolicy:
    requests_per_minute: int = 30
    max_retries: int = 3
    initial_backoff_seconds: float = 1.0
    reuse_cached_snapshots: bool = True
    resume_supported: bool = True
    bypass_restricted_access: bool = False


class ExternalCardAdapter(ABC):
    """Adapters can acquire and stage evidence but cannot mutate canonical records."""

    source_name: str
    parser_version: str
    access_policy = AccessPolicy()

    @abstractmethod
    def discover_cards(self) -> Iterable[dict[str, Any]]: ...

    @abstractmethod
    def fetch_card(self, discovery: dict[str, Any]) -> bytes: ...

    @abstractmethod
    def parse_card(self, snapshot: RawSnapshot, content: bytes) -> dict[str, Any]: ...

    @abstractmethod
    def normalize_card(self, parsed: dict[str, Any], snapshot: RawSnapshot) -> ExternalCard: ...

    def stage_card(self, card: ExternalCard) -> dict[str, Any]:
        """Convert external evidence to the shared ingestion-manifest representation."""
        return {
            "record_id": f"EXT-{card.external_source.upper()}-{card.external_card_id}",
            "record_type": "card",
            "disposition": "REFERENCE_DATA",
            "validation_status": card.validation_status,
            "values": {
                "external_source": card.external_source,
                "external_player_id": card.external_player_id,
                "external_card_id": card.external_card_id,
                "player": card.player_name,
                "position": card.position,
                "overall": card.overall,
                "archetype": card.archetype,
                "program": card.program,
                "card_type": card.card_type,
                "team_school": card.team_school,
                "release_date": card.release_date,
                "attributes": {
                    name: value if value is not None else "UNKNOWN"
                    for name, value in card.displayed_ratings.items()
                },
                "raw_snapshot_reference": card.raw_snapshot_reference,
            },
            "unresolved_fields": sorted(
                name for name, value in card.displayed_ratings.items() if value is None
            ),
            "source_links": [
                {
                    "source_id": card.external_source,
                    "locator": card.source_reference,
                    "catalog_source": True,
                }
            ],
        }


class FixtureAdapter(ExternalCardAdapter):
    """Reference adapter for deterministic local fixtures."""

    source_name = "FIXTURE"
    parser_version = "fixture-v1"

    def __init__(self, discoveries: list[dict[str, Any]], payloads: dict[str, bytes]) -> None:
        self._discoveries = discoveries
        self._payloads = payloads

    def discover_cards(self) -> Iterable[dict[str, Any]]:
        return list(self._discoveries)

    def fetch_card(self, discovery: dict[str, Any]) -> bytes:
        return self._payloads[discovery["external_card_id"]]

    def parse_card(self, snapshot: RawSnapshot, content: bytes) -> dict[str, Any]:
        import json

        return json.loads(content.decode("utf-8"))

    def normalize_card(self, parsed: dict[str, Any], snapshot: RawSnapshot) -> ExternalCard:
        parsed = dict(parsed)
        parsed["market_observations"] = tuple(
            MarketObservation(**item) for item in parsed.get("market_observations", [])
        )
        return ExternalCard(
            **parsed,
            raw_snapshot_reference=snapshot.snapshot_location,
            extraction_status="COMPLETE",
            validation_status="STAGED_EXTERNAL",
        )
