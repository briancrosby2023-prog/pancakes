from pathlib import Path
import ast, json
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parents[1]
SERVER=ROOT/"runtime/simple_evaluator/server.py"
ACTION=ROOT/"scripts/pancake_single_worktab_action.py"

def _load_helper(tmp_path, *, platform_name="nt"):
    tree=ast.parse(SERVER.read_text(encoding="utf-8"))
    fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=="_write_browser_observation_state")
    state=tmp_path/"app-state.json"
    state.write_text(json.dumps({"old":True},indent=2)+"\n",encoding="utf-8")
    def deny_atomic(path,payload):
        raise PermissionError(5,"Access is denied")
    events=[]
    ns={
        "json":json,
        "os":SimpleNamespace(name=platform_name,fsync=lambda fd: None),
        "STATE":state,
        "backup_path":lambda p: p.with_name(p.name+".bak"),
        "write_json_atomic":deny_atomic,
        "record_event":lambda *a,**k: events.append((a,k)),
        "OPERATION_LOG":tmp_path/"events.jsonl",
        "RELEASE_ID":"3T",
        "RELEASE_VERSION":"1.2.0",
    }
    exec(compile(ast.Module(body=[fn],type_ignores=[]),str(SERVER),"exec"),ns)
    return ns[fn.name],state,events

def test_windows_permission_error_falls_back_in_place_and_verifies(tmp_path):
    func,state,events=_load_helper(tmp_path)
    preimage=state.read_bytes()
    payload={"schema":"simple-evaluator-server-state-v1","observations":[{"card_id":"x"}],"watches":[],"value_probe_status":{"status":"RATE_LIMITED","persistent_lock":True},"value_probe_rate_limit":{"active":True}}
    mode=func(payload)
    assert mode=="INPLACE_WINDOWS_SHARING_FALLBACK"
    assert json.loads(state.read_text(encoding="utf-8"))==payload
    assert state.with_name(state.name+".bak").read_bytes()==preimage
    assert events and events[0][0][1]=="browser_observation_state_inplace_fallback"

def test_non_windows_permission_error_stays_fail_closed(tmp_path):
    func,_,_=_load_helper(tmp_path,platform_name="posix")
    try:
        func({"x":1})
    except PermissionError:
        pass
    else:
        raise AssertionError("non-Windows PermissionError must propagate")

def test_browser_observation_uses_bounded_state_fallback():
    source=SERVER.read_text(encoding="utf-8")
    block=source[source.index("def record_browser_observation"):source.index("def _production_acceptance_candidate")]
    assert "state_write_mode = _write_browser_observation_state(state)" in block
    assert '"state_write_mode": state_write_mode' in block
    assert "write_json_atomic(STATE, state)" not in block

def test_acceptance_hides_all_powershell_children():
    source=ACTION.read_text(encoding="utf-8")
    assert 'WINDOWS_NO_WINDOW = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0' in source
    assert source.count("creationflags=WINDOWS_NO_WINDOW") >= 3
