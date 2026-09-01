from operation_pancake.cfb27_ocr_match import match_candidate_cfb27
from operation_pancake.team_import import Candidate


def card(cid, name, position, ovr, season="CFB27"):
    return {"card_id": cid, "player_name": name, "position": position, "native_overall": ovr, "season": season}


def test_fuzzy_name_and_ovr_resolve_to_canonical_cfb27_identity():
    c = Candidate("x", "OFFENSE", "QB1", "Carson HINZMN", 87, "QB")
    out = match_candidate_cfb27(c, [card("27-qb", "Carson Hinzman", "QB", 87), card("other", "Carson Beck", "QB", 87)])
    assert out.match_status == "MATCHED"
    assert out.canonical_card_id == "27-qb"
    assert out.player_name == "Carson Hinzman"
    assert "identity-vocabulary:cfb27-only" in out.provenance


def test_historical_exact_name_is_never_allowed_into_candidate_universe():
    c = Candidate("x", "SPECIAL TEAMS", "K1", "Jason ELAM", 82, "K")
    out = match_candidate_cfb27(c, [card("26-k", "Jason Elam", "K", 82, "CFB26")])
    assert out.match_status == "UNRESOLVED"
    assert out.canonical_card_id is None
    assert out.player_name is None


def test_garbage_observation_is_not_renderable_as_player_identity():
    cards = [card("ls", "Alex Ward", "LS", 82), card("k", "Evan Johnson", "K", 84)]
    for slot, raw, pos in [("LS1", "SHRADER", "LS"), ("K1", "wost", "K"), ("KOS1", "Ex od", "KOS")]:
        out = match_candidate_cfb27(Candidate(slot, "SPECIAL TEAMS", slot, raw, None, pos), cards)
        assert out.match_status == "UNRESOLVED"
        assert out.player_name is None
        assert out.canonical_card_id is None


def test_position_filter_precedes_fuzzy_name_match():
    c = Candidate("x", "SPECIAL TEAMS", "K1", "Jason Elam", 82, "K")
    out = match_candidate_cfb27(c, [card("wrong", "Jason Elam", "QB", 82)])
    assert out.match_status == "UNRESOLVED"


def test_backup_is_matched_independently_and_fails_closed():
    c = Candidate("x", "OFFENSE", "WR1", "Malachi TONEY", 89, "WR", backups=[
        {"player_name": "Rashid Robinsn", "displayed_ovr": 84},
        {"player_name": "wost", "displayed_ovr": 80},
    ])
    cards = [card("starter", "Malachi Toney", "WR", 89), card("backup", "Rashid Robinson", "WR", 84)]
    out = match_candidate_cfb27(c, cards)
    assert out.canonical_card_id == "starter"
    assert out.backups[0]["canonical_card_id"] == "backup"
    assert out.backups[0]["player_name"] == "Rashid Robinson"
    assert out.backups[1]["match_status"] == "UNRESOLVED"
    assert out.backups[1]["player_name"] is None


def test_return_role_maps_only_to_eligible_native_cfb27_positions():
    c = Candidate("x", "SPECIAL TEAMS", "KR1", "Malachi TONEY", 89, "KR")
    out = match_candidate_cfb27(c, [card("wr", "Malachi Toney", "WR", 89), card("qb", "Malachi Toney", "QB", 89)])
    assert out.match_status == "MATCHED"
    assert out.canonical_card_id == "wr"
