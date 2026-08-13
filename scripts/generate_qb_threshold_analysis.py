"""Generate discrete threshold and QB boundary research artifacts."""

import json
from pathlib import Path

from operation_pancake.research.qb_model_comparison import build_model_comparison
from operation_pancake.research.qb_threshold_analysis import (
    build_threshold_analysis,
    write_threshold_artifacts,
)


def main() -> None:
    """Regenerate baseline predictions and evaluate fit-only score bands."""
    research = json.loads(
        Path("data/research/qb_formula_phase_population_boundary.json").read_text(encoding="utf-8")
    )
    baseline = build_model_comparison(research)
    analysis = build_threshold_analysis(research, baseline)
    write_threshold_artifacts("data/research/qb_threshold_analysis", analysis)


if __name__ == "__main__":
    main()
