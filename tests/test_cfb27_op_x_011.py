import json
from pathlib import Path

import pytest

from operation_pancake.research.cfb27_op_x_011 import (
    build_op_x_011,
    validate_progression_observation,
)

ROOT = Path(__file__).resolve().parents[1]
RESEARCH = ROOT / "data/research/cfb27_op_x_011"


def load(name):
    return json.loads((RESEARCH / f"{name}.json").read_text())


def test_all_31_distinct_events_are_recovered_with_provenance():
    events = load("progression_events_v2")
    assert len(events) == 31
    assert len({row["event_id"] for row in events}) == 31
    assert all(row["source"] and row["source_locator"] for row in events)


def test_chains_are_ordered_and_continuous():
    chains = load("progression_chains_v2")
    assert len(chains) == 14
    assert all(row["classification"] == "COMPLETE" for row in chains)
    assert all(row["observed_ovrs"] == sorted(row["observed_ovrs"]) for row in chains)


def test_exact_seau_deltas_are_recovered_from_repository():
    events = {row["source_event_id"]: row for row in load("progression_events_v2")}
    assert events["4"]["attribute_deltas"] == {"AGI": 2, "COD": 2, "CTH": 8, "PRC": 2, "PUR": 2}
    assert events["PREMADE_84_86"]["number_attributes_changed"] == 22


def test_unknown_primary_classification_is_preserved():
    reset = next(row for row in load("progression_events_v2") if row["system"] == "SATURDAY_RESET")
    assert reset["primary_attribute_points"] is None
    assert reset["secondary_attribute_points"] is None


def test_historical_claims_without_vectors_are_not_promoted():
    audit = load("progression_data_loss_audit")
    assert audit["manifest_claims"] == 13
    assert audit["newly_promoted_events"] == 2
    assert all(not row["usable_transition"] for row in audit["records"])


def test_reconstructability_never_uses_displayed_ovr():
    result = load("reconstructability_v1")
    assert result["rule"]["displayed_ovr_sufficient"] is False
    assert set(result["current_ol"].values()) == {"NOT_RECONSTRUCTABLE"}


def test_future_ingestion_rejects_duplicate_and_missing_fields():
    payload = {
        "player": "Test",
        "card": "card-1",
        "before_state": "a",
        "after_state": "b",
        "deltas": {"SPD": 1},
        "system": "EVO",
        "source": "test",
    }
    event = validate_progression_observation(payload, [])
    with pytest.raises(ValueError, match="Duplicate"):
        validate_progression_observation(payload, [event])
    with pytest.raises(ValueError, match="Missing"):
        validate_progression_observation({}, [])


def test_generation_is_deterministic_and_integrity_strict():
    first = build_op_x_011(ROOT)
    assert first == build_op_x_011(ROOT)
    assert first["freeze"]["source_commit"] == "1485910"
    assert all(value is False for value in first["validation"].values())
