"""Generate the E.15 same-OVR / adjacent-boundary evidence matrix."""

from __future__ import annotations

import json
from pathlib import Path

from operation_pancake.research.cfb27_alpha_population import build_alpha_population
from operation_pancake.research.cfb27_e15_multi_family import build_multi_family_matrix


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    alpha = build_alpha_population(root)
    cards = list(alpha["cards"].values())
    matrix = build_multi_family_matrix(cards)
    matrix["alpha_population"] = alpha["summary"]

    output = root / "data/research/cfb27_e15/multi_family_evidence_matrix.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(matrix, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(f"Wrote {output.relative_to(root)}")
    for family, payload in matrix["families"].items():
        print(f"[{family}]")
        for row in payload["positions"]:
            drivers = ",".join(item["rating"] for item in row["candidate_drivers"][:8]) or "-"
            non_drivers = ",".join(item["rating"] for item in row["likely_non_drivers"][:8]) or "-"
            print(
                f"{row['position']}: n={row['cards']} archetypes={len(row['archetypes'])} "
                f"drivers={drivers} non_drivers={non_drivers}"
            )


if __name__ == "__main__":
    main()
