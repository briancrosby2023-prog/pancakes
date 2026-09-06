from pathlib import Path

from operation_pancake.production.competitive_evidence import import_evidence
from operation_pancake.production.contextual_value import (
    AbilityContext,
    Deployment,
    FrozenBase,
    RealizedBuild,
    classify_residual,
    contextual_report,
    contextualize,
)
from operation_pancake.production.engine import load_population

ROOT = Path(__file__).resolve().parents[1]
BASE = FrozenBase(84.25, 7, 92.1)
EXPECTED = (84.25, 7, 92.1)


def test_context_never_mutates_frozen_evaluation():
    result = contextualize(
        BASE,
        Deployment("QB", "QB", deployment_role="POCKET", assignments=("POCKET",)),
        behavior="NEGATIVE",
        functional_risks=("QB RELEASE",),
    )
    assert result.frozen_identity() == EXPECTED


def test_unknown_context_is_not_bonus_or_penalty():
    result = contextualize(BASE, Deployment("TE"))
    assert result.verdict == "UNKNOWN" and result.behavior == "UNKNOWN"
    assert result.functional_advantages == () and result.functional_risks == ()


def test_treydez_green_identity_survives_gadget_hb_deployment():
    te = contextualize(
        BASE,
        Deployment("TE", "TE", deployment_role="RECEIVING_MISMATCH", assignments=("RECEIVING",)),
        role_fit="PARTIAL",
        functional_risks=("BLOCKING",),
    )
    hb = contextualize(
        BASE,
        Deployment(
            "TE",
            "HB",
            specialist_slot="GADGET",
            deployment_role="POWER_MOVEMENT",
            assignments=("RECEIVING",),
        ),
        role_fit="SUPPORTED",
        behavior="POSITIVE",
        verdict="SPECIALIST FIT",
    )
    assert te.deployment.canonical_position == hb.deployment.canonical_position == "TE"
    assert hb.deployment.deployment_position == "HB"
    assert te.frozen_identity() == hb.frozen_identity() == EXPECTED


def test_rgiii_and_benkert_release_context_only():
    rgiii = contextualize(
        BASE, Deployment("QB", "QB"), behavior="NEGATIVE", functional_risks=("QB RELEASE",)
    )
    benkert = contextualize(
        BASE, Deployment("QB", "QB"), behavior="POSITIVE", functional_advantages=("QB RELEASE",)
    )
    assert rgiii.frozen_identity() == benkert.frozen_identity() == EXPECTED


def test_bo_movement_risk_does_not_change_score():
    result = contextualize(
        BASE,
        Deployment("RB", "RB", deployment_role="POWER_MOVEMENT"),
        behavior="MIXED",
        functional_risks=("TIGHT-HOLE MOVEMENT",),
    )
    assert result.base == BASE


def test_sherman_assignment_counterfactual():
    zone = contextualize(
        BASE,
        Deployment("CB", "CB", assignments=("ZONE",)),
        scheme_fit="SUPPORTED",
        verdict="GOOD FIT",
    )
    man = contextualize(
        BASE,
        Deployment("CB", "CB", assignments=("MAN",)),
        scheme_fit="CONFLICT",
        verdict="SPECIALIST FIT",
    )
    assert zone.frozen_identity() == man.frozen_identity() == EXPECTED


def test_amauiri_and_sammy_are_role_specific():
    run_dt = contextualize(
        BASE,
        Deployment("DT", "DT", deployment_role="RUN_STOPPER", assignments=("RUN_DEFENSE",)),
        role_fit="SUPPORTED",
        verdict="SPECIALIST FIT",
    )
    coverage_lb = contextualize(
        BASE,
        Deployment("LB", "LB", deployment_role="COVERAGE_USER", assignments=("ZONE",)),
        role_fit="SUPPORTED",
        verdict="GOOD FIT",
    )
    assert run_dt.base == coverage_lb.base == BASE


def test_ability_semantics_reuse_op_x_043a_statuses():
    available = AbilityContext("DOT", ability_status="AVAILABLE")
    equipped = AbilityContext("DOT", ability_status="EQUIPPED")
    assert available.ability_status != equipped.ability_status


def test_theoretical_build_cannot_masquerade_as_observed():
    assert RealizedBuild("candidate").status == "THEORETICAL"


def test_residual_does_not_claim_model_error():
    row = classify_residual(
        high_pancake=True, adopted=False, rejected=True, explanation="ANIMATION"
    )
    assert row["category"] == "HIGH_PANCAKE_REJECTION" and row["model_error_claimed"] is False


def test_op_x_043a_import_accepts_context_fields(monkeypatch):
    monkeypatch.setattr(
        "operation_pancake.production.competitive_evidence.GMProduct",
        lambda root: type("G", (), {"population": []})(),
    )
    row = {
        "source_url": "https://example.test/context",
        "publisher": "Creator",
        "publication_timestamp": "2026-08-20T00:00:00+00:00",
        "evidence_type": "OBSERVED GAMEPLAY",
        "extraction": "used in the slot",
        "context_evidence_kind": "OBSERVED_USAGE",
        "behavior_state": "POSITIVE",
        "role_fit": "SUPPORTED",
        "scheme_fit": "PARTIAL",
        "deployment_position": "HB",
        "specialist_slot": "GADGET",
        "deployment_role": "POWER_MOVEMENT",
        "assignments": ["RECEIVING"],
        "build_id": "build-1",
        "build_status": "OBSERVED",
        "functional_advantages": ["OPEN-FIELD MOVEMENT"],
    }
    accepted = import_evidence(ROOT, [row])["accepted"][0]
    assert accepted["context_evidence_kind"] == "OBSERVED_USAGE"
    assert accepted["deployment_position"] == "HB"
    assert accepted["build_status"] == "OBSERVED"


def test_recommendation_remains_distinct_from_observed_usage(monkeypatch):
    monkeypatch.setattr(
        "operation_pancake.production.competitive_evidence.GMProduct",
        lambda root: type("G", (), {"population": []})(),
    )
    row = {
        "source_url": "https://example.test/recommend",
        "publisher": "Creator",
        "publication_timestamp": "2026-08-20T00:00:00+00:00",
        "evidence_type": "CREATOR STATEMENT",
        "extraction": "recommended",
        "context_evidence_kind": "RECOMMENDATION",
    }
    accepted = import_evidence(ROOT, [row])["accepted"][0]
    assert accepted["context_evidence_kind"] == "RECOMMENDATION"
    assert accepted["observed_usage"] is False


def test_contextual_report_exposes_frozen_gm_value_without_mutation():
    card = load_population(ROOT)[0]
    report = contextual_report(ROOT, card["card_id"])
    assert report["status"] == "CONTEXTUALIZED"
    assert report["frozen_evaluation"]["position_percentile"] is not None
    assert report["score_modified"] is False
    assert report["buy_gates_modified"] is False
    assert report["market_semantics_modified"] is False
    assert report["unknowns"]
