"""Unrestricted C-3PO program observation from persisted lineup pixels."""
from __future__ import annotations

import base64
import json
import logging
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Mapping, Protocol

if TYPE_CHECKING:
    from operation_pancake.c3po_roster import C3POPlayer
    from operation_pancake.c3po_source_evidence import C3POSourceEvidence

LOGGER = logging.getLogger(__name__)
# A full-roster multimodal analysis exceeded the former 60-second client cap.
# Keep one request and give that client-side operation a bounded three minutes.
DEFAULT_CARD_VERSION_TIMEOUT_MS = 180_000
WEAK_EVIDENCE = re.compile(
    r"\b(maybe|likely|probably|possibly|uncertain|appears|seems)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class CardVersionDecision:
    state: str
    program: str | None = None
    confidence: str | None = None
    positive_visual_evidence: tuple[str, ...] = ()

    @classmethod
    def ambiguous(cls) -> CardVersionDecision:
        return cls("AMBIGUOUS")

    @classmethod
    def no_evidence(cls) -> CardVersionDecision:
        return cls("NO_EVIDENCE")

    @classmethod
    def provider_failure(cls) -> CardVersionDecision:
        return cls("PROVIDER_FAILURE")

    @classmethod
    def identified(
        cls, program: str, evidence: tuple[str, ...]
    ) -> CardVersionDecision:
        return cls(
            "IDENTIFIED",
            program=program,
            confidence="HIGH",
            positive_visual_evidence=evidence,
        )


@dataclass(frozen=True)
class C3POCardObservation:
    fingerprint: str
    player_name: str
    displayed_ovr: int | None
    program: str | None
    state: str
    confidence: str | None = None
    positive_visual_evidence: tuple[str, ...] = ()


class C3POCardObservationStore:
    """Persist C-3PO program observations independently of the roster."""

    def __init__(self, path: Path):
        self.path = path

    def load(self) -> dict[str, C3POCardObservation]:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            return {}
        rows = payload.get("observations") if isinstance(payload, dict) else None
        if not isinstance(rows, list):
            return {}
        observations = {}
        for row in rows:
            if not isinstance(row, dict):
                continue
            fingerprint = row.get("fingerprint")
            player_name = row.get("player_name")
            if not isinstance(fingerprint, str) or not isinstance(player_name, str):
                continue
            evidence = row.get("positive_visual_evidence", [])
            observations[fingerprint] = C3POCardObservation(
                fingerprint=fingerprint,
                player_name=player_name,
                displayed_ovr=row.get("displayed_ovr"),
                program=row.get("program") if isinstance(row.get("program"), str) else None,
                state=str(row.get("state") or "UNCERTAIN"),
                confidence=(
                    row.get("confidence")
                    if isinstance(row.get("confidence"), str)
                    else None
                ),
                positive_visual_evidence=tuple(
                    item for item in evidence if isinstance(item, str) and item.strip()
                )
                if isinstance(evidence, list)
                else (),
            )
        return observations

    def save(self, observations: Mapping[str, C3POCardObservation]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        rows = []
        for fingerprint in sorted(observations):
            observation = observations[fingerprint]
            rows.append(
                {
                    "fingerprint": observation.fingerprint,
                    "player_name": observation.player_name,
                    "displayed_ovr": observation.displayed_ovr,
                    "program": observation.program,
                    "state": observation.state,
                    "confidence": observation.confidence,
                    "positive_visual_evidence": list(
                        observation.positive_visual_evidence
                    ),
                }
            )
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(
            json.dumps({"observations": rows}, indent=2) + "\n", encoding="utf-8"
        )
        temporary.replace(self.path)


@dataclass(frozen=True)
class CardVersionAnalysisRequest:
    fingerprint: str
    observation: C3POPlayer


@dataclass(frozen=True)
class CardVersionBatchResult:
    decisions: Mapping[str, CardVersionDecision]
    request_succeeded: bool
    rate_limited: bool = False
    timed_out: bool = False


@dataclass(frozen=True)
class CardVersionAnalysisOutcome:
    requested: int
    request_succeeded: bool
    provider_failed: bool = False
    rate_limited: bool = False
    timed_out: bool = False


class CardVersionAnalyzer(Protocol):
    """Optional downstream analyzer that observes a program, never identity."""

    def analyze_batch(
        self,
        requests: tuple[CardVersionAnalysisRequest, ...],
        evidence: C3POSourceEvidence,
    ) -> CardVersionBatchResult: ...


def _normalized_name(value: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", "", (value or "").casefold())


def _batch_prompt(requests: tuple[CardVersionAnalysisRequest, ...]) -> str:
    blocks = []
    for request in requests:
        observation = request.observation
        blocks.append(
            f"""OBSERVATION {request.fingerprint}
The player's identity is already established as {observation.name}.
Do not identify, rename, reject, or substitute this player.
Team Manager view: {observation.view}
Observed lineup slot: {observation.slot}
EA displayed OVR: {observation.displayed_ovr}"""
        )
    observations = "\n\n".join(blocks)
    return f"""Every player's identity is already established by C-3PO.
Do not identify, rename, reject, or substitute any player.

Inspect the supplied original EA Team Manager screenshot pixels and your knowledge
to report the visible card program/version for each observation below. No database
is supplied and no database constrains what you may report.

{observations}

Use visible card/program treatment, card design, rarity or program indicators, and
the immutable lineup context. EA displayed OVR is context, not sufficient by itself.
Do not guess. Weak, likely, probable, or uncertain evidence means UNCERTAIN. A
program absent from Pancake's data is still permitted.

Return JSON only as {{"results":[...]}} with at most one item per observation.
Each item must contain "observation_fingerprint" and "result". Result may be
"IDENTIFIED", "UNCERTAIN", or "NO_EVIDENCE". IDENTIFIED also requires an
unrestricted "program_version", "confidence":"HIGH", and a nonempty
"positive_visual_evidence" list of supporting facts. Never return a database card ID.
"""


def _clean_json(text: str) -> Any:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    return json.loads(cleaned)


def _decision(payload: Any) -> CardVersionDecision:
    if not isinstance(payload, dict):
        return CardVersionDecision.no_evidence()
    result = payload.get("result")
    if result in {"AMBIGUOUS", "UNCERTAIN"}:
        return CardVersionDecision.ambiguous()
    if result == "NO_EVIDENCE":
        return CardVersionDecision.no_evidence()
    if result == "PROVIDER_FAILURE":
        return CardVersionDecision.provider_failure()
    visual_evidence = payload.get("positive_visual_evidence")
    evidence_is_positive = (
        isinstance(visual_evidence, list)
        and bool(visual_evidence)
        and all(isinstance(item, str) and item.strip() for item in visual_evidence)
        and not any(WEAK_EVIDENCE.search(item) for item in visual_evidence)
    )
    program = payload.get("program_version")
    if (
        result == "IDENTIFIED"
        and payload.get("confidence") == "HIGH"
        and isinstance(program, str)
        and program.strip()
        and evidence_is_positive
    ):
        return CardVersionDecision.identified(
            program.strip(), tuple(item.strip() for item in visual_evidence)
        )
    return CardVersionDecision.no_evidence()


def _safe_quota_metadata(details: Any) -> tuple[str, str]:
    allowed = {"reason", "quotaMetric", "quotaId", "quotaValue", "retryDelay"}
    fields: list[tuple[str, str]] = []

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                if key in allowed and isinstance(child, (str, int, float)):
                    safe_value = re.sub(r"[^a-zA-Z0-9_.:/+-]", "_", str(child))[:160]
                    fields.append((key, safe_value))
                else:
                    visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(details)
    rendered = " ".join(f"{key}={value}" for key, value in fields)
    evidence = rendered.casefold()
    if "perday" in evidence or "per_day" in evidence or "per day" in evidence:
        classification = "DAILY_QUOTA"
    elif "perminute" in evidence or "per_minute" in evidence or "rpm" in evidence:
        classification = "RATE_QUOTA"
    elif "request_too_large" in evidence or "payload_too_large" in evidence:
        classification = "REQUEST_SIZE"
    elif "model" in evidence and ("unavailable" in evidence or "quotavalue=0" in evidence):
        classification = "MODEL_QUOTA_UNAVAILABLE"
    else:
        classification = "RESOURCE_EXHAUSTED_UNCLASSIFIED"
    return classification, rendered or "unavailable"


def _rate_limit_metadata(
    exc: Exception,
) -> tuple[bool, str | None, str, str, int | None, str, str]:
    code = getattr(exc, "code", None)
    status = str(getattr(exc, "status", "")).upper()
    response = getattr(exc, "response", None)
    status_code = getattr(response, "status_code", None)
    headers = getattr(response, "headers", {}) or {}
    retry_after = headers.get("retry-after") if hasattr(headers, "get") else None
    limited = (
        code == 429
        or status_code == 429
        or "RESOURCE_EXHAUSTED" in status
        or "RATELIMIT" in type(exc).__name__.upper()
    )
    provider_status = status or (str(code) if code is not None else "unavailable")
    detail = str(getattr(exc, "message", None) or exc)
    detail = re.sub(
        r"(?i)(api[_-]?key|key)\s*[=:]\s*[^\s,;}]+",
        r"\1=[REDACTED]",
        detail,
    )
    detail = re.sub(r"data:[^\s,;}]+", "data:[REDACTED]", detail)
    detail = " ".join(detail.split())[:240] or type(exc).__name__
    classification, quota = _safe_quota_metadata(getattr(exc, "details", None))
    return (
        limited,
        str(retry_after) if retry_after is not None else None,
        provider_status,
        detail,
        code if isinstance(code, int) else status_code,
        classification,
        quota,
    )


class GeminiCardVersionAnalyzer:
    """One bounded Gemini request that may resolve card version, never identity."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        timeout_ms: int | None = None,
        client_factory: Callable[[], Any] | None = None,
    ):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.model = model or os.getenv(
            "PANCAKE_GEMINI_VERSION_MODEL",
            os.getenv("PANCAKE_GEMINI_MODEL", "gemini-3.7-flash"),
        )
        configured_timeout = os.getenv("PANCAKE_GEMINI_VERSION_TIMEOUT_MS")
        if timeout_ms is not None:
            self.timeout_ms = timeout_ms
        elif configured_timeout:
            try:
                parsed_timeout = int(configured_timeout)
                self.timeout_ms = (
                    parsed_timeout
                    if parsed_timeout > 0
                    else DEFAULT_CARD_VERSION_TIMEOUT_MS
                )
            except ValueError:
                self.timeout_ms = DEFAULT_CARD_VERSION_TIMEOUT_MS
        else:
            self.timeout_ms = DEFAULT_CARD_VERSION_TIMEOUT_MS
        self.client_factory = client_factory

    def _client(self):
        if self.client_factory is not None:
            return self.client_factory()
        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY is required for card-version analysis")
        from google import genai
        from google.genai import types

        return genai.Client(
            api_key=self.api_key,
            http_options=types.HttpOptions(
                timeout=self.timeout_ms,
                retry_options=types.HttpRetryOptions(attempts=1),
            ),
        )

    def analyze_batch(
        self,
        requests: tuple[CardVersionAnalysisRequest, ...],
        evidence: C3POSourceEvidence,
    ) -> CardVersionBatchResult:
        bounded = tuple(
            CardVersionAnalysisRequest(request.fingerprint, request.observation)
            for request in requests
            if request.fingerprint and _normalized_name(request.observation.name)
        )
        if not bounded or len(evidence.images) != 4:
            return CardVersionBatchResult({}, request_succeeded=True)
        request_input: list[dict[str, str]] = [
            {"type": "text", "text": _batch_prompt(bounded)}
        ]
        for image in evidence.images:
            request_input.append(
                {
                    "type": "image",
                    "data": base64.b64encode(image.payload).decode("ascii"),
                    "mime_type": image.mime_type,
                }
            )
        started_at = time.monotonic()
        try:
            client = self._client()
            with client:
                interaction = client.interactions.create(
                    model=self.model, input=request_input
                )
        except Exception as exc:  # provider SDK/network failures are fail-open
            elapsed_ms = round((time.monotonic() - started_at) * 1000)
            (
                rate_limited,
                retry_after,
                provider_status,
                detail,
                http_status,
                classification,
                quota,
            ) = _rate_limit_metadata(exc)
            timed_out = "TIMEOUT" in type(exc).__name__.upper()
            if timed_out:
                rate_limited = False
                detail = "client_side_timeout"
            if timed_out:
                LOGGER.error(
                    "C-3PO program provider failure: TIMEOUT exception=%s "
                    "configured_timeout_ms=%d effective_timeout_seconds=%.3f "
                    "http_status=%s google_status=%s model=%s source_images=%d "
                    "source_bytes=%d work_items=%d elapsed_ms=%d detail=%s",
                    type(exc).__name__,
                    self.timeout_ms,
                    self.timeout_ms / 1000,
                    http_status or "unavailable",
                    provider_status,
                    self.model,
                    len(evidence.images),
                    sum(len(image.payload) for image in evidence.images),
                    len(bounded),
                    elapsed_ms,
                    detail,
                )
            elif rate_limited:
                LOGGER.error(
                    "C-3PO program provider failure: RATE_LIMITED exception=%s "
                    "http_status=%s google_status=%s classification=%s "
                    "retry_after=%s model=%s source_images=%d source_bytes=%d "
                    "work_items=%d quota=%s detail=%s",
                    type(exc).__name__,
                    http_status or "unavailable",
                    provider_status,
                    classification,
                    retry_after or "unavailable",
                    self.model,
                    len(evidence.images),
                    sum(len(image.payload) for image in evidence.images),
                    len(bounded),
                    quota,
                    detail,
                )
            else:
                LOGGER.error("C-3PO program provider failure: %s", type(exc).__name__)
            return CardVersionBatchResult(
                {},
                request_succeeded=False,
                rate_limited=rate_limited,
                timed_out=timed_out,
            )

        text = getattr(interaction, "output_text", None)
        if not isinstance(text, str) or not text.strip():
            return CardVersionBatchResult({}, request_succeeded=True)
        try:
            payload = _clean_json(text)
        except (json.JSONDecodeError, TypeError):
            return CardVersionBatchResult({}, request_succeeded=True)
        rows = payload.get("results") if isinstance(payload, dict) else None
        if not isinstance(rows, list):
            return CardVersionBatchResult({}, request_succeeded=True)
        allowed = {request.fingerprint for request in bounded}
        decisions: dict[str, CardVersionDecision] = {}
        duplicates = set()
        for row in rows:
            fingerprint = (
                row.get("observation_fingerprint") if isinstance(row, dict) else None
            )
            if fingerprint not in allowed:
                continue
            if fingerprint in decisions:
                duplicates.add(fingerprint)
            else:
                decisions[fingerprint] = _decision(row)
        for fingerprint in duplicates:
            decisions[fingerprint] = CardVersionDecision.no_evidence()
        return CardVersionBatchResult(decisions, request_succeeded=True)

    def analyze(
        self,
        observation: C3POPlayer,
        evidence: C3POSourceEvidence,
    ) -> CardVersionDecision:
        """Compatibility helper for focused single-observation diagnostics."""
        fingerprint = "single-observation"
        result = self.analyze_batch(
            (CardVersionAnalysisRequest(fingerprint, observation),), evidence
        )
        if not result.request_succeeded:
            return CardVersionDecision.provider_failure()
        return result.decisions.get(fingerprint, CardVersionDecision.no_evidence())
