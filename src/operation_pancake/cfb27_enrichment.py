"""Optional CFB27 card enrichment layered after authoritative C-3PO observations."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable

from operation_pancake.c3po_roster import C3POPlayer, C3PORoster


def normalize_c3po_name(value: str | None) -> str:
    """Normalize only enough for exact-name lookup; never infer another identity."""
    return re.sub(r"[^a-z0-9]+", "", (value or "").casefold())


@dataclass(frozen=True)
class CFB27CardData:
    canonical_name: str
    native_position: str | None = None
    card_ovr: int | None = None
    program: str | None = None
    card_id: str | None = None
    ratings: dict[str, Any] | None = None


@dataclass(frozen=True)
class CFB27PlayerEnrichment:
    observation: C3POPlayer
    state: str
    card: CFB27CardData | None = None
    choices: tuple[CFB27CardData, ...] = ()


@dataclass(frozen=True)
class CFB27RosterEnrichment:
    roster: C3PORoster
    players: tuple[CFB27PlayerEnrichment, ...]


def _card(row: dict[str, Any]) -> CFB27CardData:
    return CFB27CardData(
        canonical_name=str(row.get("player_name") or row.get("name") or ""),
        native_position=row.get("position") or row.get("native_position"),
        card_ovr=row.get("native_overall", row.get("overall", row.get("ovr"))),
        program=row.get("program") or row.get("card_type"),
        card_id=row.get("card_id") or row.get("id"),
        ratings=row.get("ratings") if isinstance(row.get("ratings"), dict) else None,
    )


def enrich_c3po_roster(
    roster: C3PORoster, cards: Iterable[dict[str, Any]] | None
) -> CFB27RosterEnrichment:
    """Attach exact normalized-name card data without changing C-3PO evidence."""
    index: dict[str, list[CFB27CardData]] = {}
    for row in cards or ():
        card = _card(row)
        key = normalize_c3po_name(card.canonical_name)
        if key:
            index.setdefault(key, []).append(card)

    enriched = []
    for observation in roster.players:
        matches = index.get(normalize_c3po_name(observation.name), [])
        if len(matches) == 1:
            enriched.append(CFB27PlayerEnrichment(observation, "LINKED", matches[0]))
        elif len(matches) > 1:
            enriched.append(
                CFB27PlayerEnrichment(observation, "SELECT CARD", choices=tuple(matches))
            )
        else:
            enriched.append(CFB27PlayerEnrichment(observation, "CFB27 DATA NOT LINKED"))
    return CFB27RosterEnrichment(roster, tuple(enriched))
