"""Generate Saturday Reset and TE progression context artifacts."""

import json
from pathlib import Path

from operation_pancake.research.reset_context_audit import (
    build_reset_context_audit,
    write_reset_context_artifacts,
)


def main() -> None:
    """Audit all repository-accessible reset and TE linkage evidence."""
    progression = json.loads(
        Path("data/research/progression_audit/progression_inventory.json").read_text(
            encoding="utf-8"
        )
    )
    transitions = json.loads(
        Path("data/research/progression_audit/confirmed_transition_deltas.json").read_text(
            encoding="utf-8"
        )
    )
    progression["confirmed_transitions"] = transitions
    files = [str(path) for path in Path(".").rglob("*") if path.is_file()]
    audit = build_reset_context_audit(progression, "data/canonical/canonical_v1.9.xlsx", files)
    write_reset_context_artifacts("data/research/reset_context_audit", audit)


if __name__ == "__main__":
    main()
