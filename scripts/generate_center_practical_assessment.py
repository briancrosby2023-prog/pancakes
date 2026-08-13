"""Generate Center practical-model readiness artifacts."""

import json
from pathlib import Path

from operation_pancake.research.center_practical_assessment import (
    build_center_practical_assessment,
    write_center_practical_artifacts,
)


def _read(path: str) -> object:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main() -> None:
    """Assess Center evaluation readiness with evidence types separated."""
    analysis = build_center_practical_assessment(
        _read("data/research/progression_audit/progression_inventory.json"),
        _read(
            "data/research/historical_center_assessment/"
            "historical_center_population_reconciliation.json"
        ),
        _read("data/research/center_exact_validation/saturday_frozen_model_validation.json"),
    )
    write_center_practical_artifacts("data/research/center_practical_assessment", analysis)


if __name__ == "__main__":
    main()
