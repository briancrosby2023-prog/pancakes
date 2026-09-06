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

# Parser v1 deterministically rewrote three CFB.FAN/CFB27 labels before storing
# them.  This reverse map is therefore a repair of Pancake's own historical
# normalization, not a translation of a current secondary source.
LEGACY_PARSER_V1_REVERSE = {"MLB": "MIKE", "LE": "LEDG", "RE": "REDG"}


def canonical_position(card: dict) -> str | None:
    """Return the CFB.FAN/CFB27-native Alpha position.

    Current records already preserve the source label.  Historical records
    produced by ``cfb-fan-html-v1`` are reversibly repaired from Pancake's own
    deterministic MIKE->MLB, LEDG->LE and REDG->RE normalization.
    """
    value = card.get("position")
    if not isinstance(value, str) or not value:
        return None
    return LEGACY_PARSER_V1_REVERSE.get(value, value)


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
        "position_rule": "PRESERVE_OR_RESTORE_CFB_FAN_CFB27_LABEL",
        "secondary_position_rule": "PROVENANCE_ONLY_NON_BLOCKING",
        "legacy_parser_v1_reverse": dict(sorted(LEGACY_PARSER_V1_REVERSE.items())),
        "legacy_labels_noncanonical": sorted(NONCANONICAL_LEGACY_LABELS),
        "defensive_position_examples": sorted(CFB27_DEFENSIVE_POSITIONS),
        "claim_scope": "ALPHA_ENGINEERING_CONVENTION_NOT_SOURCE_INFALLIBILITY",
    }
