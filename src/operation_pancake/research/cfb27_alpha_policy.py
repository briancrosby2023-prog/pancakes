"""Operation Pancake Alpha source and terminology policy for CFB27 CUT.

Alpha intentionally uses the terminology displayed by CFB27 and CFB.FAN.
Secondary schemas are provenance only; they never overwrite a CFB27-native
position or make an otherwise usable CFB.FAN vector ineligible.
"""

from __future__ import annotations

CANONICAL_SOURCE = "CFB_FAN"
CANONICAL_TAXONOMY = "CFB27_GAME"
CFB27_DEFENSIVE_POSITIONS = frozenset(
    {"SAM", "MIKE", "WILL", "LEDG", "REDG", "DT", "CB", "FS", "SS"}
)
NONCANONICAL_LEGACY_LABELS = frozenset({"LOLB", "MLB", "ROLB", "LE", "RE"})


def canonical_position(card: dict) -> str | None:
    """Return the CFB.FAN/CFB27 position already stored on the card.

    No Madden/NFL-style translation is performed.  This function is
    deliberately boring: Alpha's canonical position is the observed CFB.FAN
    listing/game label.
    """
    value = card.get("position")
    return value if isinstance(value, str) and value else None


def secondary_position_is_blocking(card: dict, structured_position: str | None) -> bool:
    """Return whether a secondary position label blocks Alpha use.

    Position nomenclature alone never blocks a record. Identity/rating
    disagreements remain separate validation concerns.
    """
    return False


def alpha_policy_metadata() -> dict:
    return {
        "canonical_source": CANONICAL_SOURCE,
        "canonical_taxonomy": CANONICAL_TAXONOMY,
        "position_rule": "PRESERVE_CFB_FAN_CFB27_LABEL",
        "secondary_position_rule": "PROVENANCE_ONLY_NON_BLOCKING",
        "legacy_labels_noncanonical": sorted(NONCANONICAL_LEGACY_LABELS),
        "defensive_position_examples": sorted(CFB27_DEFENSIVE_POSITIONS),
        "claim_scope": "ALPHA_ENGINEERING_CONVENTION_NOT_SOURCE_INFALLIBILITY",
    }
