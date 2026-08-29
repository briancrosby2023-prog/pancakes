import json
from operation_pancake.roster_state import RosterAssignment,RosterStore
from operation_pancake.team_import import Candidate,TeamImportStore,match_candidate
from operation_pancake import team_app

def test_real_upload_surface_and_routes_present():
    import inspect
    src=inspect.getsource(team_app)
    assert 'type="file"' in src and 'multiple required' in src and 'multipart/form-data' in src
    assert '/team/upload' in src and '/team/confirm' in src
    assert 'DROP TEAM PICTURES HERE' in src

def test_image_bytes_are_persisted_and_multiple(tmp_path):
    s=TeamImportStore(tmp_path/'team.json'); rows=s.stage_bytes([('o.png','image/png',b'PNGDATA'),('d.jpg','image/jpeg',b'JPEGDATA')])
    assert len(rows)==2 and all((tmp_path/'team_uploads'/PathLike(r['path']).name).exists() for r in rows)
    assert [x['bytes'] for x in rows]==[7,8]

def PathLike(value):
    from pathlib import Path
    return Path(value)

def test_invalid_non_image_fails_safely(tmp_path):
    import pytest
    with pytest.raises(ValueError): TeamImportStore(tmp_path/'t.json').stage_bytes([('x.txt','text/plain',b'x')])

def test_partial_extraction_does_not_invent():
    c=Candidate('1','OFFENSE','QB'); assert match_candidate(c,[{'card_id':'x','player_name':'Somebody','position':'QB'}]).canonical_card_id is None

def test_exact_and_ambiguous_matching():
    cards=[{'card_id':'a','player_name':'Jay Doe','position':'SS','native_overall':85},{'card_id':'b','player_name':'Jay Doe','position':'SS','native_overall':86}]
    exact=match_candidate(Candidate('1','DEFENSE','SS1','Jay Doe',85,'SS'),cards); assert exact.match_status=='MATCHED' and exact.canonical_card_id=='a'
    amb=match_candidate(Candidate('2','DEFENSE','SS1','Jay Doe',position='SS'),cards); assert amb.match_status=='AMBIGUOUS' and amb.canonical_card_id is None

def test_observed_effective_state_distinct_and_restart_safe(tmp_path):
    p=tmp_path/'roster.json'; s=RosterStore(p,{'c1'}); s.add(RosterAssignment('c1','SS','SS1',observed_overall=85,observed_ratings={'SPD':89,'MCV':91},evidence=['shot-1']))
    r=RosterStore(p,{'c1'}).load()[0]; assert r.observed_overall==85 and r.observed_ratings['SPD']==89 and json.loads(p.read_text())['version']==2

def test_specialist_duplicate_is_assignment_not_owned_copy(tmp_path):
    s=RosterStore(tmp_path/'r.json',{'c1'}); s.add(RosterAssignment('c1','HB','HB1')); s.add(RosterAssignment('c1','HB','3DRB',assignment_kind='SPECIALIST'))
    assert len(s.load())==2 and len({x.card_id for x in s.load()})==1

def test_old_v1_and_v2_remain_loadable(tmp_path):
    p=tmp_path/'r.json'; p.write_text(json.dumps({'version':1,'assignments':[{'card_id':'c1','position':'FS','slot':'FS1'}]})); assert RosterStore(p,{'c1'}).load()[0].observed_ratings=={}
    p.write_text(json.dumps({'version':2,'assignments':[{'card_id':'c1','position':'FS','slot':'FS1','current_level':2}]})); assert RosterStore(p,{'c1'}).load()[0].current_level==2
