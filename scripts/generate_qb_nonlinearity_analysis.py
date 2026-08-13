"""Generate EA-plausible QB nonlinearity research artifacts."""

import json
from pathlib import Path

from operation_pancake.research.qb_nonlinearity_analysis import (
    build_nonlinearity_analysis,
    write_nonlinearity_artifacts,
)


def main() -> None:
    research = json.loads(
        Path("data/research/qb_formula_phase_population_boundary.json").read_text(encoding="utf-8")
    )
    analysis = build_nonlinearity_analysis(research)
    write_nonlinearity_artifacts("data/research/qb_nonlinearity_analysis", analysis)


if __name__ == "__main__":
    main()
