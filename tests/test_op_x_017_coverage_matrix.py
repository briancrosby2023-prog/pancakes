import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]


def test_coverage_matrix_has_required_controls():
    subprocess.run(
        [sys.executable, "scripts/op_x_017_build_coverage_matrix.py"],
        cwd=ROOT,
        check=True,
    )
    matrix = json.loads((ROOT / "data/research/op_x_017/coverage_matrix.json").read_text())
    required = {
        "model",
        "version",
        "archetype",
        "production_status",
        "cfb25_n",
        "cfb25_accuracy",
        "cfb26_n",
        "cfb26_accuracy",
        "cross_season_verdict",
        "at_or_above_95_percent",
        "locked",
        "remaining_blocker",
        "next_scientific_action",
    }
    assert matrix["models"]
    assert all(required <= set(row) for row in matrix["models"])
    assert "QB-SHARED-001 v1.0" in matrix["summary"]["durable_production_locks"]
    assert matrix["summary"]["currently_executable_frozen_models_exhausted"] is True


def test_inventory_covers_requested_position_families():
    inventory = json.loads((ROOT / "data/research/op_x_017/model_inventory.json").read_text())
    positions = {row["position_family"] for row in inventory}
    assert {
        "QB",
        "HB/RB",
        "FB",
        "WR",
        "TE",
        "C",
        "EDGE/DE",
        "DT",
        "CB",
        "FS",
        "SS",
        "K/P",
    } <= positions
