"""Generate deterministic Phase-IV research artifacts."""

from __future__ import annotations

import json
from pathlib import Path

from operation_pancake.importers.workbook_importer import WorkbookImporter
from operation_pancake.research.cfb27_phase4 import (
    build_phase4_analysis,
    freeze_phase4,
    write_phase4_artifacts,
)

TE_ATTRIBUTE_MAP = {
    "Speed": "SPD",
    "Acceleration": "ACC",
    "Agility": "AGI",
    "Strength": "STR",
    "Jumping": "JMP",
    "Awareness": "AWR",
    "Ball Carrier Vision": "BCV",
    "Break Tackle": "BTK",
    "Elusiveness": None,
    "Trucking": "TRK",
    "Stiff Arm": "SFA",
    "Catching": "CTH",
    "Catch in Traffic": "CIT",
    "Spectacular Catch": "SPC",
    "Release": "RLS",
    "Short Route Running": "SRR",
    "Medium Route Running": "MRR",
    "Deep Route Running": "DRR",
    "Impact Blocking": "IBL",
    "Lead Block": "LBK",
    "Pass Block": "PBK",
    "Pass Block Finesse": "PBF",
    "Pass Block Power": "PBP",
    "Run Block": "RBK",
    "Run Block Finesse": "RBF",
    "Run Block Power": "RBP",
}


def _load(root: Path, relative: str):
    return json.loads((root / relative).read_text(encoding="utf-8"))


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    state = _load(root, "data/external/cfb_fan_population_state.json")
    cards = list(state["cards"].values())
    workbook = WorkbookImporter(root / "data/canonical/canonical_v1.9.xlsx")
    canonical_te = [record.values for record in workbook.records("TE_Cards")]
    te_rows = [record.values for record in workbook.records("Madden19_TE_Weights")]
    te_weights = {
        archetype: {
            TE_ATTRIBUTE_MAP[row["Attribute"]]: float(row[archetype])
            for row in te_rows
            if TE_ATTRIBUTE_MAP[row["Attribute"]] is not None
            and row.get(archetype) is not None
            and float(row[archetype]) > 0
        }
        for archetype in ("Blocking", "Possession", "Vertical Threat")
    }
    qb_rows = [record.values for record in workbook.records("Madden19_QB_Weights")]
    qb_weights = {
        archetype: {
            row["Attribute"]: float(row[archetype])
            for row in qb_rows
            if row.get(archetype) is not None and float(row[archetype]) > 0
        }
        for archetype in ("Field General", "Scrambler", "Strong Arm", "West Coast")
    }
    phase3 = _load(root, "data/research/cfb27_inheritance_phase3/phase3_summary.json")
    source = _load(root, "data/research/cfb27_inheritance_phase4/ea_schema_sources.json")
    continuity = _load(
        root, "data/research/cfb27_inheritance_phase4/cross_year_table_continuity.json"
    )
    search = _load(
        root,
        "data/research/cfb27_inheritance_phase4/archetype_progression_schema_search.json",
    )
    analysis = build_phase4_analysis(
        canonical_te, cards, te_weights, qb_weights, phase3, source, continuity, search
    )
    ability_continuity = _load(
        root,
        "data/research/cfb27_inheritance_phase4/ability_progression_tunable_continuity.json",
    )
    analysis["table_44_cross_check"] = {
        "exact_historical_long_name_found": False,
        "ability_progression_tunable_present_games": sorted(
            game for game, table in ability_continuity.items() if table
        ),
        "m19_m21_asset_id": "115590",
        "m22_m27_asset_id": "102144",
        "cfb27_asset_id": "6494910",
        "finding": (
            "AbilityProgressionTunable exists in every M19-M27 and CFB27 schema. Madden "
            "retains six identical fields through M27; CFB27 retains the table name but changes "
            "its asset ID and fields. This strongly supports an EA table-family origin for the "
            "historical Table_44 artifact, but does not prove row-level identity."
        ),
        "confidence": "HIGH_ARCHITECTURAL_MODERATE_ROW_IDENTITY",
    }
    base_roster = root / "data/research/cfb27_inheritance_phase4/base_roster_pilot.json"
    if base_roster.exists():
        analysis["base_roster_pilot"] = json.loads(base_roster.read_text(encoding="utf-8"))
    output = root / "data/research/cfb27_inheritance_phase4"
    write_phase4_artifacts(output, analysis)
    (output / "phase4_frozen_snapshot.json").write_text(
        json.dumps(freeze_phase4(root, cards), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        f"Phase IV analyzed {len(cards)} cards and "
        f"{sum(result['historical']['pairs'] for result in analysis['te_null_tests'].values())} "
        "TE cross-OVR pairs."
    )


if __name__ == "__main__":
    main()
