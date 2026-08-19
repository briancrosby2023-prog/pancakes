"""Offline refresh of the Phase-I inheritance artifacts from frozen repository state."""

import json
from pathlib import Path

from operation_pancake.research.cfb27_inheritance import (
    build_inheritance_analysis,
    write_inheritance_artifacts,
)


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    state = json.loads(
        (root / "data/external/cfb_fan_population_state.json").read_text(encoding="utf-8")
    )
    summary_path = root / "data/research/cfb27_inheritance_phase1/analysis_summary.json"
    previous = json.loads(summary_path.read_text(encoding="utf-8"))
    cards = [
        card
        for card in state["cards"].values()
        if card["retrieval_timestamp"] in {"2026-08-13T20:00:00Z", "2026-08-13T22:00:00Z"}
    ]
    analysis = build_inheritance_analysis(cards, previous["historical_leads"])
    if "acquisition" in previous:
        analysis["acquisition"] = previous["acquisition"]
    write_inheritance_artifacts(root / "data/research/cfb27_inheritance_phase1", analysis)
    print(f"Refreshed Phase-I inheritance artifacts from {len(cards)} frozen cards.")


if __name__ == "__main__":
    main()
