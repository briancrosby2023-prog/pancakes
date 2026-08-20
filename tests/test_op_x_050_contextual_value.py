from operation_pancake.production.contextual_value import (
    AbilityContext, ContextEvidence, Deployment, FrozenBase, RealizedBuild,
    classify_residual, contextualize,
)

BASE = FrozenBase(84.25, 7, 92.1)
EXPECTED = (84.25, 7, 92.1)

def test_context_never_mutates_frozen_evaluation():
    result = contextualize(BASE, Deployment("QB", "QB", deployment_role="POCKET", assignments=("POCKET",)), behavior="NEGATIVE", functional_risks=("QB RELEASE",))
    assert result.frozen_identity() == EXPECTED

def test_unknown_context_is_not_bonus_or_penalty():
    result = contextualize(BASE, Deployment("TE"))
    assert result.verdict == "UNKNOWN" and result.behavior == "UNKNOWN"
    assert result.functional_advantages == () and result.functional_risks == ()

def test_treydez_green_identity_survives_gadget_hb_deployment():
    te = contextualize(BASE, Deployment("TE", "TE", deployment_role="RECEIVING_MISMATCH", assignments=("RECEIVING",)), role_fit="PARTIAL", functional_risks=("BLOCKING",))
    hb = contextualize(BASE, Deployment("TE", "HB", specialist_slot="GADGET", deployment_role="POWER_MOVEMENT", assignments=("RECEIVING",)), role_fit="SUPPORTED", behavior="POSITIVE", verdict="SPECIALIST FIT")
    assert te.deployment.canonical_position == hb.deployment.canonical_position == "TE"
    assert hb.deployment.deployment_position == "HB"
    assert te.frozen_identity() == hb.frozen_identity() == EXPECTED

def test_rgiii_and_benkert_release_context_only():
    rgiii = contextualize(BASE, Deployment("QB", "QB"), behavior="NEGATIVE", functional_risks=("QB RELEASE",))
    benkert = contextualize(BASE, Deployment("QB", "QB"), behavior="POSITIVE", functional_advantages=("QB RELEASE",))
    assert rgiii.frozen_identity() == benkert.frozen_identity() == EXPECTED

def test_bo_movement_risk_does_not_change_score():
    result = contextualize(BASE, Deployment("RB", "RB", deployment_role="POWER_MOVEMENT"), behavior="MIXED", functional_risks=("TIGHT-HOLE MOVEMENT",))
    assert result.base == BASE

def test_sherman_assignment_counterfactual():
    zone = contextualize(BASE, Deployment("CB", "CB", assignments=("ZONE",)), scheme_fit="SUPPORTED", verdict="GOOD FIT")
    man = contextualize(BASE, Deployment("CB", "CB", assignments=("MAN",)), scheme_fit="CONFLICT", verdict="SPECIALIST FIT")
    assert zone.frozen_identity() == man.frozen_identity() == EXPECTED

def test_amauiri_and_sammy_are_role_specific():
    run_dt = contextualize(BASE, Deployment("DT", "DT", deployment_role="RUN_STOPPER", assignments=("RUN_DEFENSE",)), role_fit="SUPPORTED", verdict="SPECIALIST FIT")
    coverage_lb = contextualize(BASE, Deployment("LB", "LB", deployment_role="COVERAGE_USER", assignments=("ZONE",)), role_fit="SUPPORTED", verdict="GOOD FIT")
    assert run_dt.base == coverage_lb.base == BASE

def test_ability_semantics_are_separate():
    a = AbilityContext("DOT", available=True, equipped=False, competitive_evidence=ContextEvidence(state="POSITIVE"))
    assert a.available is True and a.equipped is False

def test_theoretical_build_cannot_masquerade_as_observed():
    assert RealizedBuild("candidate").status == "THEORETICAL"

def test_residual_does_not_claim_model_error():
    row = classify_residual(high_pancake=True, adopted=False, rejected=True, explanation="ANIMATION")
    assert row["category"] == "HIGH_PANCAKE_REJECTION" and row["model_error_claimed"] is False
