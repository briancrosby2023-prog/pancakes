"""Generate controlled Joey Harrington progression research artifacts."""

import json
from pathlib import Path

from operation_pancake.research.qb_harrington_analysis import (
    build_harrington_analysis,
    write_harrington_artifacts,
)


def _read(path: str) -> dict[str, object]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main() -> None:
    """Analyze the confirmed chain with previously established model parameters."""
    research = _read("data/research/qb_formula_phase_population_boundary.json")
    comparison = _read("data/research/qb_model_comparison/qb_model_comparison.json")
    constraints = json.loads(
        Path(
            "data/research/qb_provenance_audit/qb_confirmed_progression_constraints.json"
        ).read_text(encoding="utf-8")
    )
    analysis = build_harrington_analysis(
        research,
        comparison,
        {"confirmed_constraints": constraints},
        "data/canonical/canonical_v1.9.xlsx",
    )
    write_harrington_artifacts("data/research/qb_harrington_analysis", analysis)


if __name__ == "__main__":
    main()
