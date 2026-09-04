"""Clean-room C-3PO roster: provider transcription is the roster authority."""
from __future__ import annotations

import base64
import json
import mimetypes
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Iterable

VIEWS = ("OFFENSE", "DEFENSE", "SPECIAL TEAMS", "SPECIALISTS")

PROMPT = """You are C-3PO, a literal data-entry clerk reading one EA SPORTS
COLLEGE FOOTBALL 27 Team Manager screenshot. Identify the visible lineup view.
For every visible lineup slot, transcribe the slot label, player name, displayed
OVR, and visible backups. Report only what the pixels say. Do not search for,
infer, correct, reconcile, or replace player identity. If a name cannot be read,
return null. Return only the requested JSON structure."""

SCHEMA = {
    "type": "object",
    "properties": {
        "view": {"type": "string", "enum": list(VIEWS)},
        "players": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "slot": {"type": "string"},
                    "name": {"type": ["string", "null"]},
                    "displayed_ovr": {"type": ["integer", "null"]},
                    "backups": {"type": "array"},
                },
                "required": ["slot", "name", "displayed_ovr", "backups"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["view", "players"],
    "additionalProperties": False,
}


@dataclass(frozen=True)
class C3POPlayer:
    view: str
    slot: str
    name: str | None
    displayed_ovr: int | None
    backups: tuple[dict[str, Any], ...] = ()


@dataclass(frozen=True)
class C3PORoster:
    players: tuple[C3POPlayer, ...]
    provider: str
    model: str
    status: str = "C-3PO READ"


class C3PORosterStore:
    def __init__(self, path: Path):
        self.path = path

    def save(self, roster: C3PORoster) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "players": [asdict(player) for player in roster.players],
            "provider": roster.provider,
            "model": roster.model,
            "status": roster.status,
        }
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        temporary.replace(self.path)

    def load(self) -> C3PORoster:
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        players = tuple(
            C3POPlayer(
                view=row["view"],
                slot=row["slot"],
                name=row.get("name"),
                displayed_ovr=row.get("displayed_ovr"),
                backups=tuple(row.get("backups", [])),
            )
            for row in payload["players"]
        )
        return C3PORoster(
            players=players,
            provider=payload["provider"],
            model=payload["model"],
            status=payload.get("status", "C-3PO READ"),
        )


class GeminiC3POProvider:
    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        timeout_ms: int = 15000,
        client_factory: Callable[[], Any] | None = None,
    ):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.model = model or os.getenv("PANCAKE_GEMINI_MODEL", "gemini-3.7-flash")
        self.timeout_ms = timeout_ms
        self.client_factory = client_factory

    def _client(self):
        if self.client_factory is not None:
            return self.client_factory()
        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY is required for C-3PO transcription")
        from google import genai
        from google.genai import types

        return genai.Client(
            api_key=self.api_key,
            http_options=types.HttpOptions(timeout=self.timeout_ms),
        )

    def read(self, screenshot: Path) -> dict[str, Any]:
        try:
            data = screenshot.read_bytes()
            mime = mimetypes.guess_type(screenshot.name)[0] or "image/png"
            client = self._client()
            with client:
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
                        "schema": SCHEMA,
                    },
                )
            payload = json.loads(interaction.output_text)
            payload.update(provider="google-gemini", model=self.model, status="C-3PO READ")
            return payload
        except Exception as exc:
            return {
                "view": "",
                "players": [],
                "provider": "google-gemini",
                "model": self.model,
                "status": "PROVIDER FAILURE",
                "error": type(exc).__name__,
            }


def roster_from_screens(screenshots: Iterable[Path], provider: Any) -> C3PORoster:
    paths = tuple(screenshots)
    if len(paths) != 4:
        raise ValueError("C-3PO roster requires exactly four screenshots")
    reads = tuple(provider.read(path) for path in paths)
    failed = [read for read in reads if read.get("status") == "PROVIDER FAILURE"]
    if failed:
        return C3PORoster((), failed[0]["provider"], failed[0]["model"], "PROVIDER FAILURE")
    views = tuple(read["view"] for read in reads)
    if len(set(views)) != 4 or set(views) != set(VIEWS):
        raise ValueError("C-3PO must return one of each Team Manager view")
    players = []
    for read in reads:
        for row in read["players"]:
            players.append(
                C3POPlayer(
                    view=read["view"],
                    slot=str(row["slot"]).strip().upper(),
                    name=row.get("name"),
                    displayed_ovr=row.get("displayed_ovr"),
                    backups=tuple(row.get("backups", [])),
                )
            )
    return C3PORoster(tuple(players), reads[0]["provider"], reads[0]["model"])


class C3PORosterService:
    """The product boundary: four images in, persisted C-3PO roster out."""

    def __init__(self, store: C3PORosterStore, provider: Any):
        self.store = store
        self.provider = provider

    def import_four(self, screenshots: Iterable[Path]) -> C3PORoster:
        roster = roster_from_screens(screenshots, self.provider)
        if roster.status != "PROVIDER FAILURE":
            self.store.save(roster)
        return roster

    def my_team_html(self) -> str:
        from operation_pancake.c3po_roster_page import render_c3po_roster

        return render_c3po_roster(self.store.load())
