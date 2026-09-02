from pathlib import Path

from operation_pancake import ocr_team_app_visual
from operation_pancake.cfb27_ocr_match import candidate_pool_count, match_candidate_cfb27
from operation_pancake.production.gm import GMProduct
from operation_pancake.team_import import Candidate


def test_installed_production_runtime_loads_nonempty_cfb27_corpus_and_role_pools():
    gm = GMProduct(Path.cwd())
    assert len(gm.population) > 0
    roles = {
        "QB1": "QB",
        "WR1": "WR",
        "MIKE1": "MIKE",
        "K1": "K",
        "LS1": "LS",
        "3DRB1": "3DRB",
        "PWHB1": "PWHB",
        "SLWR1": "SLWR",
        "NT1": "NT",
        "SUBLB1": "SUBLB",
        "RRE1": "RRE",
        "RDT1": "RDT",
        "RLE1": "RLE",
        "SLCB1": "SLCB",
    }
    counts = {}
    for slot, position in roles.items():
        c = Candidate(slot, "SPECIALISTS", slot, None, None, position)
        counts[slot] = candidate_pool_count(c, gm.population)
    assert all(count > 0 for count in counts.values()), counts


def test_operation_pancake_app_patches_the_matcher_binding_used_by_active_extractor():
    ocr_team_app_visual.install_runtime()
    assert ocr_team_app_visual.patch6.patch5.match_candidate is match_candidate_cfb27


def test_unresolved_candidate_records_population_and_rejection_reason():
    cards = [
        {"card_id": "hb1", "player_name": "Rueben Owens II", "position": "HB", "native_overall": 86, "season": "CFB27"},
        {"card_id": "hb2", "player_name": "Jamaal Charles", "position": "HB", "native_overall": 87, "season": "CFB27"},
    ]
    c = Candidate("3drb", "SPECIALISTS", "3DRB1", None, None, "3DRB")
    out = match_candidate_cfb27(c, cards)
    assert out.match_status == "UNRESOLVED"
    assert "cfb27-candidate-count:2" in out.provenance
    assert "identity-rejection:no-name-observation" in out.provenance


def test_noisy_observation_reaches_cfb27_matcher_with_real_candidate_filtering():
    cards = [
        {"card_id": "wr1", "player_name": "Malachi Toney", "position": "WR", "native_overall": 89, "season": "CFB27"},
        {"card_id": "qb1", "player_name": "Malachi Toney", "position": "QB", "native_overall": 89, "season": "CFB27"},
    ]
    c = Candidate("slwr", "SPECIALISTS", "SLWR1", "Malachi T0NEY", 89, "SLWR")
    out = match_candidate_cfb27(c, cards)
    assert out.match_status == "MATCHED"
    assert out.canonical_card_id == "wr1"
    assert "cfb27-candidate-count:1" in out.provenance
    assert "identity-rejection:none" in out.provenance
