# ruff: noqa: E501
"""Clean-room C-3PO roster: provider transcription is the roster authority."""
from __future__ import annotations

import base64
import hashlib
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
displayed chemistry-adjusted OVR when readable, and visually identified card program/type.
Displayed OVR is not base card OVR and must not be used to infer the program.
Inspect the actual card art/design to identify its program where readable.
Include visible backups as additional player rows using their visible slot label
when present. Do not search, infer, correct, reconcile, or replace a player name,
OVR, or program. If a name or program cannot be read, use null.
Return JSON only, preferably as:
{"screens":[{"view":"OFFENSE","players":[{"slot":"LT1","name":"...",
"displayed_ovr":80,"program":"..."}]}]}
One screen object per attached screenshot. Partial readable transcription is
useful; never omit a readable named player because another field is missing."""


@dataclass(frozen=True)
class C3POPlayer:
    view: str
    slot: str
    name: str | None
    displayed_ovr: int | None
    backups: tuple[dict[str, Any], ...] = ()
    program: str | None = None


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
        players = tuple(C3POPlayer(view=row["view"], slot=row["slot"], name=row.get("name"), displayed_ovr=row.get("displayed_ovr"), backups=tuple(row.get("backups", [])), program=row.get("program") if isinstance(row.get("program"), str) else None) for row in payload["players"])
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


def _program(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value or None


def _rows_from_payload(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        screens = payload
    elif isinstance(payload, dict):
        screens = payload.get("screens") or payload.get("views") or payload.get("sections")
        if screens is None and any(payload.get(key) is not None for key in ("players", "slots", "lineup")):
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
            starter = player.get("starter")
            observation = starter if isinstance(starter, dict) else player
            name = observation.get("name")
            if name is None:
                name = observation.get("player_name", observation.get("observed_name"))
            if isinstance(name, str):
                name = name.strip() or None
            rows.append({"view": view, "slot": str(slot).strip().upper(), "name": name, "displayed_ovr": _ovr(observation.get("displayed_ovr", observation.get("ovr", observation.get("rating")))), "program": _program(observation.get("program", observation.get("card_program", observation.get("card_version")))), "backups": player.get("backups") if isinstance(player.get("backups"), list) else []})
    return rows


def _safe_message(exc: Exception) -> str:
    return " ".join(str(exc).split())[:500] or "no message"


class GeminiC3POProvider:
    def __init__(self, api_key: str | None = None, model: str | None = None, timeout_ms: int = 60000, client_factory: Callable[[], Any] | None = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.model = model or os.getenv("PANCAKE_GEMINI_MODEL", "gemini-3.7-flash")
        self.timeout_ms = timeout_ms
        self.client_factory = client_factory
        self.request_count = 0

    def _client(self):
        if self.client_factory is not None:
            return self.client_factory()
        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY is required for C-3PO transcription")
        from google import genai
        from google.genai import types
        return genai.Client(api_key=self.api_key, http_options=types.HttpOptions(timeout=self.timeout_ms, retry_options=types.HttpRetryOptions(attempts=1)))

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
                self.request_count += 1
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
                self.request_count += 1
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
            players.append(C3POPlayer(view=view, slot=str(slot).strip().upper(), name=row.get("name"), displayed_ovr=_ovr(row.get("displayed_ovr")), backups=tuple(row.get("backups", [])), program=_program(row.get("program"))))
    if not players:
        raise ValueError("C-3PO returned no usable lineup rows")
    return C3PORoster(tuple(players), reads[0]["provider"], reads[0]["model"])


def roster_from_partial_screens(screenshots: Iterable[Path], provider: Any) -> tuple[C3PORoster, tuple[str, ...]]:
    paths = tuple(screenshots)
    if not 1 <= len(paths) <= 3:
        raise ValueError("Partial C-3PO roster update requires one to three screenshots")
    reads = tuple(provider.read(path) for path in paths)
    if any(read.get("status") == "PROVIDER FAILURE" for read in reads):
        raise ValueError("C-3PO could not read one or more supplied screenshots")
    views = tuple(_view(read.get("view")) for read in reads)
    if any(view is None for view in views):
        raise ValueError("C-3PO could not identify every supplied Team Manager section")
    if len(set(views)) != len(views):
        raise ValueError("Each supplied Team Manager screenshot must be a different section")
    players = []
    for read, view in zip(reads, views, strict=True):
        for row in read.get("players", []):
            slot = row.get("slot")
            if slot:
                players.append(C3POPlayer(view=view, slot=str(slot).strip().upper(), name=row.get("name"), displayed_ovr=_ovr(row.get("displayed_ovr")), backups=tuple(row.get("backups", [])), program=_program(row.get("program"))))
    if not players:
        raise ValueError("C-3PO returned no usable lineup rows")
    first = reads[0]
    return C3PORoster(tuple(players), first["provider"], first["model"]), tuple(view for view in views if view is not None)


def card_version_work_groups(roster: C3PORoster) -> tuple[tuple[Any, ...], ...]:
    """Group only byte-for-byte equivalent immutable version questions."""
    work: dict[tuple[Any, ...], list[Any]] = {}
    for occurrence, observation in roster_observations(roster):
        if not observation.name or not observation.name.strip():
            continue
        fingerprint = observation_fingerprint(observation, occurrence)
        evidence_key = (observation.view, observation.slot, observation.name, observation.displayed_ovr, json.dumps(observation.backups, sort_keys=True))
        work.setdefault(evidence_key, []).append((fingerprint, observation))
    return tuple(tuple(group) for group in work.values())


def observation_fingerprint(observation: C3POPlayer, occurrence: int | str) -> str:
    """Bind downstream observations to one immutable C-3PO roster row."""
    evidence = json.dumps([re.sub(r"[^a-z0-9]+", "", (observation.name or "").casefold()), observation.view, observation.slot, observation.displayed_ovr, occurrence], separators=(",", ":"))
    return hashlib.sha256(evidence.encode("utf-8")).hexdigest()


def roster_observations(roster: C3PORoster) -> tuple[tuple[int | str, C3POPlayer], ...]:
    """Expose top-level and nested provider observations without changing storage."""
    rows: list[tuple[int | str, C3POPlayer]] = []
    for occurrence, player in enumerate(roster.players):
        rows.append((occurrence, player))
        parent_position = re.sub(r"\s*\d+$", "", player.slot).strip() or player.slot
        for backup_index, backup in enumerate(player.backups):
            if not isinstance(backup, dict):
                continue
            slot = backup.get("slot") or backup.get("slot_label")
            if not slot:
                slot = f"{parent_position}{backup_index + 2}"
            name = backup.get("name", backup.get("player_name", backup.get("observed_name")))
            if isinstance(name, str):
                name = name.strip() or None
            rows.append((f"{occurrence}:backup:{backup_index}", C3POPlayer(player.view, str(slot).strip().upper(), name, _ovr(backup.get("displayed_ovr", backup.get("ovr"))), program=_program(backup.get("program", backup.get("card_program", backup.get("card_version")))))))
    return tuple(rows)


class C3PORosterService:
    """The product boundary: four images in, persisted C-3PO roster out."""
    def __init__(self, store: C3PORosterStore, provider: Any, enrichment_cards: Iterable[dict[str, Any]] | Callable[[], Iterable[dict[str, Any]]] | None = None, card_choice_store: Any | None = None, source_evidence_store: Any | None = None, version_analyzer: Any | None = None, card_observation_store: Any | None = None, card_art_root: Path | None = None):
        self.store = store
        self.provider = provider
        self.enrichment_cards = enrichment_cards
        self.card_choice_store = card_choice_store
        self.source_evidence_store = source_evidence_store
        self.version_analyzer = version_analyzer
        if card_observation_store is None:
            from operation_pancake.c3po_card_version import C3POCardObservationStore
            card_observation_store = C3POCardObservationStore(store.path.parent / "c3po-programs.json")
        self.card_observation_store = card_observation_store
        self.card_art_root = card_art_root

    def _exact_art(self, observation: C3POPlayer, program: str | None):
        from operation_pancake.card_art import resolve_exact_card_art
        cards = self.enrichment_cards() if callable(self.enrichment_cards) else self.enrichment_cards
        return resolve_exact_card_art(cards or (), observation.name, program)

    def persist_inline_programs(self, roster: C3PORoster) -> int:
        if self.card_observation_store is None:
            return 0
        from operation_pancake.c3po_card_version import C3POCardObservation
        programs = {}
        for occurrence, observation in roster_observations(roster):
            if not observation.name or not observation.program:
                continue
            card_id, art_asset = self._exact_art(observation, observation.program)
            fingerprint = observation_fingerprint(observation, occurrence)
            programs[fingerprint] = C3POCardObservation(
                fingerprint=fingerprint,
                player_name=observation.name,
                displayed_ovr=observation.displayed_ovr,
                program=observation.program,
                state="IDENTIFIED" if observation.program else "UNCERTAIN",
                confidence="HIGH" if observation.program else None,
                positive_visual_evidence=("program read in roster screenshot request",) if observation.program else (),
                card_id=card_id,
                art_asset=art_asset,
            )
        if programs:
            self.card_observation_store.save(programs)
        return len(programs)

    def import_screenshots(self, screenshots: Iterable[Path]) -> C3PORoster:
        paths = tuple(screenshots)
        if len(paths) == 4:
            return self.import_four(paths)
        if not 1 <= len(paths) <= 3:
            raise ValueError("One to four Team Manager screenshots are required")
        if not self.store.path.exists():
            raise ValueError("Upload all four Team Manager screenshots for initial setup")
        try:
            previous = self.store.load()
        except (OSError, ValueError, TypeError) as exc:
            raise ValueError("A valid saved roster is required for a partial update") from exc
        incoming, supplied_views = roster_from_partial_screens(paths, self.provider)
        incoming_by_view = {view: tuple(player for player in incoming.players if player.view == view) for view in supplied_views}
        for view in supplied_views:
            previous_count = sum(player.view == view for player in previous.players)
            if len(incoming_by_view[view]) < previous_count:
                raise ValueError(f"C-3PO returned fewer observations for {view}; saved roster was not changed")
        merged_players = []
        for view in VIEWS:
            merged_players.extend(incoming_by_view.get(view, tuple(player for player in previous.players if player.view == view)))
        merged = C3PORoster(tuple(merged_players), incoming.provider, incoming.model)
        if self.card_observation_store is not None:
            from dataclasses import replace
            old_cards = self.card_observation_store.load()
            old_rows = {}
            old_counts = {}
            for occurrence, player in roster_observations(previous):
                key = (player.view, player.slot, re.sub(r"[^a-z0-9]+", "", (player.name or "").casefold()))
                ordinal = old_counts.get(key, 0)
                old_counts[key] = ordinal + 1
                prior = old_cards.get(observation_fingerprint(player, occurrence))
                if prior is not None:
                    old_rows[(key, ordinal)] = prior
            preserved = {}
            new_counts = {}
            for occurrence, player in roster_observations(merged):
                key = (player.view, player.slot, re.sub(r"[^a-z0-9]+", "", (player.name or "").casefold()))
                ordinal = new_counts.get(key, 0)
                new_counts[key] = ordinal + 1
                prior = old_rows.get((key, ordinal))
                if prior is None or (player.program and player.program != prior.program):
                    continue
                fingerprint = observation_fingerprint(player, occurrence)
                preserved[fingerprint] = replace(prior, fingerprint=fingerprint, player_name=player.name or "", displayed_ovr=player.displayed_ovr)
            if preserved:
                self.card_observation_store.save(preserved)
        else:
            preserved = {}
        resolve_fingerprints = {
            observation_fingerprint(player, occurrence)
            for occurrence, player in roster_observations(merged)
            if player.view in supplied_views
            and observation_fingerprint(player, occurrence) not in preserved
        }
        self.store.save(merged)
        from operation_pancake.c3po_card_import import complete_import
        complete_import(self, merged, resolve_fingerprints=resolve_fingerprints)
        return merged

    def import_four(self, screenshots: Iterable[Path]) -> C3PORoster:
        paths = tuple(screenshots)
        roster = roster_from_screens(paths, self.provider)
        if roster.status != "PROVIDER FAILURE":
            try:
                previous = self.store.load() if self.store.path.exists() else None
            except (OSError, ValueError, TypeError):
                previous = None
            incoming_count = len(roster_observations(roster))
            previous_count = len(roster_observations(previous)) if previous is not None else 0
            if previous is not None and incoming_count < previous_count:
                LOGGER.warning("C-3PO partial import ignored: incoming=%d authoritative=%d", incoming_count, previous_count)
                return previous
            if self.source_evidence_store is not None:
                try:
                    self.source_evidence_store.save(roster, paths)
                except (OSError, ValueError, TypeError):
                    LOGGER.exception("C-3PO source evidence could not be persisted")
            self.store.save(roster)
            from operation_pancake.c3po_card_import import complete_import
            complete_import(self, roster)
        return roster

    def my_team_html(self) -> str:
        return self.render_html(self.store.load())

    def render_html(self, roster: C3PORoster) -> str:
        from operation_pancake.c3po_roster_page import render_c3po_roster
        programs = self.card_observation_store.load() if self.card_observation_store is not None else {}
        return render_c3po_roster(roster, programs)

    def analyze_card_versions(self, roster: C3PORoster):
        """Explicit legacy-compatible analyzer; normal imports never invoke it."""
        from operation_pancake.c3po_card_version import (
            CardVersionAnalysisOutcome,
            CardVersionAnalysisRequest,
            CardVersionBatchResult,
            CardVersionDecision,
        )
        if self.source_evidence_store is None or self.version_analyzer is None or self.card_observation_store is None:
            return CardVersionAnalysisOutcome(0, request_succeeded=False)
        work_groups = card_version_work_groups(roster)
        if not work_groups:
            return CardVersionAnalysisOutcome(0, request_succeeded=True)
        try:
            evidence = self.source_evidence_store.load_for(roster)
        except (OSError, ValueError, TypeError):
            LOGGER.exception("C-3PO source evidence could not be loaded")
            evidence = None
        if evidence is None:
            return CardVersionAnalysisOutcome(len(work_groups), request_succeeded=False)
        requests = tuple(CardVersionAnalysisRequest(group[0][0], group[0][1]) for group in work_groups)
        roster_observations_count = sum(len(group) for group in work_groups)
        try:
            batch_result = self.version_analyzer.analyze_batch(requests, evidence)
        except Exception:
            LOGGER.exception("C-3PO program batch analysis failed")
            batch_result = CardVersionBatchResult({}, request_succeeded=False)
        if not batch_result.request_succeeded:
            result = (
                "RATE_LIMITED"
                if batch_result.rate_limited
                else "TIMEOUT"
                if batch_result.timed_out
                else "PROVIDER_FAILURE"
            )
            LOGGER.info(
                "VERSION ANALYZER BATCH request_count=1 work_items=%d "
                "roster_observations=%d source_evidence_compatible=yes "
                "source_images=%d result=%s",
                len(requests),
                roster_observations_count,
                len(evidence.images),
                result,
            )
            return CardVersionAnalysisOutcome(len(requests), request_succeeded=False, provider_failed=True, rate_limited=batch_result.rate_limited, timed_out=batch_result.timed_out)
        from operation_pancake.c3po_card_version import C3POCardObservation
        updated_observations = {}
        for group in work_groups:
            representative_fingerprint, representative = group[0]
            decision = batch_result.decisions.get(representative_fingerprint, CardVersionDecision.no_evidence())
            LOGGER.info(
                "VERSION ANALYZER RESULT player=%s result=%s program=%s",
                representative.name,
                decision.state,
                decision.program or "not-read",
            )
            if decision.state in {"IDENTIFIED", "AMBIGUOUS", "NO_EVIDENCE"}:
                for fingerprint, observation in group:
                    card_id, art_asset = self._exact_art(observation, decision.program)
                    updated_observations[fingerprint] = C3POCardObservation(
                        fingerprint=fingerprint,
                        player_name=observation.name or "",
                        displayed_ovr=observation.displayed_ovr,
                        program=decision.program,
                        state="IDENTIFIED" if decision.state == "IDENTIFIED" else "UNCERTAIN",
                        confidence=decision.confidence,
                        positive_visual_evidence=decision.positive_visual_evidence,
                        card_id=card_id,
                        art_asset=art_asset,
                    )
        self.card_observation_store.save(updated_observations)
        LOGGER.info(
            "VERSION ANALYZER BATCH request_count=1 work_items=%d "
            "roster_observations=%d source_evidence_compatible=yes "
            "source_images=%d result=SUCCESS",
            len(requests),
            roster_observations_count,
            len(evidence.images),
        )
        return CardVersionAnalysisOutcome(len(requests), request_succeeded=True)
