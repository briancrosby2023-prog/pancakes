"""C-3PO screenshot translation boundary for the bounded LT/RT pilot."""
from __future__ import annotations

import base64
import json
import mimetypes
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Protocol

TACKLE_SLOTS = ("LT1", "RT1")
GEMINI_REQUEST_TIMEOUT_MS = 15_000


@dataclass(frozen=True)
class PlayerObservation:
    observed_name: str | None
    displayed_ovr: int | None


@dataclass(frozen=True)
class TackleSlotObservation:
    starter: PlayerObservation
    backups: tuple[PlayerObservation, ...] = ()


@dataclass(frozen=True)
class TackleScreenObservation:
    view: str
    slots: dict[str, TackleSlotObservation]
    provider: str
    model: str

    def to_dict(self) -> dict:
        return asdict(self)


class ScreenshotTranslator(Protocol):
    def translate_offense_tackles(self, screenshot: Path) -> TackleScreenObservation: ...


TRANSLATOR_SCHEMA = {
    "type": "object",
    "properties": {
        "view": {"type": "string", "enum": ["OFFENSE"]},
        "slots": {
            "type": "object",
            "properties": {
                slot: {
                    "type": "object",
                    "properties": {"starter": {"$ref": "#/$defs/player"}, "backups": {"type": "array", "items": {"$ref": "#/$defs/player"}}},
                    "required": ["starter", "backups"],
                    "additionalProperties": False,
                }
                for slot in TACKLE_SLOTS
            },
            "required": list(TACKLE_SLOTS),
            "additionalProperties": False,
        },
    },
    "required": ["view", "slots"],
    "additionalProperties": False,
    "$defs": {
        "player": {
            "type": "object",
            "properties": {"observed_name": {"type": ["string", "null"]}, "displayed_ovr": {"type": ["integer", "null"], "minimum": 40, "maximum": 99}},
            "required": ["observed_name", "displayed_ovr"],
            "additionalProperties": False,
        }
    },
}

PROMPT = """You are C-3PO, a literal screen translator for an EA SPORTS COLLEGE FOOTBALL 27 Team Manager OFFENSE screenshot.
Read ONLY the LT1 and RT1 tackle containers, including their visible backup rows.
Return what is visibly present, not database knowledge. observed_name is the visible player name. displayed_ovr is the number displayed in the lineup UI, which may include boosts and is NOT necessarily the native card overall.
Do not search or infer any CFB database identity, card id, program, theme-team boost, chemistry, strategy, EVO, or GM decision.
Do not correct a displayed overall to a value you think belongs to a card.
If a name or overall is genuinely unreadable, return null for that field. Never manufacture unreadable text.
Return only the schema-constrained observation."""


class GeminiScreenshotTranslator:
    """Official Gemini API implementation using Google's google-genai SDK."""

    def __init__(self, api_key: str | None = None, model: str | None = None, timeout_ms: int = GEMINI_REQUEST_TIMEOUT_MS):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.model = model or os.getenv("PANCAKE_GEMINI_MODEL", "gemini-3.7-flash")
        self.timeout_ms = timeout_ms
        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY is required for the Gemini C-3PO translator")

    def translate_offense_tackles(self, screenshot: Path) -> TackleScreenObservation:
        try:
            from google import genai
            from google.genai import types
        except ImportError as exc:
            raise RuntimeError("Install the 'google-genai' package for Gemini translation") from exc

        data = screenshot.read_bytes()
        mime = mimetypes.guess_type(screenshot.name)[0] or "image/png"
        with genai.Client(api_key=self.api_key, http_options=types.HttpOptions(timeout=self.timeout_ms)) as client:
            interaction = client.interactions.create(
                model=self.model,
                input=[{"type": "text", "text": PROMPT}, {"type": "image", "data": base64.b64encode(data).decode("ascii"), "mime_type": mime}],
                response_format={"type": "text", "mime_type": "application/json", "schema": TRANSLATOR_SCHEMA},
            )
        payload = json.loads(interaction.output_text)
        slots = {}
        for slot in TACKLE_SLOTS:
            raw = payload["slots"][slot]
            starter = PlayerObservation(**raw["starter"])
            backups = tuple(PlayerObservation(**row) for row in raw["backups"])
            slots[slot] = TackleSlotObservation(starter=starter, backups=backups)
        return TackleScreenObservation("OFFENSE", slots, "google-gemini", self.model)
