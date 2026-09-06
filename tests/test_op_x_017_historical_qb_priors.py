import importlib.util
from pathlib import Path

PATH = Path(__file__).parents[1] / "scripts/op_x_017_historical_qb_priors.py"
SPEC = importlib.util.spec_from_file_location("opx17_qb_priors", PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_qb_prior_denominators_preserve_source_totals():
    assert {name: sum(weights.values()) for name, weights in MODULE.WEIGHTS.items()} == {
        "Field General": 100,
        "Scrambler": 97,
        "Strong Arm": 100,
        "West Coast": 100,
    }


def test_qb_prior_score_renormalizes_rounding_total():
    attributes = {field: 80 for field in MODULE.WEIGHTS["Scrambler"]}
    result = MODULE.score(
        {"attributes": attributes, "archetype": "Scrambler", "ovr": 80}, "Scrambler"
    )
    assert result["frozen_score"] == 80
    assert result["weight_denominator"] == 97
