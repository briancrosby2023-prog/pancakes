"""Tests for source-supported QB progression and provenance auditing."""

import json
from pathlib import Path

import pytest

from operation_pancake.research.qb_formula_phase import QB_RATING_FIELDS
from operation_pancake.research.qb_model_comparison import build_model_comparison
from operation_pancake.research.qb_provenance_audit import (
    CONFIRMED,
    CONTRADICTED,
    SYSTEMATIC_ERROR_QB_IDS,
    build_provenance_audit,
    write_provenance_artifacts,
)


@pytest.fixture(scope="module")
def research() -> dict[str, object]:
    return json.loads(
        Path("data/research/qb_formula_phase_population_boundary.json").read_text(encoding="utf-8")
    )


@pytest.fixture(scope="module")
def audit(research: dict[str, object]) -> dict[str, object]:
    return build_provenance_audit(
        research,
        build_model_comparison(research),
        "data/canonical/canonical_v1.9.xlsx",
        [str(path) for path in Path(".").rglob("*") if path.is_file()],
    )


def test_all_17_candidates_are_classified_without_false_linkage(
    audit: dict[str, object],
) -> None:
    assert len(audit["sequences"]) == 17
    assert audit["sequence_classification_counts"] == {
        CONFIRMED: 2,
        CONTRADICTED: 15,
        "PROBABLE_PROGRESSION": 0,
        "UNRESOLVED": 0,
    }
    assert all(
        item["lower"]["program"] == item["upper"]["program"]
        for item in audit["sequences"]
        if item["classification"] == CONFIRMED
    )
    assert all(
        item["lower"]["program"] != item["upper"]["program"]
        for item in audit["sequences"]
        if item["classification"] == CONTRADICTED
    )


def test_explicit_79_to_81_link_is_recovered_as_a_constraint(
    audit: dict[str, object],
) -> None:
    pairs = [(item["lower_qb_id"], item["upper_qb_id"]) for item in audit["confirmed_constraints"]]
    assert set(pairs) == {
        ("QB-0074", "QB-0038"),
        ("QB-0038", "QB-0013"),
        ("QB-0013", "QB-0003"),
    }
    assert audit["recovered_confirmed_constraints"][0]["recovered_outside_17_candidates"]


def test_qb_0074_is_complete_and_not_silently_corrected(
    audit: dict[str, object],
) -> None:
    card = audit["qb_0074_provenance"]
    assert card["all_15_ratings_present"]
    assert set(card["ratings"]) == set(QB_RATING_FIELDS)
    assert card["overall"] == 79
    assert card["source_id"] == "SRC-QB-002"
    assert card["transcription_or_mapping_issue_found"] is False
    assert audit["canonical_corrections_found"] == []


def test_systematic_error_cards_preserve_complete_provenance(
    audit: dict[str, object],
) -> None:
    cards = audit["systematic_error_card_audits"]
    assert {card["qb_id"] for card in cards} == set(SYSTEMATIC_ERROR_QB_IDS)
    assert all(card["all_15_ratings_present"] for card in cards)
    assert all(card["source_id"] and card["source_locator"] for card in cards)
    assert all(not card["profile_duplicate_qb_ids"] for card in cards)


def test_raw_source_absence_is_explicitly_backlogged(audit: dict[str, object]) -> None:
    assert all(
        not item["source_content_directly_available_in_repository"]
        for item in audit["source_inventory"]
    )
    scopes = {item["scope"] for item in audit["evidence_acquisition_backlog"]}
    assert scopes == {
        "raw_source_preservation",
        "systematic_error_source_reverification",
    }


def test_audit_and_artifacts_are_deterministic(
    research: dict[str, object], audit: dict[str, object], tmp_path: Path
) -> None:
    second = build_provenance_audit(
        research,
        build_model_comparison(research),
        "data/canonical/canonical_v1.9.xlsx",
        [str(path) for path in Path(".").rglob("*") if path.is_file()],
    )
    assert second == audit
    write_provenance_artifacts(tmp_path, audit)
    assert len(list(tmp_path.glob("*.json"))) == 8
