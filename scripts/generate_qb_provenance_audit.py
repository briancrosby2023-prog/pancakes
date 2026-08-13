"""Generate QB progression, provenance, and evidence-gap research artifacts."""

import json
from pathlib import Path

from operation_pancake.research.qb_model_comparison import build_model_comparison
from operation_pancake.research.qb_provenance_audit import (
    build_provenance_audit,
    write_provenance_artifacts,
)


def main() -> None:
    """Build the audit from canonical research and workbook evidence."""
    research = json.loads(
        Path("data/research/qb_formula_phase_population_boundary.json").read_text(encoding="utf-8")
    )
    audit = build_provenance_audit(
        research,
        build_model_comparison(research),
        "data/canonical/canonical_v1.9.xlsx",
        [str(path) for path in Path(".").rglob("*") if path.is_file()],
    )
    write_provenance_artifacts("data/research/qb_provenance_audit", audit)


if __name__ == "__main__":
    main()
