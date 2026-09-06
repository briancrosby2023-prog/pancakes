import json
from pathlib import Path

from operation_pancake.research.cfb27_e15_center import build_center_calibration_assessment


def test_center_assessment_contract_uses_canonical_alpha_population():
    root = Path(__file__).resolve().parents[1]
    result = build_center_calibration_assessment(root)
    assert result["phase"] == "OP-X-012E.15"
    assert result["experiment"] == "CENTER_FROZEN_HISTORICAL_PRIOR"
    assert result["refit_before_evaluation"] is False
    population = json.loads(
        (root / "data/external/cfb_fan_population_state.json").read_text()
    )
    assert result["alpha_population"]["alpha_complete"] == len(population["cards"])
    assert result["center_cards"] >= 315
    assert result["assessments"]
    assert sum(row["population_cards"] for row in result["assessments"]) == result["center_cards"]
    for row in result["assessments"]:
        assert row["position"] == "C"
        assert row["confidence"] in {
            "EXACT",
            "HIGH_CONFIDENCE",
            "PROVISIONAL",
            "UNDERDETERMINED",
            "REJECTED",
        }
        assert {item["rounding"] for item in row["rounding_comparison"]} == {
            "HALF_UP",
            "FLOOR",
            "CEIL",
        }
