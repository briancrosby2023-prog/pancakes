"""Narrow result contract for optional CFB27 card-version analysis."""
from __future__ import annotations

import base64
import json
import logging
import os
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable, Protocol

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


class CardVersionAnalyzer(Protocol):
    """Optional downstream analyzer; it can select only a supplied card ID."""

    def analyze(
        self,
        observation: C3POPlayer,
        evidence: C3POSourceEvidence,
        cards: tuple[CFB27CardData, ...],
    ) -> CardVersionDecision: ...


def _normalized_name(value: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", "", (value or "").casefold())


def _prompt(observation: C3POPlayer, cards: tuple[CFB27CardData, ...]) -> str:
    supplied_versions = "\n".join(
        f"- card_id={card.card_id}; native OVR={card.card_ovr}; "
        f"position={card.native_position}; program={card.program}"
        for card in cards
    )
    return f"""The player's identity is already established as {observation.name}.

Do not identify, rename, reject, or substitute the player.

Inspect the supplied original EA Team Manager screenshot pixels only to determine
whether they contain positive visual evidence distinguishing among the supplied
versions of {observation.name}.

Observed lineup slot: {observation.slot}
EA displayed OVR: {observation.displayed_ovr}

Supplied card versions (this exact player only):
{supplied_versions}

Use visible card/program treatment, card design, rarity or program indicators, or
other version-specific presentation only when actually visible. EA displayed OVR
may be reported as evidence but is not sufficient by itself to choose a version.
Do not guess. Weak, likely, probable, or uncertain evidence means AMBIGUOUS.

Return JSON only:
{{"result":"UNIQUE_VERSION","card_id":"one supplied card_id",
"confidence":"HIGH","positive_visual_evidence":["visible fact"]}}
or {{"result":"AMBIGUOUS"}} or {{"result":"NO_EVIDENCE"}}.
"""


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

    def analyze(
        self,
        observation: C3POPlayer,
        evidence: C3POSourceEvidence,
        cards: tuple[CFB27CardData, ...],
    ) -> CardVersionDecision:
        identity = _normalized_name(observation.name)
        exact_cards = tuple(
            card
            for card in cards
            if identity
            and _normalized_name(card.canonical_name) == identity
            and card.card_id
        )
        if len(exact_cards) < 2 or len(evidence.images) != 4:
            return CardVersionDecision.no_evidence()
        request_input: list[dict[str, str]] = [
            {"type": "text", "text": _prompt(observation, exact_cards)}
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
            LOGGER.error("CFB27 version provider failure: %s", type(exc).__name__)
            return CardVersionDecision.provider_failure()

        text = getattr(interaction, "output_text", None)
        if not isinstance(text, str) or not text.strip():
            return CardVersionDecision.no_evidence()
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
            cleaned = re.sub(r"\s*```$", "", cleaned)
        try:
            payload = json.loads(cleaned)
        except (json.JSONDecodeError, TypeError):
            return CardVersionDecision.no_evidence()
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
