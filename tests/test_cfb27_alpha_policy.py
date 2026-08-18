from operation_pancake.research.cfb27_alpha_policy import (
    CANONICAL_SOURCE,
    CANONICAL_TAXONOMY,
    NONCANONICAL_LEGACY_LABELS,
    alpha_policy_metadata,
    canonical_position,
    secondary_position_is_blocking,
)


def test_alpha_uses_cfb_fan_and_cfb27_terminology():
    assert CANONICAL_SOURCE == "CFB_FAN"
    assert CANONICAL_TAXONOMY == "CFB27_GAME"
    assert canonical_position({"position": "WILL"}) == "WILL"
    assert canonical_position({"position": "MIKE"}) == "MIKE"
    assert canonical_position({"position": "LEDG"}) == "LEDG"
    assert canonical_position({"position": "REDG"}) == "REDG"


def test_legacy_secondary_position_does_not_block_alpha_record():
    card = {"position": "WILL", "external_source": "CFB_FAN"}
    assert "ROLB" in NONCANONICAL_LEGACY_LABELS
    assert secondary_position_is_blocking(card, "ROLB") is False
    assert canonical_position(card) == "WILL"


def test_policy_is_machine_readable_and_explicitly_scoped():
    policy = alpha_policy_metadata()
    assert policy["canonical_source"] == "CFB_FAN"
    assert policy["canonical_taxonomy"] == "CFB27_GAME"
    assert policy["secondary_position_rule"] == "PROVENANCE_ONLY_NON_BLOCKING"
    assert policy["claim_scope"] == "ALPHA_ENGINEERING_CONVENTION_NOT_SOURCE_INFALLIBILITY"
