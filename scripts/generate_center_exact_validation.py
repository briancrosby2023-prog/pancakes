"""Generate exact recovered Center model and Saturday validation artifacts."""

import json
from pathlib import Path

from operation_pancake.research.center_exact_validation import (
    build_center_exact_validation,
    write_center_exact_artifacts,
)


def _read(path: str) -> object:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main() -> None:
    """Freeze recovered constants before evaluating controlled Center evidence."""
    transitions = _read(
        "data/research/saturday_center_analysis/saturday_center_transition_matrix.json"
    )
    reconciliation = _read(
        "data/research/historical_center_assessment/"
        "historical_center_population_reconciliation.json"
    )
    analysis = build_center_exact_validation(transitions, reconciliation)
    write_center_exact_artifacts("data/research/center_exact_validation", analysis)


if __name__ == "__main__":
    main()
