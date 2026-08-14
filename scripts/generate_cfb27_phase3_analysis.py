"""Generate deterministic Phase-III falsification and chronology artifacts."""

from __future__ import annotations

import json
from pathlib import Path

from operation_pancake.research.cfb27_phase3 import build_phase3_analysis, write_phase3_artifacts


def main() -> None:
    root = Path(__file__).resolve().parents[1]

    def load(path: str):
        return json.loads((root / path).read_text(encoding="utf-8"))

    state = load("data/external/cfb_fan_population_state.json")
    freeze = load("data/research/cfb27_inheritance_phase3/phase3_frozen_snapshot.json")
    phase2 = load("data/research/cfb27_inheritance_phase2/phase2_summary.json")
    analysis = build_phase3_analysis(list(state["cards"].values()), freeze, phase2)
    write_phase3_artifacts(root / "data/research/cfb27_inheritance_phase3", analysis)
    print(
        f"Phase III analyzed {analysis['population']['total']} cards; "
        "prospective Center n="
        f"{len(analysis['center_prospective_validation']['new_ordinary_centers'])}."
    )


if __name__ == "__main__":
    main()
