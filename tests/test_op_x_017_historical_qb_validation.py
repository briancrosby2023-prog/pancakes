import importlib.util
from pathlib import Path

PATH = Path(__file__).parents[1] / "scripts/op_x_017_historical_qb_validation.py"
SPEC = importlib.util.spec_from_file_location("opx17_qb", PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_frozen_qb_weights_total_100():
    assert sum(MODULE.WEIGHTS.values()) == 100


def test_qb_score_is_unchanged_weighted_vector():
    attributes = {field: 80 for field in MODULE.WEIGHTS}
    result = MODULE.score({"attributes": attributes, "archetype": "Pocket Passer", "ovr": 80})
    assert result["frozen_score"] == 80
    assert result["scoring_eligible"] is True


def test_qb_score_excludes_missing_weighted_fields():
    result = MODULE.score({"attributes": {}, "archetype": "Pocket Passer", "ovr": 80})
    assert result["scoring_eligible"] is False
    assert result["frozen_score"] is None
    assert len(result["missing_weighted_attributes"]) == 12
