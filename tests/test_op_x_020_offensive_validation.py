import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from op_x_018_historical_wr_validation import score  # noqa: E402

RB = json.loads((ROOT / "data/research/op_x_020/rb/frozen_rb_scoring_spec.json").read_text())
FB = json.loads((ROOT / "data/research/op_x_020/fb/frozen_fb_scoring_spec.json").read_text())


def test_rb_vectors_total_100():
    assert all(sum(weights.values()) == 100 for weights in RB["weights"].values())


def test_rb_mapping_and_no_calibration():
    attrs = {name: 84 for name in RB["weights"]["Elusive Back"]}
    result = score(
        {"season": 26, "position": "HB", "archetype": "East/West Playmaker", "attributes": attrs},
        RB,
    )
    assert result["frozen_score"] == 84
    assert result["mapping_status"] == "SUPPORTED"


def test_fb_denominators_and_exact_mapping():
    assert {name: sum(weights.values()) for name, weights in FB["weights"].items()} == {
        "Utility": 100,
        "Blocking": 102,
    }
    attrs = {name: 76 for name in FB["weights"]["Blocking"]}
    result = score(
        {"season": 26, "position": "FB", "archetype": "Blocking", "attributes": attrs},
        FB,
    )
    assert result["frozen_score"] == 76
    assert result["mapping_status"] == "EXACT"
