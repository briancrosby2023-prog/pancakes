import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from op_x_018_historical_wr_validation import score  # noqa: E402

SAFETY = json.loads(
    (ROOT / "data/research/op_x_019/safety/frozen_safety_scoring_spec.json").read_text()
)
EDGE = json.loads((ROOT / "data/research/op_x_019/edge/frozen_edge_scoring_spec.json").read_text())
MIKE = json.loads((ROOT / "data/research/op_x_019/mike/frozen_mike_scoring_spec.json").read_text())
DT = json.loads((ROOT / "data/research/op_x_019/dt/frozen_dt_scoring_spec.json").read_text())


def test_safety_source_denominators_are_preserved():
    assert {name: sum(weights.values()) for name, weights in SAFETY["weights"].items()} == {
        "Hybrid": 100,
        "Run Support": 97,
        "Zone Coverage": 104,
    }


def test_safety_score_uses_actual_denominator_without_calibration():
    attrs = {name: 82 for name in SAFETY["weights"]["Run Support"]}
    result = score(
        {"season": 26, "position": "S", "archetype": "Box Specialist", "attributes": attrs},
        SAFETY,
    )
    assert result["frozen_score"] == 82
    assert result["weight_denominator"] == 97
    assert result["mapping_status"] == "SUPPORTED"


def test_edge_vectors_total_100_and_position_mapping_is_explicit():
    assert all(sum(weights.values()) == 100 for weights in EDGE["weights"].values())
    attrs = {name: 75 for name in EDGE["weights"]["Run Stopper"]}
    result = score(
        {"season": 26, "position": "EDGE", "archetype": "Gap Specialist", "attributes": attrs},
        EDGE,
    )
    assert result["frozen_score"] == 75
    assert result["model_archetype"] == "Run Stopper"


def test_mike_vectors_and_signal_caller_mapping_are_frozen():
    assert all(sum(weights.values()) == 100 for weights in MIKE["weights"].values())
    attrs = {name: 79 for name in MIKE["weights"]["Field General"]}
    result = score(
        {"season": 26, "position": "MIKE", "archetype": "Signal Caller", "attributes": attrs},
        MIKE,
    )
    assert result["frozen_score"] == 79
    assert result["model_archetype"] == "Field General"


def test_dt_vectors_and_pure_power_mapping_are_frozen():
    assert all(sum(weights.values()) == 100 for weights in DT["weights"].values())
    attrs = {name: 77 for name in DT["weights"]["Power Rusher"]}
    result = score(
        {"season": 26, "position": "DT", "archetype": "Pure Power", "attributes": attrs},
        DT,
    )
    assert result["frozen_score"] == 77
    assert result["model_archetype"] == "Power Rusher"
