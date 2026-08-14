"""Freeze Phase-III inputs before prospective CFB27 acquisition."""

from __future__ import annotations

import hashlib
import json
import statistics
from pathlib import Path

from operation_pancake.research.center_exact_validation import WEIGHTS
from operation_pancake.research.cfb27_phase2 import _fit, _score, is_special

FROZEN_AT = "2026-08-13T00:00:00-07:00"


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    state_path = root / "data/external/cfb_fan_population_state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    cards = sorted(state["cards"].values(), key=lambda row: row["external_card_id"])
    centers = [
        row
        for row in cards
        if row["position"] == "C"
        and not is_special(row)
        and all(attribute in row["displayed_ratings"] for attribute in WEIGHTS)
    ]
    scores = [_score(row, WEIGHTS) for row in centers]
    ovrs = [row["overall"] for row in centers]
    affine = _fit(scores, ovrs)
    fixed = _fit(scores, ovrs, 1.0)
    canonical = root / "data/canonical/canonical_v1.9.xlsx"
    phase2 = root / "data/research/cfb27_inheritance_phase2/phase2_summary.json"
    saturday = root / "data/research/center_exact_validation/saturday_frozen_model_validation.json"
    payload = {
        "schema_version": 1,
        "phase": "Inheritance Falsification Phase III",
        "frozen_at": FROZEN_AT,
        "source_commit": "b6ce2ed",
        "population": {
            "count": len(cards),
            "card_ids": [row["external_card_id"] for row in cards],
            "normalized_sha256": hashlib.sha256(
                json.dumps(cards, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest(),
            "state_file_sha256": _digest(state_path),
        },
        "center_training": {
            "n": len(centers),
            "card_ids": [row["external_card_id"] for row in centers],
            "ovr_distribution": {
                str(level): sum(row["overall"] == level for row in centers)
                for level in sorted(set(ovrs))
            },
            "historical_weights": WEIGHTS,
            "affine_calibration": {"slope": affine[0], "intercept": affine[1]},
            "fixed_slope_calibration": {"slope": fixed[0], "intercept": fixed[1]},
            "score_mean": statistics.mean(scores),
        },
        "frozen_evidence": {
            "canonical_workbook_sha256": _digest(canonical),
            "phase2_summary_sha256": _digest(phase2),
            "saturday_progression_sha256": _digest(saturday),
        },
        "ordinary_definition": "program prefix Core or Platinum",
        "future_eligibility": (
            "A card absent from population.card_ids and acquired after source_commit is eligible; "
            "the frozen calibration must not be refit before scoring."
        ),
        "guessed_values": False,
        "leakage": False,
    }
    target = root / "data/research/cfb27_inheritance_phase3/phase3_frozen_snapshot.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Frozen {len(cards)} cards and {len(centers)} ordinary Centers.")


if __name__ == "__main__":
    main()
