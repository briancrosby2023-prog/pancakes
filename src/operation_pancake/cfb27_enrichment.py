"""Optional CFB27 card enrichment layered after authoritative C-3PO observations."""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping
from urllib.parse import urlparse

from operation_pancake.c3po_roster import C3POPlayer, C3PORoster

PRODUCTION_CARDS_PATH = Path("data/production/cfb27_scored_population.json")


def normalize_c3po_name(value: str | None) -> str:
    """Normalize only enough for exact-name lookup; never infer another identity."""
    return re.sub(r"[^a-z0-9]+", "", (value or "").casefold())


def load_cfb27_production_cards(root: Path) -> tuple[dict[str, Any], ...]:
    """Load the existing scored CFB27 population, or fail open with no cards."""
    try:
        payload = json.loads((root / PRODUCTION_CARDS_PATH).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return ()
    if not isinstance(payload, list) or not all(isinstance(row, dict) for row in payload):
        return ()
    return tuple(payload)


@dataclass(frozen=True)
class CFB27CardData:
    canonical_name: str
    native_position: str | None = None
    card_ovr: int | None = None
    program: str | None = None
    card_id: str | None = None
    ratings: dict[str, Any] | None = None
    source_url: str | None = None


@dataclass(frozen=True)
class CFB27PlayerEnrichment:
    observation: C3POPlayer
    state: str
    fingerprint: str
    card: CFB27CardData | None = None
    choices: tuple[CFB27CardData, ...] = ()


@dataclass(frozen=True)
class CFB27RosterEnrichment:
    roster: C3PORoster
    players: tuple[CFB27PlayerEnrichment, ...]


class CFB27CardChoiceStore:
    """Persistence for explicit card-version choices, separate from C3PORoster."""

    def __init__(self, path: Path):
        self.path = path

    def load(self) -> dict[str, str]:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            return {}
        choices = payload.get("choices") if isinstance(payload, dict) else None
        if not isinstance(choices, dict):
            return {}
        return {
            str(fingerprint): str(card_id)
            for fingerprint, card_id in choices.items()
            if isinstance(fingerprint, str) and isinstance(card_id, str)
        }

    def save(self, choices: Mapping[str, str]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(
            json.dumps({"choices": dict(choices)}, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary.replace(self.path)


def observation_fingerprint(observation: C3POPlayer, occurrence: int) -> str:
    """Bind a choice to one immutable observed roster row."""
    evidence = json.dumps(
        [
            normalize_c3po_name(observation.name),
            observation.view,
            observation.slot,
            observation.displayed_ovr,
            occurrence,
        ],
        separators=(",", ":"),
    )
    return hashlib.sha256(evidence.encode("utf-8")).hexdigest()


def _card(row: dict[str, Any]) -> CFB27CardData:
    source = row.get("source")
    source_url = source.get("ratings") if isinstance(source, dict) else None
    parsed_source = urlparse(source_url) if isinstance(source_url, str) else None
    if (
        parsed_source is None
        or parsed_source.scheme != "https"
        or parsed_source.netloc != "cfb.fan"
    ):
        source_url = None
    return CFB27CardData(
        canonical_name=str(row.get("player_name") or row.get("name") or ""),
        native_position=row.get("position") or row.get("native_position"),
        card_ovr=row.get("native_overall", row.get("overall", row.get("ovr"))),
        program=row.get("program") or row.get("card_type"),
        card_id=row.get("card_id") or row.get("id"),
        ratings=row.get("ratings") if isinstance(row.get("ratings"), dict) else None,
        source_url=source_url,
    )


def enrich_c3po_roster(
    roster: C3PORoster,
    cards: Iterable[dict[str, Any]] | None,
    stored_choices: Mapping[str, str] | None = None,
) -> CFB27RosterEnrichment:
    """Attach exact normalized-name card data without changing C-3PO evidence."""
    index: dict[str, list[CFB27CardData]] = {}
    for row in cards or ():
        card = _card(row)
        key = normalize_c3po_name(card.canonical_name)
        if key:
            index.setdefault(key, []).append(card)

    enriched = []
    for occurrence, observation in enumerate(roster.players):
        fingerprint = observation_fingerprint(observation, occurrence)
        matches = index.get(normalize_c3po_name(observation.name), [])
        selected_id = (stored_choices or {}).get(fingerprint)
        selected = [card for card in matches if card.card_id == selected_id]
        if len(selected) == 1:
            enriched.append(
                CFB27PlayerEnrichment(observation, "LINKED", fingerprint, selected[0])
            )
        elif len(matches) == 1:
            enriched.append(
                CFB27PlayerEnrichment(observation, "LINKED", fingerprint, matches[0])
            )
        elif len(matches) > 1:
            enriched.append(
                CFB27PlayerEnrichment(
                    observation,
                    "SELECT CARD",
                    fingerprint,
                    choices=tuple(matches),
                )
            )
        else:
            enriched.append(
                CFB27PlayerEnrichment(
                    observation, "CFB27 DATA NOT LINKED", fingerprint
                )
            )
    return CFB27RosterEnrichment(roster, tuple(enriched))
