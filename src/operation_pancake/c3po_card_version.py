"""Narrow result contract for optional CFB27 card-version analysis."""
from __future__ import annotations

import base64
import json
import logging
import os
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable, Mapping, Protocol

if TYPE_CHECKING:
    from operation_pancake.c3po_roster import C3POPlayer
    from operation_pancake.c3po_source_evidence import C3POSourceEvidence
    from operation_pancake.cfb27_enrichment import CFB27CardData

LOGGER = logging.getLogger(__name__)
WEAK_EVIDENCE = re.compile(
    r"\b(maybe|likely|probably|possibly|uncertain|appears|seems)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class CardVersionDecision:
    state: str
    card_id: str | None = None

    @classmethod
    def unique(cls, card_id: str) -> CardVersionDecision:
        return cls("UNIQUE_VERSION", card_id)

    @classmethod
    def ambiguous(cls) -> CardVersionDecision:
        return cls("AMBIGUOUS")

    @classmethod
    def no_evidence(cls) -> CardVersionDecision:
        return cls("NO_EVIDENCE")

    @classmethod
    def provider_failure(cls) -> CardVersionDecision:
        return cls("PROVIDER_FAILURE")


@dataclass(frozen=True)
class CardVersionAnalysisRequest:
    fingerprint: str
    observation: C3POPlayer
    cards: tuple[CFB27CardData, ...]


@dataclass(frozen=True)
class CardVersionBatchResult:
    decisions: Mapping[str, CardVersionDecision]
    request_succeeded: bool
    rate_limited: bool = False


@dataclass(frozen=True)
class CardVersionAnalysisOutcome:
    requested: int
    request_succeeded: bool
    provider_failed: bool = False
    rate_limited: bool = False


class CardVersionAnalyzer(Protocol):
    """Optional downstream analyzer; it can select only a supplied card ID."""

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
        supplied_versions = "\n".join(
            f"  - card_id={card.card_id}; native OVR={card.card_ovr}; "
            f"position={card.native_position}; program={card.program}"
            for card in request.cards
        )
        blocks.append(
            f"""OBSERVATION {request.fingerprint}
The player's identity is already established as {observation.name}.
Do not identify, rename, reject, or substitute this player.
Observed lineup slot: {observation.slot}
EA displayed OVR: {observation.displayed_ovr}
Supplied card versions for {observation.name} only:
{supplied_versions}"""
        )
    observations = "\n\n".join(blocks)
    return f"""Every player's identity is already established by C-3PO.
Do not identify, rename, reject, or substitute any player.

Inspect the supplied original EA Team Manager screenshot pixels only to determine,
independently for each observation below, whether positive visual evidence
distinguishes exactly one supplied card version. Never compare or combine card
versions across observation blocks.

{observations}

Use visible card/program treatment, card design, rarity or program indicators, or
other version-specific presentation only when actually visible. EA displayed OVR
may be reported as evidence but is not sufficient by itself to choose a version.
Do not guess. Weak, likely, probable, or uncertain evidence means AMBIGUOUS.

Return JSON only as {{"results":[...]}} with at most one item per observation.
Each item must contain "observation_fingerprint" and "result". Result may be
"UNIQUE_VERSION", "AMBIGUOUS", or "NO_EVIDENCE". UNIQUE_VERSION also requires
"card_id", "confidence":"HIGH", and a nonempty
"positive_visual_evidence" list of visible facts.
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
    if result == "AMBIGUOUS":
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
    if (
        result == "UNIQUE_VERSION"
        and payload.get("confidence") == "HIGH"
        and isinstance(payload.get("card_id"), str)
        and evidence_is_positive
    ):
        return CardVersionDecision.unique(payload["card_id"])
    return CardVersionDecision.no_evidence()


def _rate_limit_metadata(exc: Exception) -> tuple[bool, str | None]:
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
    return limited, str(retry_after) if retry_after is not None else None


class GeminiCardVersionAnalyzer:
    """One bounded Gemini request that may resolve card version, never identity."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        timeout_ms: int = 60000,
        client_factory: Callable[[], Any] | None = None,
    ):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.model = model or os.getenv(
            "PANCAKE_GEMINI_VERSION_MODEL",
            os.getenv("PANCAKE_GEMINI_MODEL", "gemini-3.7-flash"),
        )
        self.timeout_ms = timeout_ms
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
            http_options=types.HttpOptions(timeout=self.timeout_ms),
        )

    def analyze_batch(
        self,
        requests: tuple[CardVersionAnalysisRequest, ...],
        evidence: C3POSourceEvidence,
    ) -> CardVersionBatchResult:
        bounded_requests = []
        for request in requests:
            identity = _normalized_name(request.observation.name)
            exact_cards = tuple(
                card
                for card in request.cards
                if identity
                and _normalized_name(card.canonical_name) == identity
                and card.card_id
            )
            if len(exact_cards) >= 2:
                bounded_requests.append(
                    CardVersionAnalysisRequest(
                        request.fingerprint, request.observation, exact_cards
                    )
                )
        bounded = tuple(bounded_requests)
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
        try:
            client = self._client()
            with client:
                interaction = client.interactions.create(
                    model=self.model, input=request_input
                )
        except Exception as exc:  # provider SDK/network failures are fail-open
            rate_limited, retry_after = _rate_limit_metadata(exc)
            if rate_limited:
                LOGGER.error(
                    "CFB27 version provider failure: RATE_LIMITED retry_after=%s",
                    retry_after or "unavailable",
                )
            else:
                LOGGER.error("CFB27 version provider failure: %s", type(exc).__name__)
            return CardVersionBatchResult(
                {}, request_succeeded=False, rate_limited=rate_limited
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
        cards: tuple[CFB27CardData, ...],
    ) -> CardVersionDecision:
        """Compatibility helper for focused single-observation diagnostics."""
        fingerprint = "single-observation"
        result = self.analyze_batch(
            (CardVersionAnalysisRequest(fingerprint, observation, cards),), evidence
        )
        if not result.request_succeeded:
            return CardVersionDecision.provider_failure()
        return result.decisions.get(fingerprint, CardVersionDecision.no_evidence())
