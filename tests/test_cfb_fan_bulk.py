import hashlib
import json
from collections import Counter
from pathlib import Path

from operation_pancake.acquisition.cfb_fan_bulk import (
    CfbFanBulkAdapter,
    cfb27_position,
    identity_conflicts,
    parse_bulk_payload,
    promote_record,
    rating_conflicts,
    ratings_from_record,
)


def record(**updates):
    value = {
        "externalId": 123,
        "firstName": "Test",
        "lastName": "Player",
        "overall": 80,
        "position": {"abbreviation": "C"},
        "program": {"name": "Core"},
        "archetype": {"nameWithoutPosition": "Agile"},
        "speed": 0,
        "awareness": 75,
    }
    value.update(updates)
    return value


def test_parser_preserves_zero_and_unknown():
    parsed = parse_bulk_payload(json.dumps({"data": [record()]}).encode())
    ratings = ratings_from_record(parsed["27-123"])
    assert ratings["SPD"] == 0
    assert ratings["AWR"] == 75
    assert "ACC" not in ratings


def test_bulk_identity_prefers_cfb27_game_position():
    mike = record(
        position={"abbreviation": "MLB"},
        gamePosition={"abbreviation": "MIKE"},
    )
    assert cfb27_position(mike) == "MIKE"
    existing = {
        "player_name": "Test Player",
        "position": "MIKE",
        "overall": 80,
        "program": "Core",
        "archetype": "Agile",
    }
    assert identity_conflicts(existing, mike) == {}
    promoted = promote_record(
        {
            "external_card_id": "27-123",
            "position": "MIKE",
            "extraction_status": "PARTIAL",
            "metadata": {},
        },
        mike,
        "raw.json",
        "now",
    )
    assert promoted["position"] == "MIKE"


def test_comparison_detects_identity_and_rating_conflicts():
    existing = {
        "player_name": "Test Player",
        "position": "C",
        "overall": 80,
        "program": "Other",
        "archetype": "Agile",
        "displayed_ratings": {"AWR": 74},
    }
    assert set(identity_conflicts(existing, record())) == {"program"}
    assert rating_conflicts(existing, ratings_from_record(record())) == {
        "AWR": {"existing": 74, "structured": 75}
    }


def test_partial_promotes_and_full_is_preserved():
    partial = {
        "external_card_id": "27-123",
        "extraction_status": "PARTIAL_LISTING_VECTOR",
        "metadata": {},
    }
    promoted = promote_record(partial, record(), "raw.json", "now")
    assert promoted["extraction_status"] == "COMPLETE"
    assert promoted["displayed_ratings"]["SPD"] == 0
    full = {"extraction_status": "COMPLETE", "displayed_ratings": {"SPD": 99}}
    assert promote_record(full, record(), "raw.json", "now") is full


def test_checkpoint_resume_uses_raw_snapshot(tmp_path):
    calls = []
    payload = json.dumps({"data": [record()]}).encode()
    adapter = CfbFanBulkAdapter(tmp_path, fetcher=lambda url: calls.append(url) or payload)
    _, first = adapter.acquire(["27-123"], "now")
    adapter.fetcher = lambda url: (_ for _ in ()).throw(AssertionError("network used"))
    _, second = adapter.acquire(["27-123"], "later")
    assert first == second
    assert len(calls) == 1


def test_op_x_013_validated_artifacts_are_consistent():
    root = Path(__file__).resolve().parents[1]
    state = json.loads((root / "data/external/cfb_fan_population_state.json").read_text())
    validation = json.loads(
        (root / "data/research/cfb27_op_x_013/existing_full_validation.json").read_text()
    )
    pilot = json.loads((root / "data/research/cfb27_op_x_013/partial_pilot.json").read_text())
    checkpoint = json.loads(
        (root / "data/external/cfb_fan_full_vector_checkpoint.json").read_text()
    )
    assert len(state["cards"]) == 8838
    assert sum(card["extraction_status"] == "COMPLETE" for card in state["cards"].values()) == 8309
    assert len(validation) == 20
    assert {row["status"] for row in validation} == {"EXACT_EXISTING_FIELDS"}
    assert len(pilot) == 8376
    pilot_status = Counter(row["status"] for row in pilot)
    assert pilot_status["PROMOTED_TO_COMPLETE"] == 7847
    assert pilot_status["PRESERVED_CONFLICT"] == 529
    batch = next(iter(checkpoint["batches"].values()))
    raw = (root / batch["snapshot"]).read_bytes()
    assert len(batch["requested_ids"]) == len(batch["returned_ids"]) == 50
    assert hashlib.sha256(raw).hexdigest() == batch["sha256"]
