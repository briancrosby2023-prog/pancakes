"""C-3PO full Team Manager transcription for the simple My Team flow."""
from __future__ import annotations

import base64
import json
import mimetypes
import os
from dataclasses import dataclass
from pathlib import Path

from operation_pancake.team_import import Candidate, VIEW_SLOTS, match_candidate


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
    def __init__(self, api_key: str | None = None, model: str | None = None, timeout_ms: int = 15000):
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
            raise RuntimeError("Install the 'google-genai' package for C-3PO transcription") from exc
        data = screenshot.read_bytes()
        mime = mimetypes.guess_type(screenshot.name)[0] or "image/png"
        with genai.Client(api_key=self.api_key, http_options=types.HttpOptions(timeout=self.timeout_ms)) as client:
            interaction = client.interactions.create(
                model=self.model,
                input=[
                    {"type": "text", "text": PROMPT},
                    {"type": "image", "data": base64.b64encode(data).decode("ascii"), "mime_type": mime},
                ],
                response_format={"type": "text", "mime_type": "application/json", "schema": TEAM_SCHEMA},
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
            players.append(TeamPlayerObservation(slot, row.get("observed_name"), row.get("displayed_ovr"), backups))
        return TeamScreenObservation(view, tuple(players), "google-gemini", self.model)


def candidates_from_observation(observation: TeamScreenObservation, cards, source_id: str, start: int = 0):
    """Attach canonical data by exact clean name; lineup slot/OVR never veto identity."""
    out = []
    for offset, player in enumerate(observation.players, 1):
        candidate = Candidate(
            id=f"cand-{start + offset}",
            group=observation.view,
            slot=player.slot,
            player_name=player.observed_name,
            displayed_ovr=player.displayed_ovr,
            backups=list(player.backups),
            provenance=[f"c3po:{observation.provider}", f"source:{source_id}"],
        )
        out.append(match_candidate(candidate, cards))
    return out
