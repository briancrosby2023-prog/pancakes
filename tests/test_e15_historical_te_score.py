from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "scripts" / "e15_historical_te_score.py"
spec = spec_from_file_location("e15_score", SCRIPT)
mod = module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(mod)


def test_historical_archetype_aliases_are_explicit():
    assert mod.ALIASES["Possession"] == "Gritty Possession"
    assert mod.ALIASES["Blocking"] == "Pure Blocker"


def test_prr_regression_matches_frozen_toby_payne_control():
    attrs = {
        "SPD":80,"ACC":81,"AGI":74,"AWR":85,"STR":73,"JMP":78,
        "CTH":85,"CIT":84,"SRR":85,"MRR":85,"DRR":75,"SPC":82,"RLS":74,
        "BCV":60,"BTK":80,"TRK":79,"SFA":75,"RBK":74,"RBF":66,"RBP":76,
        "PBK":72,"PBF":66,"PBP":64,"LBK":48,"IBL":65,
    }
    row={"season":27,"url":"control","name":"Toby Payne","ovr":83,
         "position":"TE","archetype":"Physical Route Runner","attributes":attrs}
    scored=mod.score(row)
    assert scored["model"] == "TE-MODEL-003 v1.1"
    assert abs(scored["weighted_score"] - 79.45052653061225) < 1e-12


def test_vertical_v13_regression_matches_frozen_brahmer_control():
    attrs = {
        "SPD":80,"ACC":79,"AGI":71,"AWR":83,"JMP":81,"CTH":84,"CIT":82,
        "SRR":81,"MRR":82,"DRR":81,"SPC":84,"RLS":80,"BCV":73,"BTK":70,
        "TRK":71,"SFA":84,"RBK":77,"RBF":82,"RBP":73,"PBK":59,"PBF":66,
        "PBP":73,"LBK":78,"IBL":76,
    }
    row={"season":27,"url":"control","name":"Benjamin Brahmer","ovr":84,
         "position":"TE","archetype":"Vertical Threat","attributes":attrs}
    scored=mod.score(row)
    assert scored["model"] == "TE-MODEL-006 v1.3"
    assert abs(scored["weighted_score"] - 79.46601941747574) < 1e-12


def test_pairwise_metrics_count_inversion_and_tie():
    rows=[
        {"name":"A","url":"a","ovr":82,"weighted_score":80.0,"scoring_eligible":True},
        {"name":"B","url":"b","ovr":81,"weighted_score":81.0,"scoring_eligible":True},
        {"name":"C","url":"c","ovr":80,"weighted_score":80.0,"scoring_eligible":True},
    ]
    m=mod.metrics(rows)
    assert (m["correct_rankings"],m["inversions"],m["ties"]) == (1,1,1)
