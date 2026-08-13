"""Generate deterministic Phase-II inherited-model research artifacts."""

from __future__ import annotations

import json
from pathlib import Path

from operation_pancake.importers.workbook_importer import WorkbookImporter
from operation_pancake.research.cfb27_phase2 import build_phase2_analysis, write_phase2_artifacts


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    cards = list(
        json.loads(
            (root / "data/external/cfb_fan_population_state.json").read_text(encoding="utf-8")
        )["cards"].values()
    )
    workbook = WorkbookImporter(root / "data/canonical/canonical_v1.9.xlsx")
    te_status = [
        record.values
        for record in workbook.records("TE_STATUS_BOARD")
        if record.values.get("Archetype")
        in ("Gritty Possession", "Physical Route Runner", "Vertical Threat")
    ]
    qb_rows = [record.values for record in workbook.records("Madden19_QB_Weights")]
    qb_weights = {
        archetype: {
            row["Attribute"]: float(row[archetype])
            for row in qb_rows
            if row.get(archetype) is not None and float(row[archetype]) > 0
        }
        for archetype in ("Field General", "Scrambler", "Strong Arm", "West Coast")
    }
    saturday = json.loads(
        (
            root / "data/research/center_exact_validation/saturday_frozen_model_validation.json"
        ).read_text(encoding="utf-8")
    )
    analysis = build_phase2_analysis(cards, te_status, qb_weights, saturday)
    write_phase2_artifacts(root / "data/research/cfb27_inheritance_phase2", analysis)
    print(
        f"Analyzed {analysis['population']['total']} cards; "
        f"Center ordinary n={analysis['center']['ordinary_n']}."
    )


if __name__ == "__main__":
    main()
