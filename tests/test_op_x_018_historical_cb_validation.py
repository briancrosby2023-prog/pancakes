import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from op_x_018_historical_wr_validation import score  # noqa: E402

SPEC = json.loads((ROOT / "data/research/op_x_018/cb/frozen_cb_scoring_spec.json").read_text())


def test_cb_source_vectors_total_100():
    assert {name: sum(weights.values()) for name, weights in SPEC["weights"].items()} == {
        "Man to Man": 100,
        "Slot": 100,
        "Zone": 100,
    }


def test_exact_name_cfb25_zone_scores_without_refit():
    attributes = {name: 73 for name in SPEC["weights"]["Zone"]}
    result = score(
        {"season": 25, "position": "CB", "archetype": "Zone", "attributes": attributes},
        SPEC,
    )
    assert result["frozen_score"] == 73
    assert result["mapping_status"] == "PROVEN"
