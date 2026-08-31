import json
from operation_pancake.team_import import (Candidate, OCRObservation, SlotRegion, TeamImportStore,
    classify_view, extract_structured, match_candidate, ownership_key, to_candidate)

def o(text,x,y,w=.08,h=.04,confidence=.9): return OCRObservation(text,(x,y,x+w,y+h),confidence)
def regions(*slots):
    return [SlotRegion(s,(i*.2,.2,i*.2+.18,.8)) for i,s in enumerate(slots)]

def test_view_classification_all_and_unknown():
    assert classify_view([o('OFFENSE',.1,.1),o('QB',.2,.2),o('WR',.3,.2)])[0]=='OFFENSE'
    assert classify_view([o('DEFENSE',.1,.1),o('CB',.2,.2),o('MIKE',.3,.2)])[0]=='DEFENSE'
    assert classify_view([o('SPECIAL TEAMS',.1,.1),o('KOS',.2,.2)])[0]=='SPECIAL TEAMS'
    assert classify_view([o('SPECIALISTS',.1,.1),o('SUBLB',.2,.2),o('RDT',.3,.2)])[0]=='SPECIALISTS'
    assert classify_view([o('TEAM MANAGER',.1,.1)])[0]=='UNKNOWN'

def test_spatial_slot_association_depth_name_and_ovr():
    rs=regions('WR1','WR2','WR3')
    obs=[o('OFFENSE',.01,.01),o('WR',.01,.3),o('85',.02,.4),o('Alpha',.02,.5,.05),o('Receiver',.075,.5,.08),
         o('WR',.21,.3),o('87',.22,.4),o('Beta',.22,.5,.05),o('Receiver',.275,.5,.08),o('WR',.41,.3),o('Gamma',.42,.5,.05),o('Receiver',.475,.5,.08)]
    view,found,meta=extract_structured('off.png',obs,{'OFFENSE':rs},view='OFFENSE')
    assert view=='OFFENSE' and meta['view_confidence']==1.0
    assert [(x.slot,x.raw_player_name,x.displayed_ovr) for x in found]==[('WR1','Alpha Receiver',85),('WR2','Beta Receiver',87),('WR3','Gamma Receiver',None)]
    assert [x.slot_index for x in found]==[1,2,3]

def test_cb_ss_and_specialist_labels_remain_distinct():
    dr=regions('CB1','CB2','CB3','SS1','SS2'); obs=[]
    for i,name in enumerate(['One','Two','Three','Four','Five']): obs.append(o(name,i*.2+.01,.4))
    _,found,_=extract_structured('d.png',obs,{'DEFENSE':dr},view='DEFENSE'); assert [x.slot for x in found]==['CB1','CB2','CB3','SS1','SS2']
    sr=regions('SUBLB1','SUBLB2','RDT1','RDT2'); _,spec,_=extract_structured('s.png',[o('One',.01,.4),o('Two',.21,.4),o('Three',.41,.4),o('Four',.61,.4)],{'SPECIALISTS':sr},view='SPECIALISTS'); assert [x.slot for x in spec]==['SUBLB1','SUBLB2','RDT1','RDT2']

def test_unread_slot_is_preserved_as_unresolved_not_invented():
    rs=regions('QB1','HB1'); _,found,_=extract_structured('x.png',[o('Partial',.01,.4,.07),o('Player',.085,.4,.07)],{'OFFENSE':rs},view='OFFENSE')
    assert len(found)==2; assert found[0].slot=='QB1' and found[0].raw_player_name=='Partial Player'; assert found[1].slot=='HB1' and found[1].raw_player_name is None and found[1].displayed_ovr is None; assert 'starter-name:unresolved' in found[1].provenance

def test_matching_exact_ambiguous_unmatched_and_observed_ovr_separate():
    cards=[{'card_id':'a','player_name':'Jaylen Lewis','position':'CB','native_overall':83},{'card_id':'b','player_name':'Version Guy','position':'WR','native_overall':85},{'card_id':'c','player_name':'Version Guy','position':'WR','native_overall':87}]
    jay=Candidate('1','DEFENSE','CB1','Jaylen Lewis',85,'CB',observed_ratings={'SPD':89,'ACC':88,'AGI':89,'COD':82,'MCV':91,'ZCV':91,'PRC':84}); assert match_candidate(jay,cards).canonical_card_id=='a'; assert cards[0]['native_overall']==83 and jay.displayed_ovr==85 and jay.observed_ratings['MCV']==91
    amb=match_candidate(Candidate('2','OFFENSE','WR1','Version Guy',None,'WR'),cards); assert amb.match_status=='AMBIGUOUS'
    exact=match_candidate(Candidate('3','OFFENSE','WR1','Version Guy',87,'WR'),cards); assert exact.match_status=='MATCHED' and exact.canonical_card_id=='c'
    weak=match_candidate(Candidate('4','OFFENSE','WR2','Not There'),cards); assert weak.match_status=='UNMATCHED'

def test_specialist_assignment_dedupes_owned_card():
    a=Candidate('a','DEFENSE','SS1','Player A',canonical_card_id='card-a',match_status='MATCHED'); b=Candidate('b','SPECIALISTS','SUBLB1','Player A',canonical_card_id='card-a',match_status='MATCHED'); assert ownership_key(a)==ownership_key(b)=='card-a'; assert a.slot != b.slot

def test_observed_to_candidate_preserves_structure():
    rs=regions('QB1'); _,found,_=extract_structured('o.png',[o('86',.01,.3),o('Quarter',.01,.4,.07),o('Back',.085,.4,.06)],{'OFFENSE':rs},view='OFFENSE'); c=to_candidate(found[0]); assert c.group=='OFFENSE' and c.slot=='QB1' and c.displayed_ovr==86 and c.bounding_region is not None

def test_v1_state_is_readable_and_saves_as_current_v3(tmp_path):
    p=tmp_path/'team.json'; p.write_text(json.dumps({'version':1,'screenshots':[],'candidates':[{'id':'x','group':'OFFENSE','slot':'QB1','player_name':'Old'}]})); s=TeamImportStore(p).load(); assert s.version==1 and s.candidates[0].player_name=='Old'; TeamImportStore(p).save(s); d=json.loads(p.read_text()); assert d['version']==3 and d['candidates'][0]['slot']=='QB1'
