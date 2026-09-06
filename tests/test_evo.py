from copy import deepcopy
from operation_pancake.evo import EVODefinition, EVOStore, decide_evo, enrich_candidates, filter_candidates, projected_production


def player(pid="p1", position="SS", archetype="Coverage", overall=82):
    return {"card_id": pid, "id": pid, "position": position, "archetype": archetype, "native_overall": overall, "overall": overall, "native_ratings": {"speed": 90, "zone": 80}}


def test_persistence_round_trip(tmp_path):
    store = EVOStore(tmp_path / "evo.json"); evo = EVODefinition("e1", "Coverage EVO", 85, ("SS",), ("Coverage",), 80, 84, known_attribute_boosts={"speed": 2}); store.save([evo]); assert store.load() == [evo]


def test_verified_eligibility_position_archetype_ovr():
    evo = EVODefinition("e1", "E", 85, ("SS",), ("Coverage",), 80, 84)
    assert evo.eligible(player())[0]; assert not evo.eligible(player(position="FS"))[0]; assert not evo.eligible(player(archetype="Run Support"))[0]; assert not evo.eligible(player(overall=85))[0]


def test_owned_and_acquisition_filters_are_disjoint():
    evo = EVODefinition("e1", "E", 85, ("SS",)); players = [player("owned"), player("market")]
    assert [x["card_id"] for x in filter_candidates(evo, players, {"owned"}, "owned")] == ["owned"]
    assert [x["card_id"] for x in filter_candidates(evo, players, {"owned"}, "acquisition")] == ["market"]
    assert filter_candidates(evo, players, {"owned"}, "acquisition")[0]["ownership"] == "ACQUISITION"


def test_unknown_boosts_do_not_infer_final_state_or_score():
    projection = EVODefinition("e1", "E", 85, ("SS",)).project(player())
    assert projection["final_attributes"] is None; assert projection["final_pancake_score"] is None; assert projection["final_position_rank"] is None; assert "FINAL ATTRIBUTES UNKNOWN" in projection["limitations"]


def test_known_boosts_apply_to_native_ratings_only_and_do_not_mutate_canonical():
    original = player(); before = deepcopy(original); projection = EVODefinition("e1", "E", 85, ("SS",), known_attribute_boosts={"speed": 3}).project(original)
    assert projection["final_attributes"]["native_ratings"]["speed"] == 93; assert projection["attribute_deltas"]["speed"]["boost"] == 3; assert original == before


def test_headroom_is_descriptive_not_projection():
    candidate = filter_candidates(EVODefinition("e1", "E", 85, ("SS",)), [player(overall=81)])[0]
    assert candidate["ovr_headroom"] == 4; assert "headroom is descriptive only" in candidate["limitations"]


class FakeEngine:
    def score(self, card):
        score = card.get("native_ratings", {}).get("speed")
        return {"card_id": card["card_id"], "position_family": card["position"], "archetype": card["archetype"], "routing": {"status": "ROUTED"}, "score": score, "score_status": "SCORED_COMPLETE", "score_confidence": "HIGH", "model_limitations": []}
    def rank(self, rows):
        ordered = sorted((r for r in rows if r.get("score") is not None), key=lambda r: -r["score"])
        return [{**r, "position_rank": i} for i, r in enumerate(ordered, 1)]


class FakeGM:
    def __init__(self):
        self.population = [player("p1"), player("p2", overall=83)]; self.population[1]["native_ratings"]["speed"] = 95
        self.engine = FakeEngine(); self.ranked = self.engine.rank([self.engine.score(c) for c in self.population]); self.rank_by_id = {r["card_id"]: r for r in self.ranked}


def test_candidate_production_enrichment_all_owned_acquisition():
    gm=FakeGM(); evo=EVODefinition("e","E",85,("SS",))
    all_rows=enrich_candidates(evo,gm,{"p1"},"all"); owned=enrich_candidates(evo,gm,{"p1"},"owned"); acquisition=enrich_candidates(evo,gm,{"p1"},"acquisition")
    assert len(all_rows)==2 and [r["card_id"] for r in owned]==["p1"] and [r["card_id"] for r in acquisition]==["p2"]
    assert owned[0]["production"]["score"]==90 and owned[0]["production"]["position_rank"]==2


def test_verified_projection_uses_production_engine_and_temporary_rank():
    gm=FakeGM(); canonical=gm.population[0]; before=deepcopy(canonical); evo=EVODefinition("e","E",85,("SS",),known_attribute_boosts={"speed":7})
    projection=projected_production(evo,gm,canonical)
    assert projection["production"]["score"]==97 and projection["production"]["position_rank"]==1 and projection["production"]["confidence"]=="LIMITED"; assert canonical==before


def test_unknown_projection_never_calls_fake_score_for_final_state():
    gm=FakeGM(); projection=projected_production(EVODefinition("e","E",85,("SS",)),gm,gm.population[0])
    assert projection["production"]["score"] is None and projection["production"]["position_rank"] is None and projection["production"]["confidence"]=="UNKNOWN"


def test_missing_verified_rating_keeps_projection_unknown():
    gm=FakeGM(); projection=projected_production(EVODefinition("e","E",85,("SS",),known_attribute_boosts={"not_a_rating":3}),gm,gm.population[0])
    assert projection["production"]["score"] is None; assert any("No verified boost" in x for x in projection["production"]["limitations"])


def test_protected_slot_blocks_evo_instruction():
    assert decide_evo(slot_protected=True,slot_rerollable=False,projected_improvement=True,replacement_improvement=False,replacement_cost=None,evo_base_cost=None,final_attributes_known=True)["decision"]=="KEEP CURRENT PLAYER"


def test_unknown_final_state_saves_evo_without_known_better_path():
    assert decide_evo(slot_protected=False,slot_rerollable=False,projected_improvement=None,replacement_improvement=None,replacement_cost=None,evo_base_cost=None,final_attributes_known=False)["decision"]=="SAVE EVO"


def test_known_replacement_can_beat_unknown_evo():
    assert decide_evo(slot_protected=False,slot_rerollable=False,projected_improvement=None,replacement_improvement=True,replacement_cost=50000,evo_base_cost=None,final_attributes_known=False)["decision"]=="BUY REPLACEMENT"


def test_known_evo_improvement_can_win():
    assert decide_evo(slot_protected=False,slot_rerollable=False,projected_improvement=True,replacement_improvement=False,replacement_cost=None,evo_base_cost=10000,final_attributes_known=True)["decision"]=="USE EVO"


def test_known_non_improvement_saves_evo():
    assert decide_evo(slot_protected=False,slot_rerollable=False,projected_improvement=False,replacement_improvement=False,replacement_cost=None,evo_base_cost=10000,final_attributes_known=True)["decision"]=="SAVE EVO"


def test_unresolved_supported_projection_requires_review():
    assert decide_evo(slot_protected=False,slot_rerollable=True,projected_improvement=None,replacement_improvement=None,replacement_cost=None,evo_base_cost=None,final_attributes_known=True)["decision"]=="REVIEW"
