from pathlib import Path
import importlib.util,sys
ROOT=Path(__file__).resolve().parents[1]
ACTION=ROOT/'scripts/pancake_single_worktab_action.py'
def load():
 s=importlib.util.spec_from_file_location('r45a',ACTION);m=importlib.util.module_from_spec(s);sys.modules[s.name]=m;s.loader.exec_module(m);return m
def test_cadence_uses_current_exact_url():
 x=ACTION.read_text(encoding='utf-8'); assert 'cadence_prior_url = current_selected_url(edge_pid, control)' in x; assert 'edge_pid,\n            cadence_prior_url,\n            seconds=max(35.0, cadence_wait + 35.0),' in x
def test_baselines():
 m=load(); assert m.EXPECTED_AUTHORITY_REVISION==45; assert m.BASE_ALERTS_COUNT==1; assert m.BASE_STATE_OBS_HASH=='9ab55d9b1f8f794657160ad13be9e475eb3a285f062fc818058ef61b04ab0b43'
def test_appended_alert_allowed():
 m=load(); C=type('C',(),{'EvidenceGap':type('EvidenceGap',(Exception,),{})}); snap={'user_watch_count':2,'user_watches_hash':m.BASE_USER_WATCH_HASH,'watch_runtime_hash':m.BASE_RUNTIME_HASH,'state_observation_count':133,'feed_observation_count':100,'alerts_count':2,'alerts_prefix_hash':m.BASE_ALERTS_PREFIX_HASH,'value_probe_status':{'status':'RATE_LIMITED','persistent_lock':True},'value_probe_rate_limit':{'active':True}}; m.verify_protected(snap,C,allow_new_observations=True)
