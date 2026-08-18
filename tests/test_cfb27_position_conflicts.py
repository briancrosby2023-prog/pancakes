import json
from pathlib import Path

from operation_pancake.research.cfb27_position_conflicts import (
    audit_position_conflicts,
    classify_conflict,
)

ROOT = Path(__file__).resolve().parents[1]


def conflict(existing="WILL", structured="ROLB", **updates):
    value = {
        "identity_conflicts": {
            "position": {"existing": existing, "structured": structured}
        },
        "rating_conflicts": {},
        "resolution": "PRESERVE_EXISTING_RECORD",
    }
    value.update(updates)
    return value


def test_position_only_mismatch_is_non_blocking_under_alpha_policy():
    row = conflict()
    assert classify_conflict(row) == "SECONDARY_POSITION_NON_BLOCKING"
    audit = audit_position_conflicts({"conflicts": {"OP-X-013:27-1": row}})
    assert audit["position_pairs"] == [
        {"canonical": "WILL", "secondary": "ROLB", "count": 1}
    ]
    assert audit["all_conflicts_position_only"] is True
    assert audit["alpha_decision"] == "CFB_FAN_CFB27_POSITION_CANONICAL"
    assert audit["alpha_policy"]["canonical_taxonomy"] == "CFB27_GAME"


def test_other_identity_or_rating_disagreement_remains_blocking():
    identity = conflict(
        identity_conflicts={
            "position": {"existing": "SAM", "structured": "LOLB"},
            "overall": {"existing": 85, "structured": 84},
        }
    )
    rating = conflict(rating_conflicts={"SPD": {"existing": 84, "structured": 85}})
    assert classify_conflict(identity) == "POSITION_PLUS_OTHER_CONFLICT"
    assert classify_conflict(rating) == "POSITION_PLUS_OTHER_CONFLICT"


def test_audit_preserves_pair_direction_and_counts_other_conflicts():
    state = {
        "conflicts": {
            "OP-X-013:1": conflict("WILL", "ROLB"),
            "OP-X-013:2": conflict("WILL", "ROLB"),
            "OP-X-013:3": conflict("SAM", "LOLB"),
            "OP-X-013:4": {
                "identity_conflicts": {
                    "program": {"existing": "A", "structured": "B"}
                },
                "rating_conflicts": {},
            },
            "V3:ignored": conflict("WILL", "ROLB"),
        }
    }
    audit = audit_position_conflicts(state)
    assert audit["total_op_x_013_conflicts"] == 4
    assert audit["position_conflict_cards"] == 3
    assert audit["position_pairs"] == [
        {"canonical": "WILL", "secondary": "ROLB", "count": 2},
        {"canonical": "SAM", "secondary": "LOLB", "count": 1},
    ]
    assert audit["other_identity_conflict_fields"] == {"program": 1}
    assert audit["classification_counts"] == {
        "NON_POSITION_CONFLICT": 1,
        "SECONDARY_POSITION_NON_BLOCKING": 3,
    }
    assert audit["all_conflicts_position_only"] is False


def test_current_529_conflicts_are_non_blocking_position_only_for_alpha():
    state = json.loads((ROOT / "data/external/cfb_fan_population_state.json").read_text())
    audit = audit_position_conflicts(state)
    assert audit["total_op_x_013_conflicts"] == 529
    assert audit["position_conflict_cards"] == 529
    assert audit["secondary_position_non_blocking"] == 529
    assert audit["rating_conflict_cards"] == 0
    assert audit["other_identity_conflict_fields"] == {}
    assert audit["all_conflicts_position_only"] is True
    assert sum(row["count"] for row in audit["position_pairs"]) == 529
