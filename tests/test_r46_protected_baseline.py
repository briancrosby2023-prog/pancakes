from pathlib import Path
import importlib.util
import sys

ROOT=Path(__file__).resolve().parents[1]
ACTION=ROOT/"scripts/pancake_single_worktab_action.py"

def _module():
    spec=importlib.util.spec_from_file_location("r46_action_test",ACTION)
    mod=importlib.util.module_from_spec(spec)
    sys.modules[spec.name]=mod
    spec.loader.exec_module(mod)
    return mod

class Control:
    class EvidenceGap(RuntimeError):
        pass

def _snapshot(mod):
    return {
        "user_watch_count":2,
        "user_watches_hash":mod.BASE_USER_WATCH_HASH,
        "probe_watch_count":0,
        "state_observation_count":132,
        "state_observations_hash":"current",
        "feed_observation_count":100,
        "feed_observations_hash":"current-feed",
        "alerts_hash":"current-alerts",
        "alert_count":1,
        "alert_keys":["existing-alert"],
        "watch_runtime_hash":mod.BASE_RUNTIME_HASH,
        "value_probe_status":{"status":"RATE_LIMITED","persistent_lock":True},
        "value_probe_rate_limit":{"active":True},
    }

def test_current_legitimate_state_is_valid_starting_baseline():
    mod=_module(); before=_snapshot(mod)
    mod.verify_protected(before,Control,allow_new_observations=True)

def test_later_snapshot_may_add_observations_and_alerts_but_not_delete_baseline():
    mod=_module(); before=_snapshot(mod); later=dict(before)
    later["state_observation_count"]=135
    later["alert_count"]=2
    later["alert_keys"]=["existing-alert","new-alert"]
    mod.verify_protected(later,Control,allow_new_observations=True,baseline=before)

def test_later_snapshot_fails_if_preexisting_alert_disappears():
    mod=_module(); before=_snapshot(mod); later=dict(before)
    later["alert_keys"]=[]
    try:
        mod.verify_protected(later,Control,allow_new_observations=True,baseline=before)
    except Control.EvidenceGap:
        pass
    else:
        raise AssertionError("missing baseline alert must fail closed")

def test_run_uses_starting_snapshot_as_mid_restart_and_final_baseline():
    source=ACTION.read_text(encoding="utf-8")
    assert "verify_protected(before, control, allow_new_observations=True)" in source
    assert source.count("baseline=before") == 3
