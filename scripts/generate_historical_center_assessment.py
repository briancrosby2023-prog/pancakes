"""Generate recovered historical Center research assessment artifacts."""

import json
from pathlib import Path

from operation_pancake.research.historical_center_assessment import (
    build_historical_center_assessment,
    write_historical_center_artifacts,
)


def _read(path: str) -> object:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main() -> None:
    """Integrate supplied history with canonical and controlled Center evidence."""
    progression = _read("data/research/progression_audit/progression_inventory.json")
    saturday = _read(
        "data/research/saturday_center_analysis/saturday_center_transition_matrix.json"
    )
    analysis = build_historical_center_assessment(progression, saturday)
    write_historical_center_artifacts("data/research/historical_center_assessment", analysis)


if __name__ == "__main__":
    main()
