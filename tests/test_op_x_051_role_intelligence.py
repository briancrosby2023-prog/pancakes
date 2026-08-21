from operation_pancake.production.role_intelligence import ROLE_ATTRIBUTES, card_role_candidates, role_profile, scientific_firewall


def test_same_card_can_have_multiple_role_candidates_without_numeric_context_score():
    card={"position":"CB","attributes":{"SPD":90,"ACC":90,"MCV":90,"ZCV":90,"PRS":90,"PRC":90}}
    roles={r["role"] for r in card_role_candidates(card) if r["classification"]=="ROLE CANDIDATE"}
    assert {"MAN","ZONE","PRESS","HYBRID"} <= roles
    assert all(r["verified_role_fit"] is False for r in card_role_candidates(card))


def test_unknown_missing_traits_is_not_penalty():
    rows=card_role_candidates({"position":"QB","attributes":{}})
    assert rows and all(r["classification"]=="UNKNOWN" for r in rows)


def test_role_profiles_do_not_invent_weights():
    p=role_profile("CB","MAN")
    assert p["relative_importance"]=="UNKNOWN"
    assert p["modeled_attributes"]==list(ROLE_ATTRIBUTES["CB"]["MAN"])


def test_deployment_family_does_not_mutate_canonical_position():
    card={"position":"TE","attributes":{"SPD":90,"ACC":90,"CTH":90,"CIT":90,"SRR":90,"MRR":90}}
    assert card["position"]=="TE"
    assert card_role_candidates(card)[0]["position_family"]=="TE"


def test_market_and_purchase_firewall():
    f=scientific_firewall()
    assert not any(f.values())


def test_lower_ovr_specialist_is_semantically_allowed():
    # OP-X-051 alternatives rank binding-trait preservation; OVR is not a binding role requirement.
    p=role_profile("DT","RUN_STOPPER")
    assert "STR" in p["modeled_attributes"] and "BSH" in p["modeled_attributes"]
    assert "OVR" not in p["modeled_attributes"]
