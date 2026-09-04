# ruff: noqa: E501
"""Clean-room C-3PO roster: provider transcription is the roster authority."""
from __future__ import annotations

import base64
import json
import logging
import mimetypes
import os
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Iterable

VIEWS = ("OFFENSE", "DEFENSE", "SPECIAL TEAMS", "SPECIALISTS")
LOGGER = logging.getLogger(__name__)

PROMPT = """You are C-3PO, a literal data-entry clerk. Read the four attached
EA SPORTS COLLEGE FOOTBALL 27 Team Manager screenshots. The four sections are
OFFENSE, DEFENSE, SPECIAL TEAMS, and SPECIALISTS. For every visible lineup slot,
transcribe only what the pixels show: section, slot label, visible player name,
and displayed OVR when readable. Include visible backups as additional player
rows using their visible slot label when present. Do not search, infer, correct,
reconcile, or replace a player name. If a name cannot be read, use null.
Return JSON only, preferably as:
{"screens":[{"view":"OFFENSE","players":[{"slot":"LT1","name":"...",
"displayed_ovr":80}]}]}
One screen object per attached screenshot. Partial readable transcription is
useful; never omit a readable named player because another field is missing."""


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
        payload = {"players": [asdict(player) for player in roster.players], "provider": roster.provider, "model": roster.model, "status": roster.status}
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        temporary.replace(self.path)

    def load(self) -> C3PORoster:
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        players = tuple(C3POPlayer(view=row["view"], slot=row["slot"], name=row.get("name"), displayed_ovr=row.get("displayed_ovr"), backups=tuple(row.get("backups", []))) for row in payload["players"])
        return C3PORoster(players=players, provider=payload["provider"], model=payload["model"], status=payload.get("status", "C-3PO READ"))


def _mime(path: Path) -> str:
    guessed = mimetypes.guess_type(path.name)[0]
    if guessed in {"image/jpeg", "image/png", "image/webp"}:
        return guessed
    suffix = path.suffix.lower()
    if suffix in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if suffix == ".png":
        return "image/png"
    if suffix == ".webp":
        return "image/webp"
    raise ValueError(f"Unsupported screenshot image type: {suffix or 'unknown'}")


def _json_text(text: str) -> Any:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        starts = [index for index in (cleaned.find("{"), cleaned.find("[")) if index >= 0]
        if not starts:
            raise
        start = min(starts)
        end = max(cleaned.rfind("}"), cleaned.rfind("]"))
        if end < start:
            raise
        return json.loads(cleaned[start : end + 1])


def _view(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip().upper().replace("_", " ").replace("-", " ")
    normalized = {"SPECIAL TEAM": "SPECIAL TEAMS", "SPECIALIST": "SPECIALISTS"}.get(normalized, normalized)
    return normalized if normalized in VIEWS else None


def _ovr(value: Any) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, int):
        return value
    match = re.search(r"\b(\d{2,3})\b", str(value))
    return int(match.group(1)) if match else None


def _rows_from_payload(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        screens = payload
    elif isinstance(payload, dict):
        screens = payload.get("screens") or payload.get("views") or payload.get("sections")
        if screens is None and payload.get("players") is not None:
            screens = [payload]
    else:
        screens = None
    if not isinstance(screens, list):
        raise ValueError("Gemini JSON did not contain screens/sections")
    rows: list[dict[str, Any]] = []
    for screen in screens:
        if not isinstance(screen, dict):
            continue
        view = _view(screen.get("view") or screen.get("section") or screen.get("screen"))
        if view is None:
            continue
        players = screen.get("players") or screen.get("slots") or screen.get("lineup") or []
        if isinstance(players, dict):
            players = [dict(value, slot=key) if isinstance(value, dict) else {"slot": key, "name": value} for key, value in players.items()]
        if not isinstance(players, list):
            continue
        for player in players:
            if not isinstance(player, dict):
                continue
            slot = player.get("slot") or player.get("slot_label") or player.get("position")
            if not slot:
                continue
            name = player.get("name") if player.get("name") is not None else player.get("player_name")
            if isinstance(name, str):
                name = name.strip() or None
            rows.append({"view": view, "slot": str(slot).strip().upper(), "name": name, "displayed_ovr": _ovr(player.get("displayed_ovr", player.get("ovr", player.get("rating")))), "backups": player.get("backups") if isinstance(player.get("backups"), list) else []})
    return rows


def _safe_message(exc: Exception) -> str:
    return " ".join(str(exc).split())[:500] or "no message"


class GeminiC3POProvider:
    def __init__(self, api_key: str | None = None, model: str | None = None, timeout_ms: int = 60000, client_factory: Callable[[], Any] | None = None):
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
        return genai.Client(api_key=self.api_key, http_options=types.HttpOptions(timeout=self.timeout_ms))

    def read_four(self, screenshots: Iterable[Path]) -> list[dict[str, Any]]:
        paths = tuple(screenshots)
        if len(paths) != 4:
            raise ValueError("C-3PO provider requires exactly four screenshots")
        try:
            request_input: list[dict[str, str]] = [{"type": "text", "text": PROMPT}]
            for path in paths:
                data = path.read_bytes()
                if not data:
                    raise ValueError(f"Screenshot is empty: {path.name}")
                request_input.append({"type": "image", "data": base64.b64encode(data).decode("ascii"), "mime_type": _mime(path)})
            client = self._client()
            with client:
                interaction = client.interactions.create(model=self.model, input=request_input)
            text = getattr(interaction, "output_text", None)
            if not isinstance(text, str) or not text.strip():
                raise RuntimeError("Gemini returned no textual content")
            try:
                rows = _rows_from_payload(_json_text(text))
            except Exception as exc:
                snippet = " ".join(text.split())[:500]
                raise ValueError(f"Gemini returned text but parsing failed; snippet={snippet!r}") from exc
            if not rows:
                raise ValueError("Gemini returned textual content but no usable lineup rows")
            return [{"view": view, "players": [{key: value for key, value in row.items() if key != "view"} for row in rows if row["view"] == view], "provider": "google-gemini", "model": self.model, "status": "C-3PO READ"} for view in VIEWS]
        except Exception as exc:
            message = _safe_message(exc)
            LOGGER.error("C-3PO Gemini provider failure: %s: %s", type(exc).__name__, message)
            return [{"view": "", "players": [], "provider": "google-gemini", "model": self.model, "status": "PROVIDER FAILURE", "error": type(exc).__name__, "error_message": message}]

    def read(self, screenshot: Path) -> dict[str, Any]:
        """Compatibility helper for provider-level single-image diagnostics."""
        try:
            data = screenshot.read_bytes()
            request_input = [{"type": "text", "text": PROMPT}, {"type": "image", "data": base64.b64encode(data).decode("ascii"), "mime_type": _mime(screenshot)}]
            client = self._client()
            with client:
                interaction = client.interactions.create(model=self.model, input=request_input)
            text = getattr(interaction, "output_text", None)
            if not text:
                raise RuntimeError("Gemini returned no textual content")
            rows = _rows_from_payload(_json_text(text))
            if not rows:
                raise ValueError("Gemini returned textual content but no usable lineup rows")
            view = rows[0]["view"]
            return {"view": view, "players": [{key: value for key, value in row.items() if key != "view"} for row in rows if row["view"] == view], "provider": "google-gemini", "model": self.model, "status": "C-3PO READ"}
        except Exception as exc:
            message = _safe_message(exc)
            LOGGER.error("C-3PO Gemini provider failure: %s: %s", type(exc).__name__, message)
            return {"view": "", "players": [], "provider": "google-gemini", "model": self.model, "status": "PROVIDER FAILURE", "error": type(exc).__name__, "error_message": message}


def roster_from_screens(screenshots: Iterable[Path], provider: Any) -> C3PORoster:
    paths = tuple(screenshots)
    if len(paths) != 4:
        raise ValueError("C-3PO roster requires exactly four screenshots")
    reads = tuple(provider.read_four(paths)) if hasattr(provider, "read_four") else tuple(provider.read(path) for path in paths)
    failed = [read for read in reads if read.get("status") == "PROVIDER FAILURE"]
    if failed:
        return C3PORoster((), failed[0]["provider"], failed[0]["model"], "PROVIDER FAILURE")
    players = []
    for read in reads:
        view = _view(read.get("view"))
        if view is None:
            continue
        for row in read.get("players", []):
            slot = row.get("slot")
            if not slot:
                continue
            players.append(C3POPlayer(view=view, slot=str(slot).strip().upper(), name=row.get("name"), displayed_ovr=_ovr(row.get("displayed_ovr")), backups=tuple(row.get("backups", []))))
    if not players:
        raise ValueError("C-3PO returned no usable lineup rows")
    return C3PORoster(tuple(players), reads[0]["provider"], reads[0]["model"])


class C3PORosterService:
    """The product boundary: four images in, persisted C-3PO roster out."""
    def __init__(
        self,
        store: C3PORosterStore,
        provider: Any,
        enrichment_cards: Iterable[dict[str, Any]] | None = None,
        card_choice_store: Any | None = None,
        source_evidence_store: Any | None = None,
        version_analyzer: Any | None = None,
    ):
        self.store = store
        self.provider = provider
        self.enrichment_cards = (
            None if enrichment_cards is None else tuple(enrichment_cards)
        )
        self.card_choice_store = card_choice_store
        self.source_evidence_store = source_evidence_store
        self.version_analyzer = version_analyzer

    def import_four(self, screenshots: Iterable[Path]) -> C3PORoster:
        paths = tuple(screenshots)
        roster = roster_from_screens(paths, self.provider)
        if roster.status != "PROVIDER FAILURE":
            if self.source_evidence_store is not None:
                try:
                    self.source_evidence_store.save(roster, paths)
                except (OSError, ValueError, TypeError):
                    LOGGER.exception("C-3PO source evidence could not be persisted")
            self.store.save(roster)
            self.analyze_card_versions(roster)
        return roster

    def my_team_html(self) -> str:
        return self.render_html(self.store.load())

    def render_html(self, roster: C3PORoster) -> str:
        from operation_pancake.c3po_roster_page import render_c3po_roster
        from operation_pancake.cfb27_enrichment import enrich_c3po_roster

        enrichment = None
        if self.enrichment_cards is not None:
            stored_choices = (
                self.card_choice_store.load() if self.card_choice_store is not None else {}
            )
            enrichment = enrich_c3po_roster(
                roster, self.enrichment_cards, stored_choices
            )
        return render_c3po_roster(roster, enrichment)

    def analyze_card_versions(self, roster: C3PORoster):
        """Analyze unresolved card versions once, at the successful import event."""
        from operation_pancake.c3po_card_version import (
            CardVersionAnalysisOutcome,
            CardVersionAnalysisRequest,
            CardVersionBatchResult,
        )
        from operation_pancake.cfb27_enrichment import enrich_c3po_roster

        if (
            self.enrichment_cards is None
            or self.card_choice_store is None
            or self.source_evidence_store is None
            or self.version_analyzer is None
        ):
            return CardVersionAnalysisOutcome(0, request_succeeded=False)
        stored_choices = self.card_choice_store.load()
        enrichment = enrich_c3po_roster(
            roster, self.enrichment_cards, stored_choices
        )
        ambiguous = tuple(row for row in enrichment.players if row.state == "SELECT CARD")
        if not ambiguous:
            return CardVersionAnalysisOutcome(0, request_succeeded=True)
        try:
            evidence = self.source_evidence_store.load_for(roster)
        except (OSError, ValueError, TypeError):
            LOGGER.exception("C-3PO source evidence could not be loaded")
            evidence = None
        if evidence is None:
            for row in ambiguous:
                LOGGER.info(
                    "VERSION ANALYZER NOT INVOKED player=%s candidates=%d "
                    "source_evidence_compatible=no source_images=0 result=NO_EVIDENCE",
                    row.observation.name,
                    len(row.choices),
                )
            return CardVersionAnalysisOutcome(
                len(ambiguous), request_succeeded=False
            )

        updated_choices = dict(stored_choices)
        changed = False
        work: dict[tuple[Any, ...], list[Any]] = {}
        for row in ambiguous:
            observation = row.observation
            evidence_key = (
                observation.view,
                observation.slot,
                observation.name,
                observation.displayed_ovr,
                json.dumps(observation.backups, sort_keys=True),
                tuple(card.card_id for card in row.choices),
            )
            work.setdefault(evidence_key, []).append(row)
        work_groups = tuple(work.values())
        requests = tuple(
            CardVersionAnalysisRequest(
                rows[0].fingerprint, rows[0].observation, rows[0].choices
            )
            for rows in work_groups
        )
        try:
            batch_result = self.version_analyzer.analyze_batch(requests, evidence)
        except Exception:  # analyzer failures must never hide the roster
            LOGGER.exception("CFB27 card-version batch analysis failed")
            batch_result = CardVersionBatchResult(
                {}, request_succeeded=False
            )
        if not batch_result.request_succeeded:
            result_state = (
                "RATE_LIMITED" if batch_result.rate_limited else "PROVIDER_FAILURE"
            )
            LOGGER.info(
                "VERSION ANALYZER BATCH request_count=1 work_items=%d "
                "roster_observations=%d source_evidence_compatible=yes "
                "source_images=%d result=%s",
                len(requests),
                len(ambiguous),
                len(evidence.images),
                result_state,
            )
            return CardVersionAnalysisOutcome(
                len(requests),
                request_succeeded=False,
                provider_failed=True,
                rate_limited=batch_result.rate_limited,
            )

        LOGGER.info(
            "VERSION ANALYZER BATCH request_count=1 work_items=%d "
            "roster_observations=%d source_evidence_compatible=yes "
            "source_images=%d result=SUCCEEDED",
            len(requests),
            len(ambiguous),
            len(evidence.images),
        )
        for rows in work_groups:
            representative = rows[0]
            decision = batch_result.decisions.get(representative.fingerprint)
            decision_state = getattr(decision, "state", "NO_EVIDENCE")
            decision_card_id = getattr(decision, "card_id", None)
            valid_cards = {card.card_id: card for card in representative.choices}
            selected = valid_cards.get(decision_card_id)
            if decision_state == "UNIQUE_VERSION" and selected is not None:
                for row in rows:
                    updated_choices[row.fingerprint] = decision_card_id
                changed = True
                LOGGER.info(
                    "VERSION ANALYZER RESULT player=%s fingerprint=%s "
                    "view=%s slot=%s candidates=%d duplicates=%d "
                    "source_evidence_compatible=yes source_images=%d "
                    "result=UNIQUE_VERSION card_id=%s program=%s native_ovr=%s",
                    representative.observation.name,
                    representative.fingerprint[:12],
                    representative.observation.view,
                    representative.observation.slot,
                    len(representative.choices),
                    len(rows) - 1,
                    len(evidence.images),
                    selected.card_id,
                    selected.program,
                    selected.card_ovr,
                )
            else:
                LOGGER.info(
                    "VERSION ANALYZER RESULT player=%s fingerprint=%s "
                    "view=%s slot=%s candidates=%d duplicates=%d "
                    "source_evidence_compatible=yes source_images=%d result=%s",
                    representative.observation.name,
                    representative.fingerprint[:12],
                    representative.observation.view,
                    representative.observation.slot,
                    len(representative.choices),
                    len(rows) - 1,
                    len(evidence.images),
                    decision_state,
                )
        if changed:
            try:
                self.card_choice_store.save(updated_choices)
            except (OSError, ValueError, TypeError):
                LOGGER.exception("Automatic card-version choice could not be persisted")
        return CardVersionAnalysisOutcome(
            len(requests), request_succeeded=True
        )

    def select_card_version(self, fingerprint: str, card_id: str) -> bool:
        from operation_pancake.cfb27_enrichment import enrich_c3po_roster

        if self.enrichment_cards is None or self.card_choice_store is None:
            return False
        try:
            roster = self.store.load()
            enrichment = enrich_c3po_roster(roster, self.enrichment_cards)
            target = next(
                (row for row in enrichment.players if row.fingerprint == fingerprint),
                None,
            )
            if target is None or target.state != "SELECT CARD":
                return False
            if card_id not in {card.card_id for card in target.choices}:
                return False
            choices = self.card_choice_store.load()
            choices[fingerprint] = card_id
            self.card_choice_store.save(choices)
            return True
        except (OSError, ValueError, TypeError):
            return False
