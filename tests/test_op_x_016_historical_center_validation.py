import importlib.util
from pathlib import Path

from operation_pancake.research.center_exact_validation import FrozenHistoricalCenterModel

PATH = Path(__file__).parents[1] / "scripts/op_x_016_historical_center_validation.py"
SPEC = importlib.util.spec_from_file_location("opx16_center", PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_center_score_uses_frozen_weights_without_refit():
    model = FrozenHistoricalCenterModel()
    attributes = {field: 80 for field, _ in model.weights}
    row = MODULE.score({"attributes": attributes, "archetype": "Agile", "ovr": 80}, model)
    assert row["frozen_score"] == 80
    assert row["scoring_eligible"] is True
    assert row["missing_weighted_attributes"] == []


def test_center_score_excludes_incomplete_profiles():
    row = MODULE.score(
        {"attributes": {}, "archetype": "Power", "ovr": 80}, FrozenHistoricalCenterModel()
    )
    assert row["frozen_score"] is None
    assert row["scoring_eligible"] is False
    assert len(row["missing_weighted_attributes"]) == 12
