"""Immutable source-neutral acquisition models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class RawSnapshot:
    source: str
    retrieved_at: str
    external_identifiers: dict[str, str]
    content_sha256: str
    snapshot_location: str
    parser_version: str
    content_type: str


@dataclass(frozen=True, slots=True)
class MarketObservation:
    observation_id: str
    external_card_id: str
    price: int | None
    listing_count: int | None
    quick_sell_value: int | None
    training_value: int | None
    currency: str | None
    platform: str | None
    observed_at: str
    source: str


@dataclass(frozen=True, slots=True)
class ExternalCard:
    external_source: str
    external_player_id: str | None
    external_card_id: str
    player_name: str
    position: str
    overall: int
    archetype: str | None
    program: str | None
    card_type: str | None
    team_school: str | None
    release_date: str | None
    displayed_ratings: dict[str, int | None]
    source_reference: str
    retrieval_timestamp: str
    raw_snapshot_reference: str
    extraction_status: str
    validation_status: str
    market_observations: tuple[MarketObservation, ...] = field(default_factory=tuple)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.external_source or not self.external_card_id or not self.player_name:
            raise ValueError("External source, card ID, and player name are required.")
        if not 0 <= self.overall <= 99:
            raise ValueError("External card OVR must be between 0 and 99.")
        for name, value in self.displayed_ratings.items():
            if not name or name != name.upper():
                raise ValueError(f"Invalid displayed rating name: {name!r}")
            if value is not None and (not isinstance(value, int) or not 0 <= value <= 99):
                raise ValueError(f"Invalid displayed rating {name}: {value!r}")

    @property
    def external_key(self) -> tuple[str, str]:
        return self.external_source.casefold(), self.external_card_id

    @property
    def conservative_identity(self) -> tuple[str, str, int, str, str, str]:
        return (
            self.player_name.strip().casefold(),
            self.position.upper(),
            self.overall,
            (self.archetype or "").strip().casefold(),
            (self.program or "").strip().casefold(),
            (self.card_type or "").strip().casefold(),
        )
