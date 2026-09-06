#!/usr/bin/env python3
"""Generate CFB27 Alpha population/formula-readiness diagnostics."""

from __future__ import annotations

import json
from pathlib import Path

from operation_pancake.research.cfb27_alpha_readiness import build_alpha_readiness

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data/research/cfb27_alpha/readiness.json"


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    payload = build_alpha_readiness(ROOT)
    OUTPUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = payload["alpha_population"]
    experiments = payload["natural_experiment_inventory"]
    print(
        f"Alpha: {summary['alpha_complete']}/{summary['total']} complete; "
        f"formula eligible={payload['formula_eligibility']['eligible']}; "
        f"same-OVR/archetype cells={experiments['same_ovr_archetype_cells']}; "
        f"pairwise experiments={experiments['pairwise_comparisons']}"
    )


if __name__ == "__main__":
    main()
