from operation_pancake.ocr_team_app import REAL_TEAM_MANAGER_REGIONS, _VISUAL_LINEUP
from operation_pancake.team_import import OCRObservation, VIEW_SLOTS, classify_view, extract_structured


def o(text,x,y): return OCRObservation(text,(x-.003,y-.004,x+.003,y+.004),.96)


def test_four_views_classify_uniquely():
    cases={
      "OFFENSE":[o("OFFENSE",.5,.12),o("QB",.5,.3)],
      "DEFENSE":[o("DEFENSE",.5,.12),o("MIKE",.5,.3)],
      "SPECIAL TEAMS":[o("SPECIAL TEAMS",.5,.12),o("KOS",.5,.3)],
      "SPECIALISTS":[o("SPECIALISTS",.5,.12),o("SUBLB",.5,.3)],
    }
    got=[classify_view(v)[0] for v in cases.values()]
    assert got==list(cases)
    assert len(set(got))==4


def test_offense_instantiates_each_slot_once_and_isolates_noise_and_backups():
    obs=[o("OFFENSE",.5,.12),
      o("Samson",.302,.420),o("Okunlola",.326,.420),o("84",.350,.420),
      o("Josh",.304,.492),o("Petty",.326,.492),o("81",.349,.492),
      o("Luke",.410,.420),o("MONTGOMERY",.435,.420),o("OVR",.458,.420),o("87",.466,.420),
      o("Improvements",.12,.42),o("MENU",.15,.45),o("Neighbor",.50,.42)]
    view,found,_=extract_structured("real-offense.jpg",obs,REAL_TEAM_MANAGER_REGIONS,view="OFFENSE")
    assert view=="OFFENSE"
    assert [x.slot for x in found]==list(VIEW_SLOTS["OFFENSE"])
    assert len({x.slot for x in found})==len(found)==12
    by={x.slot:x for x in found}
    assert by["LT1"].raw_player_name=="Samson Okunlola"
    assert by["LT1"].displayed_ovr==84
    assert by["LT1"].backups==[{"player_name":"Josh Petty","displayed_ovr":81}]
    assert by["LG1"].raw_player_name=="Luke MONTGOMERY"
    assert "OVR" not in by["LG1"].raw_player_name
    assert all("Improvements" not in (x.raw_player_name or "") and "MENU" not in (x.raw_player_name or "") for x in found)


def test_malformed_slot_fails_closed():
    _,found,_=extract_structured("bad.jpg",[o("OFFENSE",.5,.12),o("OVR",.320,.420),o("?",.330,.420),o("84",.350,.420)],REAL_TEAM_MANAGER_REGIONS,view="OFFENSE")
    lt=next(x for x in found if x.slot=="LT1")
    assert lt.raw_player_name is None
    assert "starter-name:unresolved" in lt.provenance


def test_compact_ui_hides_debug_wall_by_default():
    assert "lineup-tabs" in _VISUAL_LINEUP
    assert "REVIEW" in _VISUAL_LINEUP
    assert "CANONICAL PANCAKE MATCH" not in _VISUAL_LINEUP
    assert "BACKUPS: none observed" not in _VISUAL_LINEUP
    assert "lineup-detail{display:none}" in _VISUAL_LINEUP
