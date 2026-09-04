"""Narrow result contract for optional CFB27 card-version analysis."""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from operation_pancake.c3po_roster import C3POPlayer
    from operation_pancake.c3po_source_evidence import C3POSourceEvidence
    from operation_pancake.cfb27_enrichment import CFB27CardData


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
