import json
from pathlib import Path

from operation_pancake.importers.workbook_importer import WorkbookImporter
from operation_pancake.research.cfb27_phase2 import build_phase2_analysis

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "data/external/cfb_fan_population_state.json"
SUMMARY = ROOT / "data/research/cfb27_inheritance_phase2/phase2_summary.json"


def _summary():
    return json.loads(SUMMARY.read_text(encoding="utf-8"))


def test_expanded_population_is_large_complete_and_staging_only() -> None:
    state = json.loads(STATE.read_text(encoding="utf-8"))
    summary = _summary()
    assert summary["population"]["total"] >= 250
    assert summary["center"]["ordinary_n"] > 8
    assert len(summary["population"]["positions"]) >= 15
    assert all(len(card["displayed_ratings"]) >= 15 for card in state["cards"].values())
    assert summary["canonical_modified"] is False
    assert summary["guessed_values"] is False


def test_center_calibration_battery_is_leakage_safe_and_simple() -> None:
    center = _summary()["center"]
    assert set(center["calibrations"]) == {"linear", "affine", "discrete_threshold"}
    assert center["best_calibration"] in center["calibrations"]
    assert center["weight_perturbation"]["sign_change_required"] is False
    assert center["weight_stability"]["nearby_vectors_tested"] == 200
    assert all(row["n"] >= 1 for row in center["hidden_bands"])


def test_special_cards_are_separate_and_release_chronology_is_complete() -> None:
    summary = _summary()
    population = summary["population"]
    assert population["ordinary"] + population["special"] == population["total"]
    assert len(summary["release_chronology"]) == population["total"]
    assert summary["ordinary_vs_special"]


def test_position_descriptives_include_required_noncausal_diagnostics() -> None:
    descriptives = _summary()["position_descriptives"]
    assert set(descriptives) >= {"C", "QB", "HB", "WR", "TE", "CB", "DT", "MLB"}
    for position in descriptives.values():
        assert position["attribute_means_by_ovr"]
        assert position["attribute_means_by_archetype"]
        assert position["attributes"]
        assert "not a formula weight" in position["correlation_warning"]


def test_boundary_claims_require_large_same_archetype_cells() -> None:
    summary = _summary()
    assert summary["boundary_summary"]["diagnostics"] == len(summary["boundaries"])
    assert summary["boundary_summary"]["supported"] == 0
    for row in summary["boundaries"]:
        if row["classification"] == "CANDIDATE_THRESHOLD":
            assert row["lower_n"] >= 5 and row["upper_n"] >= 5
            assert row["effect"] >= 2


def test_saturday_te_and_qb_inheritance_are_not_overpromoted() -> None:
    summary = _summary()
    assert summary["saturday"]["compatibility"] == "COMPATIBLE_SPECIAL_TUNING"
    assert summary["saturday"]["positive_direction_transitions"] == 22
    assert summary["te"]["frozen_artifacts_modified"] is False
    assert {row["Archetype"] for row in summary["te"]["reproduction"]} == {
        "Gritty Possession",
        "Physical Route Runner",
        "Vertical Threat",
    }
    assert summary["qb"]["warning"]
    assert all(
        row["status"] in {"INHERITED_BASELINE_ONLY", "INSUFFICIENT_OVR_BREADTH"}
        for row in summary["qb"]["archetypes"].values()
    )


def test_analysis_rebuilds_deterministically() -> None:
    summary = _summary()
    cards = list(json.loads(STATE.read_text(encoding="utf-8"))["cards"].values())
    workbook = WorkbookImporter(ROOT / "data/canonical/canonical_v1.9.xlsx")
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
            ROOT / "data/research/center_exact_validation/saturday_frozen_model_validation.json"
        ).read_text(encoding="utf-8")
    )
    rebuilt = build_phase2_analysis(cards, te_status, qb_weights, saturday)
    assert json.loads(json.dumps(rebuilt, sort_keys=True)) == summary
