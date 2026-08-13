"""Generate Jeff Saturday controlled Center reconstruction artifacts."""

import json
from pathlib import Path
from typing import Any

from operation_pancake.research.saturday_center_analysis import (
    build_saturday_center_analysis,
    write_saturday_center_artifacts,
)


def _read(path: str) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main() -> None:
    """Combine recovered historical identity with repository-confirmed reset deltas."""
    progression = _read("data/research/progression_audit/progression_inventory.json")
    progression["confirmed_transitions"] = _read(
        "data/research/progression_audit/confirmed_transition_deltas.json"
    )
    previous = {
        "reset_linkages": _read(
            "data/research/reset_context_audit/reset_linkage_classifications.json"
        )
    }
    analysis = build_saturday_center_analysis(progression, previous)
    write_saturday_center_artifacts("data/research/saturday_center_analysis", analysis)


if __name__ == "__main__":
    main()
