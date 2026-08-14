from pathlib import Path

import pytest

from operation_pancake.evidence.catalog import build_evidence_index

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_PLAYERS = {
    "Ashton Beers",
    "Justin Evans",
    "Bruce Mitchell",
    "Carson Hinzman",
    "Brady Small",
    "Coleton Price",
    "Landen Hatchett",
    "Lyndon Cooper",
    "Jake Guarnera",
    "Jake Renfro",
    "Levi Hubbard",
}
REQUIRED_SEARCH_PLAYERS = EXPECTED_PLAYERS - {"Ashton Beers", "Justin Evans", "Bruce Mitchell"}


@pytest.fixture(scope="module")
def index():
    return build_evidence_index(ROOT)


def historical_rows(index):
    return [
        values
        for (kind, _), values in index.records.items()
        if kind == "historical_center_observation"
    ]


def test_twelve_historical_center_results_are_preserved_without_vectors(index) -> None:
    rows = historical_rows(index)
    assert len(rows) == 12
    assert {row["player"] for row in rows} == EXPECTED_PLAYERS
    assert all(row["provenance_status"] == "HISTORICALLY_RECOVERED" for row in rows)
    assert all("attributes" not in row for row in rows)
    assert all(row["unextracted_cut_fields"] for row in rows)


def test_recovered_comparison_values_are_exact(index) -> None:
    rows = historical_rows(index)
    brady = next(row for row in rows if row["player"] == "Brady Small")
    core_beers = next(row for row in rows if row["profile"] == "Core")
    assert (brady["weighted_average"], brady["cut_ovr"]) == (80.10, 84)
    assert (core_beers["weighted_average"], core_beers["cut_ovr"]) == (78.72, 81)


def test_required_player_searches_expose_missing_cut_fields(index) -> None:
    for player in REQUIRED_SEARCH_PLAYERS:
        rows = [
            row
            for row in index.search(player)["records"]
            if row["target_type"] == "historical_center_observation"
        ]
        assert rows, player
        assert all("Q-C-004-014" in row["unextracted_cut_fields"] for row in rows)


def test_historical_workbook_and_models_are_research_only(index) -> None:
    source = index.sources["SRC-C-HIST-WB-001"]
    assert source.original_filename == "Operation_Pancake_Madden19_Center_Formula.xlsx"
    assert source.extraction_status == "COMPLETE"
    madden = index.records[("historical_model_result", "HIST-M19-CENTER-MODEL-001")]
    assert madden["population"] == 53
    assert madden["weight_total"] == 108
    assert madden["weights"]["RBP"] == 22
    assert madden["production_formula"] is False
    curve = index.records[("historical_model_result", "HIST-CFB-CENTER-CURVE-001")]
    assert curve["slope"] == 0.8206312512486102
    assert curve["production_formula"] is False


def test_cut_ea_and_historical_evidence_remain_separate(index) -> None:
    cut = index.sources["SRC-C-RAW-003"]
    ea = index.sources["SRC-RATE-001"]
    historical = index.sources["SRC-C-HIST-WB-001"]
    assert len({cut.category, ea.category, historical.category}) == 3
    model = index.record_provenance("historical_model_result", "HIST-M19-CENTER-MODEL-001")
    relationships = {link["relationship"] for link in model["sources"]}
    assert relationships == {"HISTORICAL_MODEL_SOURCE", "EA_BASE_ROSTER_REFERENCE_POPULATION"}


def test_duplicate_source_ids_are_reconciled_without_deletion(index) -> None:
    assert index.sources["SRC-C-RAW-001"]
    assert index.sources["SRC-C-RAW-002"].duplicate_of == "SRC-C-RAW-001"
    assert index.sources["SRC-C-RAW-003"]
    assert index.queue["REC-SRC-C-RAW-001"].status == "RESOLVED"
    assert index.queue["REC-SRC-C-RAW-002"].status == "RESOLVED"


def test_center_pdf_is_known_not_missing_and_remains_actionable(index) -> None:
    source = index.sources["SRC-C-RAW-003"]
    assert source.origin == "CHATGPT_FILE_LIBRARY"
    assert "Confirmed to exist" in source.notes
    assert "pages 4-14" in source.extraction_remaining
    queue = index.queue["REC-SRC-C-RAW-003"]
    assert queue.status == "OPEN"
    assert queue.issue_type == "PARTIALLY_EXTRACTED"
    assert index.audit()["open_reconciliation_count"] == 9
