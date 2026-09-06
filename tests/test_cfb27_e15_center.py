import pytest

from operation_pancake.research.center_exact_validation import FrozenHistoricalCenterModel
from operation_pancake.research.cfb27_e15_center import frozen_historical_center_candidate


def test_e15_candidate_reproduces_frozen_center_continuous_score():
    ratings = {
        "RBP": 80,
        "PBP": 82,
        "AWR": 79,
        "STR": 85,
        "RBK": 81,
        "PBF": 80,
        "IBL": 78,
        "LBK": 77,
        "SPD": 65,
        "ACC": 66,
        "AGI": 64,
        "PBK": 81,
    }
    historical = FrozenHistoricalCenterModel()
    e15 = frozen_historical_center_candidate()
    assert e15.continuous_score(ratings) == pytest.approx(historical.calibrated_score(ratings))
    assert e15.predict(ratings) == historical.predict(ratings)


def test_e15_center_candidate_remains_frozen_historical_prior():
    candidate = frozen_historical_center_candidate()
    assert candidate.name == "FROZEN_HISTORICAL_CENTER"
    assert candidate.rounding == "HALF_UP"
    assert dict(candidate.weights)["RBP"] == 22.0
    assert dict(candidate.weights)["PBP"] == 21.0
