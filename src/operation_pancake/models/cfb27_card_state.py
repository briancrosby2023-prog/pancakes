"""Canonical CFB27 player/card/state entities with deterministic identifiers."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field


def stable_id(kind: str, *parts: object) -> str:
    """Return a deterministic opaque identifier without using a name as sole identity."""
    normalized = "|".join(str(part).strip().casefold() for part in parts)
    return f"{kind}:{hashlib.sha256(normalized.encode()).hexdigest()[:20]}"


@dataclass(frozen=True, slots=True)
class PlayerEntity:
    player_id: str
    name: str
    source_player_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class CardEntity:
    card_id: str
    player_id: str
    source: str
    source_card_id: str
    position: str
    program: str | None
    archetype: str | None


@dataclass(frozen=True, slots=True)
class CardState:
    state_id: str
    card_id: str
    state_type: str
    overall: int | None
    ratings: dict[str, int | None] = field(default_factory=dict)
    provenance: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.state_type not in {"NATIVE", "UPGRADE", "ACTIVE"}:
            raise ValueError("Unsupported card-state type.")
        if self.overall is not None and not 0 <= self.overall <= 99:
            raise ValueError("Overall must be null or between 0 and 99.")
        for value in self.ratings.values():
            if value is not None and (not isinstance(value, int) or not 0 <= value <= 99):
                raise ValueError("Ratings must be null or integers between 0 and 99.")


@dataclass(frozen=True, slots=True)
class ProgressionEvent:
    event_id: str
    card_id: str
    from_state_id: str
    to_state_id: str
    from_overall: int | None
    to_overall: int | None
    attribute_deltas: dict[str, int]
    system: str
    source: str
    confidence: str
    user_observed: bool
    rerollable: bool | None = None
    deterministic_or_random: str = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class SpecialistView:
    view_id: str
    roster_instance_id: str
    underlying_card_id: str | None
    role: str
    displayed_overall: int | None
    formula_status: str = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class ChemistryContext:
    context_id: str
    boost_source: str | None = None
    affected_attributes: tuple[str, ...] = ()
    delta: int | None = None
    display_effect: str | None = None
    theme_requirement: str | None = None
    confidence: str = "UNKNOWN"
