from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "scripts" / "e15_historical_te_population_validation.py"
spec = spec_from_file_location("e15_hist", SCRIPT)
mod = module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(mod)


def test_parse_player_recovers_archetype_and_attributes():
    html = """
    <html><body><h1>D ecker DeGraaf 84 OVR</h1>
    <div>TE Standouts Archetype Gritty Possession - TE</div>
    <div>SPD 82 ACC 83 AWR 80 CTH 84 CIT 84 SRR 83 MRR 74
    IBL 80 LBK 75 RBK 81 RBF 80 RBP 79 PBK 70 PBF 69 PBP 68</div>
    </body></html>
    """
    row = mod.parse_player(html, "https://cfb.fan/example", 26)
    assert row is not None
    assert row["name"] == "Decker DeGraaf"
    assert row["archetype"] == "Gritty Possession"
    assert row["attributes"]["SPD"] == 82
    assert row["season"] == 26


def test_vertical_v13_score_is_frozen_and_deterministic():
    attrs = {k: 80 for k in mod.WEIGHTS["vertical"]}
    attrs.update({"LBK": 80, "IBL": 80})
    row = {"season": 26, "url": "u", "name": "n", "ovr": 80,
           "position": "TE", "archetype": "Vertical Threat", "attributes": attrs}
    scored = mod.score_record(row)
    assert scored["model"] == "TE-MODEL-006 v1.3"
    assert scored["weighted_score"] == 80
    assert "ELU" not in scored["attributes_used"]
    assert "LBK" in scored["attributes_used"]
    assert "IBL" in scored["attributes_used"]


def test_pairwise_inversion_and_tie_accounting():
    rows = [
        {"name": "A", "url": "a", "ovr": 82, "weighted_score": 80.0, "scoring_eligible": True},
        {"name": "B", "url": "b", "ovr": 81, "weighted_score": 81.0, "scoring_eligible": True},
        {"name": "C", "url": "c", "ovr": 80, "weighted_score": 80.0, "scoring_eligible": True},
    ]
    result = mod.analyze_group(rows)
    assert result["comparable_distinct_ovr_pairs"] == 3
    assert result["correct_rankings"] == 1
    assert result["inversions"] == 1
    assert result["ties"] == 1
    assert len(result["inversion_records"]) == 1


def test_physical_route_runner_uses_frozen_71_29_blend():
    attrs = {k: 75 for k in set(mod.WEIGHTS["vertical"]) | set(mod.WEIGHTS["possession"])}
    attrs.update({"LBK": 75, "IBL": 75})
    row = {"season": 25, "url": "u", "name": "n", "ovr": 75,
           "position": "TE", "archetype": "Physical Route Runner", "attributes": attrs}
    scored = mod.score_record(row)
    assert scored["model"] == "TE-MODEL-003 v1.1"
    assert scored["weighted_score"] == 75
