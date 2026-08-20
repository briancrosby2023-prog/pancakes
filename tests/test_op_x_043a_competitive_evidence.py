from copy import deepcopy
from pathlib import Path

import pytest

from operation_pancake.production.competitive_evidence import (
    aggregate_threshold,
    import_evidence,
    meta_summary,
    resolve_card,
)
from operation_pancake.production.engine import load_population

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def population():
    return load_population(ROOT)


def base_row(**changes):
    row = {
        "source_url": "https://example.test/video",
        "publisher": "Creator One",
        "publication_timestamp": "2026-08-20T12:00:00+00:00",
        "evidence_type": "CREATOR STATEMENT",
        "extraction": "I want at least 85 throw power",
        "criterion": "THROW POWER",
        "criterion_type": "PERSONAL MINIMUM",
        "criterion_value": 85,
    }
    row.update(changes)
    return row


def record(**changes):
    row = {
        "source_family": "creatorone",
        "criterion_attribute": "THP",
        "criterion_type": "PERSONAL MINIMUM",
        "criterion_value": 85,
        "stated_criterion": True,
        "observed_usage": False,
        "position": "QB",
        "ability": "UNKNOWN",
        "ability_status": "UNKNOWN",
        "playbook": "UNKNOWN",
        "playbook_status": "UNKNOWN",
        "formation": "UNKNOWN",
        "card_resolution": {"classification": "UNRESOLVED", "canonical_card_id": None},
    }
    row.update(changes)
    return row


def test_exact_card_evidence(population):
    card = population[0]
    assert resolve_card({"card_id": card["card_id"]}, population)["classification"] == "EXACT"


def test_ambiguous_card_remains_ambiguous():
    cards = [
        {
            "card_id": "1",
            "player_name": "A",
            "position": "QB",
            "native_overall": 80,
            "program": "X",
        },
        {
            "card_id": "2",
            "player_name": "A",
            "position": "QB",
            "native_overall": 81,
            "program": "Y",
        },
    ]
    assert resolve_card({"player": "A"}, cards)["classification"] == "AMBIGUOUS"


def test_missing_optional_fields_become_unknown(monkeypatch, population):
    monkeypatch.setattr(
        "operation_pancake.production.competitive_evidence._pancake_link",
        lambda *_: {"status": "UNAVAILABLE"},
    )
    result = import_evidence(ROOT, [base_row()], [])
    assert result["accepted"][0]["ability"] == "UNKNOWN"


def test_usage_does_not_become_threshold_testimony():
    usage = record(observed_usage=True, stated_criterion=False, criterion_value=90)
    assert aggregate_threshold([usage], "THP")["verdict"] == "INSUFFICIENT"


def test_personal_minimum_does_not_become_universal():
    summary = meta_summary([record()])
    assert summary["criteria"][0]["criterion_type"] == "PERSONAL MINIMUM"


def test_available_ability_is_not_equipped():
    summary = meta_summary([record(ability="DOT!", ability_status="AVAILABLE")])
    assert summary["abilities"][0]["status"] == "AVAILABLE"


def test_recommended_playbook_is_not_observed():
    summary = meta_summary([record(playbook="FIU", playbook_status="RECOMMENDED")])
    assert summary["playbooks"][0]["status"] == "RECOMMENDED"


def test_partial_roster_remains_partial(monkeypatch):
    monkeypatch.setattr(
        "operation_pancake.production.competitive_evidence.GMProduct",
        lambda root: type("G", (), {"population": []})(),
    )
    result = import_evidence(
        ROOT, [base_row(evidence_type="ROSTER", roster_completeness="PARTIAL")]
    )
    assert result["accepted"][0]["roster_completeness"] == "PARTIAL"


def test_same_creator_does_not_create_independence():
    rows = [record(), record(criterion_value=86)]
    assert aggregate_threshold(rows, "THP")["independent_sources"] == 1


def test_duplicate_evidence_deduplicates(monkeypatch):
    monkeypatch.setattr(
        "operation_pancake.production.competitive_evidence.GMProduct",
        lambda root: type("G", (), {"population": []})(),
    )
    result = import_evidence(ROOT, [base_row(), deepcopy(base_row())])
    assert result["accepted_count"] == 2 and result["deduplicated_total"] == 1


def test_malformed_evidence_rejected_safely(monkeypatch):
    monkeypatch.setattr(
        "operation_pancake.production.competitive_evidence.GMProduct",
        lambda root: type("G", (), {"population": []})(),
    )
    result = import_evidence(ROOT, [{"source_url": "x"}])
    assert result["accepted_count"] == 0 and result["rejected_count"] == 1


def test_pancake_link_does_not_modify_scoring(population):
    card = population[0]
    before = deepcopy(card)
    result = import_evidence(ROOT, [base_row(card_id=card["card_id"])])
    assert result["accepted"][0]["pancake_link"]["model_modified"] is False
    assert card == before


def test_thp_mac_aggregation_deterministic():
    rows = [record(), record(source_family="creatortwo", criterion_attribute="MAC")]
    first = meta_summary(rows)["threshold_testimony"]
    second = meta_summary(list(reversed(rows)))["threshold_testimony"]
    assert first == second
