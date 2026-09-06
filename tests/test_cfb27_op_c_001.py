import json
from pathlib import Path

from operation_pancake.research.cfb27_op_c_001 import build_op_c_001

ROOT = Path(__file__).resolve().parents[1]
RESEARCH = ROOT / "data/research/cfb27_op_c_001"


def load(name: str) -> dict:
    return json.loads((RESEARCH / f"{name}.json").read_text(encoding="utf-8"))


def test_mass_acquisition_population_integrity_is_preserved() -> None:
    summary = load("acquisition_summary")
    state = json.loads(
        (ROOT / "data/external/cfb_fan_population_state.json").read_text(encoding="utf-8")
    )
    assert summary["population"] == 8838
    assert summary["full_vectors"] == 8309
    assert summary["partial_vectors"] == 529
    assert summary["duplicate_source_ids_in_population"] == 0
    assert summary["ids_missing_from_responses"] == []
    assert summary["ids_unexpected_in_responses"] == []
    assert summary["failed_batches"] == 0
    assert summary["bulk_conflicts"] == 529
    assert summary["conflict_fields"] == {"position": 529}
    assert len(state["cards"]) >= summary["population"]
    assert all(value is False for value in summary["validation"].values())


def test_generation_is_deterministic_and_freeze_is_versioned() -> None:
    first = build_op_c_001(ROOT)
    assert first == build_op_c_001(ROOT)
    assert first["freeze"]["packet"] == "OP-C-001"
    assert first["freeze"]["start_commit"] == "e14c902"
    assert len(first["freeze"]["population_sha256"]) == 64
