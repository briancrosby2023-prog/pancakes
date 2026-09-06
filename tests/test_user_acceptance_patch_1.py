import json
from operation_pancake.onboarding import SetupStore, ScreenshotStageStore
from operation_pancake.product_app import page
from operation_pancake.roster_state import RosterAssignment, RosterStore


def test_first_run_setup_state(tmp_path):
    store=SetupStore(tmp_path/'setup.json')
    assert not store.load().completed
    assert store.complete().completed
    assert SetupStore(tmp_path/'setup.json').load().completed


def test_screenshot_staging_is_review_only_and_multiple(tmp_path):
    store=ScreenshotStageStore(tmp_path/'screenshots.json')
    rows=store.stage(['offense.png','defense.png'])
    assert len(rows)==2
    assert all(x.status=='AWAITING REVIEW' for x in rows)
    assert all(x.extraction_status=='NOT AVAILABLE' for x in rows)


def test_roster_v1_load_is_backward_compatible(tmp_path):
    path=tmp_path/'roster.json'
    path.write_text(json.dumps({'version':1,'assignments':[{'card_id':'c1','position':'FS','slot':'FS1','rerollable':True}]}))
    row=RosterStore(path,{'c1'}).load()[0]
    assert row.rerollable and row.current_level is None


def test_rerollable_current_level_persists(tmp_path):
    path=tmp_path/'roster.json'; store=RosterStore(path,{'c1'})
    store.add(RosterAssignment('c1','FS','FS1',rerollable=True,current_level=7))
    row=RosterStore(path,{'c1'}).load()[0]
    assert row.current_level==7
    assert json.loads(path.read_text())['version']==2


def test_dark_product_navigation():
    rendered=page('x','<h1>x</h1>').decode()
    assert '#071019' in rendered
    assert 'GM Home' in rendered and 'Players & Value' in rendered and 'Team Setup' in rendered


def test_acceptance_routes_and_unknown_contract_are_present():
    import inspect
    from operation_pancake import product_app
    src=inspect.getsource(product_app)
    for route in ('/setup','/players','/roster','/compare','/evo','/gm','/replacements'):
        assert route in src
    assert 'Automatic screenshot extraction is NOT AVAILABLE' in src
    assert 'PRICE UNKNOWN' in src
    assert 'Owned EVO candidates' in src and 'Acquisition EVO candidates' in src
    assert 'Current EVO' in src
