from operation_pancake.evo import EVODefinition, EVOStore, decide_evo, filter_candidates


def player(pid="p1", position="SS", archetype="Coverage", overall=82):
    return {"id": pid, "position": position, "archetype": archetype, "overall": overall, "speed": 90}


def test_persistence_round_trip(tmp_path):
    store = EVOStore(tmp_path / "evo.json")
    evo = EVODefinition("e1", "Coverage EVO", 85, ("SS",), ("Coverage",), 80, 84, known_attribute_boosts={"speed": 2})
    store.save([evo])
    assert store.load() == [evo]


def test_verified_eligibility_position_archetype_ovr():
    evo = EVODefinition("e1", "E", 85, ("SS",), ("Coverage",), 80, 84)
    assert evo.eligible(player())[0]
    assert not evo.eligible(player(position="FS"))[0]
    assert not evo.eligible(player(archetype="Run Support"))[0]
    assert not evo.eligible(player(overall=85))[0]


def test_owned_and_acquisition_filters_are_disjoint():
    evo = EVODefinition("e1", "E", 85, ("SS",))
    players = [player("owned"), player("market")]
    assert [x["id"] for x in filter_candidates(evo, players, {"owned"}, "owned")] == ["owned"]
    assert [x["id"] for x in filter_candidates(evo, players, {"owned"}, "acquisition")] == ["market"]


def test_unknown_boosts_do_not_infer_final_state_or_score():
    evo = EVODefinition("e1", "E", 85, ("SS",))
    projection = evo.project(player())
    assert projection["final_attributes"] is None
    assert projection["final_pancake_score"] is None
    assert "FINAL ATTRIBUTES UNKNOWN" in projection["limitations"]


def test_known_boosts_apply_only_verified_attributes():
    evo = EVODefinition("e1", "E", 85, ("SS",), known_attribute_boosts={"speed": 3})
    projection = evo.project(player())
    assert projection["final_attributes"]["speed"] == 93
    assert projection["attribute_deltas"]["speed"]["boost"] == 3


def test_headroom_is_descriptive_not_projection():
    evo = EVODefinition("e1", "E", 85, ("SS",))
    candidate = filter_candidates(evo, [player(overall=81)])[0]
    assert candidate["ovr_headroom"] == 4
    assert "headroom is descriptive only" in candidate["limitations"]


def test_protected_slot_blocks_evo_instruction():
    result = decide_evo(slot_protected=True, slot_rerollable=False, projected_improvement=True, replacement_improvement=False, replacement_cost=None, evo_base_cost=None, final_attributes_known=True)
    assert result["decision"] == "KEEP CURRENT PLAYER"


def test_unknown_final_state_saves_evo_without_known_better_path():
    result = decide_evo(slot_protected=False, slot_rerollable=False, projected_improvement=None, replacement_improvement=None, replacement_cost=None, evo_base_cost=None, final_attributes_known=False)
    assert result["decision"] == "SAVE EVO"


def test_known_replacement_can_beat_unknown_evo():
    result = decide_evo(slot_protected=False, slot_rerollable=False, projected_improvement=None, replacement_improvement=True, replacement_cost=50000, evo_base_cost=None, final_attributes_known=False)
    assert result["decision"] == "BUY REPLACEMENT"


def test_known_evo_improvement_can_win():
    result = decide_evo(slot_protected=False, slot_rerollable=False, projected_improvement=True, replacement_improvement=False, replacement_cost=None, evo_base_cost=10000, final_attributes_known=True)
    assert result["decision"] == "USE EVO"
