"""C-3PO full Team Manager transcription for the observation-first My Team flow."""
from __future__ import annotations

import base64
import json
import mimetypes
import os
from dataclasses import dataclass
from pathlib import Path

from operation_pancake.team_import import Candidate, VIEW_SLOTS, normalize_name


@dataclass(frozen=True)
class TeamPlayerObservation:
    slot: str
    observed_name: str | None
    displayed_ovr: int | None
    backups: tuple[dict, ...] = ()


@dataclass(frozen=True)
class TeamScreenObservation:
    view: str
    players: tuple[TeamPlayerObservation, ...]
    provider: str
    model: str


PLAYER_SCHEMA = {
    "type": "object",
    "properties": {
        "slot": {"type": "string"},
        "observed_name": {"type": ["string", "null"]},
        "displayed_ovr": {"type": ["integer", "null"], "minimum": 40, "maximum": 99},
        "backups": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "player_name": {"type": ["string", "null"]},
                    "displayed_ovr": {"type": ["integer", "null"], "minimum": 40, "maximum": 99},
                },
                "required": ["player_name", "displayed_ovr"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["slot", "observed_name", "displayed_ovr", "backups"],
    "additionalProperties": False,
}

TEAM_SCHEMA = {
    "type": "object",
    "properties": {
        "view": {"type": "string", "enum": list(VIEW_SLOTS)},
        "players": {"type": "array", "items": PLAYER_SCHEMA},
    },
    "required": ["view", "players"],
    "additionalProperties": False,
}

PROMPT = """You are C-3PO, a literal data-entry clerk reading one EA SPORTS
COLLEGE FOOTBALL 27 Team Manager screenshot. Identify which visible lineup view
this is: OFFENSE, DEFENSE, SPECIAL TEAMS, or SPECIALISTS. For every visible
lineup slot in that view, transcribe the slot label, visible player name, and
the OVR number EA visibly displays. Include visible backup rows in backups.
Report pixels only. Do not search for, infer, correct, or choose a CFB27 card.
Displayed OVR may include boosts and must be copied exactly rather than changed
to a database value. If text is genuinely unreadable, return null. Never invent
an unreadable player name. Return only the schema-constrained observation."""


class GeminiTeamTranslator:
    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        timeout_ms: int = 15000,
    ):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.model = model or os.getenv("PANCAKE_GEMINI_MODEL", "gemini-3.7-flash")
        self.timeout_ms = timeout_ms
        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY is required for C-3PO transcription")

    def translate(self, screenshot: Path) -> TeamScreenObservation:
        try:
            from google import genai
            from google.genai import types
        except ImportError as exc:
            raise RuntimeError(
                "Install the 'google-genai' package for C-3PO transcription"
            ) from exc
        data = screenshot.read_bytes()
        mime = mimetypes.guess_type(screenshot.name)[0] or "image/png"
        with genai.Client(
            api_key=self.api_key,
            http_options=types.HttpOptions(timeout=self.timeout_ms),
        ) as client:
            interaction = client.interactions.create(
                model=self.model,
                input=[
                    {"type": "text", "text": PROMPT},
                    {
                        "type": "image",
                        "data": base64.b64encode(data).decode("ascii"),
                        "mime_type": mime,
                    },
                ],
                response_format={
                    "type": "text",
                    "mime_type": "application/json",
                    "schema": TEAM_SCHEMA,
                },
            )
        payload = json.loads(interaction.output_text)
        view = payload["view"]
        allowed = set(VIEW_SLOTS[view])
        players = []
        for row in payload["players"]:
            slot = str(row["slot"]).upper().strip()
            if slot not in allowed:
                continue
            backups = tuple(x for x in row.get("backups", []) if x.get("player_name"))
            players.append(
                TeamPlayerObservation(
                    slot,
                    row.get("observed_name"),
                    row.get("displayed_ovr"),
                    backups,
                )
            )
        return TeamScreenObservation(view, tuple(players), "google-gemini", self.model)


def _cfb27(card):
    markers = [card.get(k) for k in ("game", "season", "title", "dataset") if card.get(k)]
    if not markers:
        return True
    text = " ".join(str(value).upper() for value in markers)
    return not ("CFB25" in text or "CFB 25" in text or "CFB26" in text or "CFB 26" in text)


def _exact_cards(name, cards):
    query = normalize_name(name or "")
    if not query:
        return []
    return [
        card
        for card in cards
        if _cfb27(card) and normalize_name(card.get("player_name") or "") == query
    ]


def _enrich(candidate, cards):
    """Enrich an observation without adjudicating or replacing its identity."""
    if not candidate.player_name or not normalize_name(candidate.player_name):
        candidate.match_status = "UNRESOLVED"
        return candidate
    matches = _exact_cards(candidate.player_name, cards)
    candidate.match_diagnostics = dict(candidate.match_diagnostics)
    candidate.match_diagnostics["enrichment"] = {
        "status": "not-linked",
        "card_ids": [card.get("card_id") for card in matches],
    }
    candidate.match_status = "OBSERVED"
    if not matches:
        return candidate
    identities = {normalize_name(card.get("player_name") or "") for card in matches}
    if len(identities) != 1 or len(matches) != 1:
        candidate.match_status = "AMBIGUOUS_CARD"
        candidate.match_diagnostics["enrichment"]["status"] = "ambiguous-card"
        return candidate
    card = matches[0]
    candidate.canonical_card_id = card.get("card_id")
    candidate.program = card.get("program")
    candidate.confidence = 1.0
    candidate.match_status = "LINKED"
    candidate.match_diagnostics["enrichment"] = {
        "status": "linked",
        "canonical_name": card.get("player_name"),
        "native_position": card.get("position"),
        "native_card_ovr": card.get("native_overall"),
        "program": card.get("program"),
        "card_ids": [card.get("card_id")],
    }
    return candidate


def _enrich_backup(backup, cards):
    row = dict(backup)
    name = row.get("player_name")
    if not name or not normalize_name(name):
        row["enrichment_status"] = "unresolved"
        return row
    matches = _exact_cards(name, cards)
    row["enrichment_status"] = "not-linked"
    if len(matches) == 1:
        card = matches[0]
        row.update(
            enrichment_status="linked",
            canonical_card_id=card.get("card_id"),
            canonical_name=card.get("player_name"),
            native_position=card.get("position"),
            native_card_ovr=card.get("native_overall"),
            program=card.get("program"),
        )
    elif len(matches) > 1:
        row["enrichment_status"] = "ambiguous-card"
        row["canonical_card_ids"] = [card.get("card_id") for card in matches]
    return row


def candidates_from_observation(
    observation: TeamScreenObservation,
    cards,
    source_id: str,
    start: int = 0,
):
    """Preserve C-3PO identity; canonical CFB27 lookup is enrichment only."""
    out = []
    for offset, player in enumerate(observation.players, 1):
        candidate = Candidate(
            id=f"cand-{start + offset}",
            group=observation.view,
            slot=player.slot,
            player_name=player.observed_name,
            displayed_ovr=player.displayed_ovr,
            backups=[_enrich_backup(row, cards) for row in player.backups],
            provenance=[f"c3po:{observation.provider}", f"source:{source_id}"],
        )
        out.append(_enrich(candidate, cards))
    return out
