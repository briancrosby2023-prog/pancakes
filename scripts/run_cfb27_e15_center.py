"""Generate the deterministic OP-X-012E.15 Center calibration artifact."""

from __future__ import annotations

import json
from pathlib import Path

from operation_pancake.research.cfb27_e15_center import build_center_calibration_assessment


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    output = root / "data/research/cfb27_e15/center_calibration_assessment.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    assessment = build_center_calibration_assessment(root)
    output.write_text(json.dumps(assessment, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Wrote {output.relative_to(root)}")
    print(f"Center cards: {assessment['center_cards']}")
    for row in assessment["assessments"]:
        print(
            f"{row['archetype']}: n={row['scored_cards']} "
            f"exact={row['exact_match_rate']} mae={row['mean_absolute_error']} "
            f"confidence={row['confidence']}"
        )


if __name__ == "__main__":
    main()
