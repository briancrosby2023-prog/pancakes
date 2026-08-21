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


def test_role_alternatives_reads_canonical_population_attributes():
    from pathlib import Path
    import operation_pancake.production.role_intelligence as ri

    class FakeProduct:
        def __init__(self, root):
            self.cards={"target":{"card_id":"target","position":"QB","attributes":{"THP":90,"SAC":90,"MAC":90,"DAC":90,"TUP":90}}}
            self.population=[self.cards["target"],{"card_id":"alt","position":"QB","native_overall":80,"player_name":"Alt","attributes":{"THP":89,"SAC":90,"MAC":90,"DAC":90,"TUP":90}}]
        def lookup(self, card_id):
            # Deliberately identity-only: regression proves role_alternatives does not require attributes here.
            return {"card":{"card_id":card_id,"position":"QB"}}

    original=ri.GMProduct
    ri.GMProduct=FakeProduct
    try:
        result=ri.role_alternatives(Path('.'),"target","POCKET",10)
    finally:
        ri.GMProduct=original
    assert result["status"]=="CANDIDATES"
    assert result["alternatives"][0]["card_id"]=="alt"
    assert result["alternatives"][0]["trait_distance"]==1.0
