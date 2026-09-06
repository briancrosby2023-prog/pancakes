import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/op_x_018_historical_wr_validation.py"
SPEC = json.loads((ROOT / "data/research/op_x_018/frozen_wr_scoring_spec.json").read_text())
sys.path.insert(0, str(ROOT / "scripts"))
module_spec = importlib.util.spec_from_file_location("op_x_018_wr", SCRIPT)
MODULE = importlib.util.module_from_spec(module_spec)
assert module_spec.loader
module_spec.loader.exec_module(MODULE)


def test_source_weight_totals_are_preserved_exactly():
    assert {name: sum(weights.values()) for name, weights in SPEC["weights"].items()} == {
        "Deep Threat": 99,
        "Possession": 100,
        "Red Zone": 101,
        "Slot": 100,
    }


def test_score_normalizes_actual_denominator_without_calibration():
    row = {
        "season": 25,
        "position": "WR",
        "archetype": "Deep Threat",
        "ovr": 91,
        "attributes": {attribute: 80 for attribute in SPEC["weights"]["Deep Threat"]},
    }
    result = MODULE.score(row, SPEC)
    assert result["frozen_score"] == 80
    assert result["weight_denominator"] == 99
    assert result["scoring_eligible"] is True


def test_unsupported_special_archetype_is_excluded_explicitly():
    result = MODULE.score(
        {"season": 26, "position": "WR", "archetype": "Legacy Receiver", "attributes": {}},
        SPEC,
    )
    assert result["scoring_eligible"] is False
    assert result["exclusion_reason"] == "unsupported_archetype"
    assert result["mapping_status"] == "UNSUPPORTED"
