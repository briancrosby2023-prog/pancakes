import importlib.util,json
from pathlib import Path
P=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('opx16',P/'scripts/op_x_016_historical_te_validation.py'); m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
S=json.loads((P/'data/research/op_x_016/frozen_te_scoring_spec.json').read_text())
def test_vertical_v13_visible_denominator_103():
 a={k:80 for k in S['madden19_weights']['Vertical Threat'] if k!='ELU'}; a.update(LBK=80,IBL=80); r=m.score({'archetype':'Vertical Threat','attributes':a,'ovr':80},S); assert r['weight_denominator']==103; assert r['frozen_score']==80
def test_pure_blocker_is_nonproduction_control(): assert S['models']['Pure Blocker']['production'] is False
def test_physical_route_runner_is_frozen_blend():
 a={k:75 for family in S['madden19_weights'].values() for k in family}; r=m.score({'archetype':'Physical Route Runner','attributes':a,'ovr':75},S); assert r['frozen_model']=='TE-MODEL-003 v1.1'; assert r['frozen_score']==75
