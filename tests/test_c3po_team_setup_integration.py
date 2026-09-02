from pathlib import Path

from operation_pancake.c3po_team_setup import integrate_offense_tackles
from operation_pancake.c3po_vision import PlayerObservation, TackleScreenObservation, TackleSlotObservation
from operation_pancake.team_import import Candidate, TeamImportState

class Store:
    def __init__(self, state): self.state = state
    def load(self): return self.state
    def save(self, state): self.state = state
class Translator:
    def __init__(self, observation=None, error=None): self.observation, self.error = observation, error
    def translate_offense_tackles(self, screenshot):
        if self.error: raise self.error
        return self.observation

def obs(rt_name='Cason Henry', rt_ovr=85, rt_backups=(), lt_name=None, lt_ovr=None, lt_backups=()):
    return TackleScreenObservation('OFFENSE', {'LT1': TackleSlotObservation(PlayerObservation(lt_name, lt_ovr), tuple(lt_backups)), 'RT1': TackleSlotObservation(PlayerObservation(rt_name, rt_ovr), tuple(rt_backups))}, 'fake-gemini', 'fake-model')
def cards():
    return [
        {'game':'CFB27','position':'RT','player_name':'Cason Henry','native_overall':85,'program':'Phenoms','card_id':'cason-85'},
        {'game':'CFB27','position':'RT','player_name':'Juan Gaston','native_overall':80,'program':'Phenoms','card_id':'juan-80'},
        {'game':'CFB27','position':'LT','player_name':'Josh Petty','native_overall':80,'program':'Phenoms','card_id':'petty-80'},
        {'game':'CFB26','position':'RT','player_name':'Cason Henry','native_overall':99,'program':'Wrong Season','card_id':'old'},
        {'game':'CFB27','position':'LT','player_name':'Cason Henry','native_overall':97,'program':'Wrong Position','card_id':'wrong-pos'},
    ]
def state(tmp_path):
    image = tmp_path / 'opaque-upload.png'; image.write_bytes(b'pixels')
    return TeamImportState(screenshots=[{'id':'shot-o','path':str(image),'view':'OFFENSE'}], candidates=[Candidate('lt','OFFENSE','LT1',player_name='old-lt'), Candidate('rt','OFFENSE','RT1',player_name='old-rt'), Candidate('qb','OFFENSE','QB1',player_name='KEEP QB'), Candidate('cb','DEFENSE','CB1',player_name='KEEP CB')])

def test_c3po_team_setup_resolves_real_tackle_shapes_and_preserves_display_native(tmp_path):
    st = state(tmp_path); store = Store(st)
    translated = obs(rt_backups=(PlayerObservation('Juan Gaston',81),), lt_backups=(PlayerObservation('Josh Petty',80),))
    integrate_offense_tackles(store, cards(), Translator(translated))
    rt = next(c for c in st.candidates if c.slot == 'RT1')
    assert (rt.player_name, rt.displayed_ovr, rt.program, rt.canonical_card_id) == ('Cason Henry',85,'Phenoms','cason-85')
    assert rt.match_diagnostics['c3po']['native_card_ovr'] == 85
    assert rt.backups[0] == {'observed_player_name':'Juan Gaston','player_name':'Juan Gaston','displayed_ovr':81,'native_card_ovr':80,'program':'Phenoms','canonical_card_id':'juan-80','match_status':'MATCHED'}
    lt = next(c for c in st.candidates if c.slot == 'LT1')
    assert lt.backups[0]['player_name'] == 'Josh Petty' and lt.backups[0]['native_card_ovr'] == 80

def test_c3po_team_setup_isolates_position_and_cfb27(tmp_path):
    st = state(tmp_path); store = Store(st); integrate_offense_tackles(store, cards(), Translator(obs()))
    rt = next(c for c in st.candidates if c.slot == 'RT1'); assert rt.canonical_card_id == 'cason-85' and rt.program == 'Phenoms'
def test_c3po_team_setup_insufficient_identity_is_unresolved(tmp_path):
    st = state(tmp_path); store = Store(st); integrate_offense_tackles(store, cards(), Translator(obs(rt_name='X', rt_ovr=85)))
    rt = next(c for c in st.candidates if c.slot == 'RT1'); assert rt.match_status == 'UNMATCHED'; assert rt.player_name is None and rt.canonical_card_id is None; assert rt.match_diagnostics['c3po']['observed_player_name'] == 'X'
def test_c3po_team_setup_translator_failure_preserves_existing_state(tmp_path):
    st = state(tmp_path); before = [(c.id,c.player_name,c.canonical_card_id) for c in st.candidates]; store = Store(st); integrate_offense_tackles(store, cards(), Translator(error=RuntimeError('api down')))
    assert [(c.id,c.player_name,c.canonical_card_id) for c in st.candidates] == before; assert st.team_observations['c3po_tackles']['status'] == 'ERROR'
def test_c3po_team_setup_does_not_touch_non_tackles(tmp_path):
    st = state(tmp_path); store = Store(st); integrate_offense_tackles(store, cards(), Translator(obs()))
    assert next(c for c in st.candidates if c.slot == 'QB1').player_name == 'KEEP QB'; assert next(c for c in st.candidates if c.slot == 'CB1').player_name == 'KEEP CB'
