"""Generate held-out QB architecture A-D comparison artifacts."""

import json
from pathlib import Path

from operation_pancake.research.qb_model_comparison import (
    build_model_comparison,
    write_model_artifacts,
)


def main() -> None:
    """Build comparison artifacts from the committed population research."""
    research = json.loads(
        Path("data/research/qb_formula_phase_population_boundary.json").read_text(encoding="utf-8")
    )
    comparison = build_model_comparison(research)
    write_model_artifacts("data/research/qb_model_comparison", comparison)


if __name__ == "__main__":
    main()
