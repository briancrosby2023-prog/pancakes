from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parents[1]
RUNNER = REPO / "scripts" / "pancake_local_control.py"


def load_runner():
    spec = importlib.util.spec_from_file_location("pancake_local_control_tested", RUNNER)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_control_blob_verifier_accepts_windows_crlf_and_rejects_tamper(tmp_path: Path):
    mod = load_runner()
    for rel in mod.CONTROL_BLOB_MANIFEST:
        src = REPO / rel
        dst = tmp_path / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        raw = src.read_bytes().replace(b"\r\n", b"\n")
        dst.write_bytes(raw.replace(b"\n", b"\r\n"))
    mod.verify_control_modules(tmp_path)
    victim = tmp_path / "src/operation_pancake/__init__.py"
    victim.write_bytes(victim.read_bytes() + b"# real tamper\r\n")
    with pytest.raises(mod.ControlError, match="hash mismatch"):
        mod.verify_control_modules(tmp_path)


def test_plan_oauth_responses_body_omits_unsupported_max_output_tokens(monkeypatch):
    mod = load_runner()
    captured = {}

    class FakeSession:
        def __init__(self, *args, **kwargs):
            pass

        def ensure(self):
            return {"access_token": "token"}

    def fake_stream(body, access_token, **kwargs):
        captured["body"] = body
        captured["token"] = access_token
        return {
            "proposed_plan": "fail closed",
            "allowed_actions": [],
            "blocked_actions": ["apply_bounded_patch"],
            "next_action": "none",
            "obstacle_classification": "EVIDENCE_GAP",
            "alternatives_considered": ["none"],
            "selected_reason": "diagnostic",
            "implementation_basis_fact_keys": [],
            "user_action_required": False,
            "remaining_executable_routes": [],
        }

    monkeypatch.setattr(mod, "OAuthSession", FakeSession)
    monkeypatch.setattr(mod, "available_models", lambda token, opener=None: [{"slug": "gpt-5.6-sol", "visibility": "list"}])
    monkeypatch.setattr(mod, "stream_response", fake_stream)
    provider = mod.ChatGPTPlanOAuthDecisionProvider()
    provider.decide("diagnostic", {
        "mission": "test",
        "evidence": {},
        "typed_evidence": [],
        "state_fingerprint": {"test": True},
        "mutation_requested": False,
        "instruction": "fail closed",
    })
    body = captured["body"]
    assert captured["token"] == "token"
    assert body["store"] is False
    assert body["stream"] is True
    assert "max_output_tokens" not in body
    assert body["text"]["format"]["type"] == "json_schema"


def test_control_request_rejects_arbitrary_command_field():
    mod = load_runner()
    payload = {
        "schema": mod.CONTROL_REQUEST_SCHEMA,
        "request_id": "red-command",
        "mission": "OP-CONTROL-002",
        "expected_repository": mod.EXPECTED_REPOSITORY,
        "expected_branch": mod.EXPECTED_BOOTSTRAP_BRANCH,
        "expected_head": "a" * 40,
        "expected_authority_revision": 7,
        "requested_action": "inspect_control_state",
        "request": "inspect only",
        "command": "cmd /c whoami",
    }
    with pytest.raises(mod.RequestRejected, match="unexpected control request fields: command"):
        mod.ControlRequest.parse(json.dumps(payload))


def test_terminal_receipt_blocks_replay(tmp_path: Path):
    mod = load_runner()
    journal = mod.ReceiptJournal(tmp_path)
    journal.write("replay-id", "COMPLETE", result={"ok": True})
    req = mod.ControlRequest(
        schema=mod.CONTROL_REQUEST_SCHEMA,
        request_id="replay-id",
        mission="OP-CONTROL-002",
        expected_repository=mod.EXPECTED_REPOSITORY,
        expected_branch=mod.EXPECTED_BOOTSTRAP_BRANCH,
        expected_head="a" * 40,
        expected_authority_revision=7,
        requested_action="inspect_control_state",
        request="inspect only",
    )
    state = {
        "mission": "OP-CONTROL-002",
        "branch": mod.EXPECTED_BOOTSTRAP_BRANCH,
        "head": "a" * 40,
        "authority_revision": 7,
    }
    with pytest.raises(mod.RequestRejected, match="replayed request_id"):
        mod.validate_control_request(req, state, journal, ["inspect_control_state"])


def test_installed_receipt_is_valid(tmp_path: Path):
    mod = load_runner()
    path = tmp_path / "receipt.json"
    path.write_text(json.dumps({
        "schema": mod.CONTROL_RECEIPT_SCHEMA,
        "request_id": "installer",
        "status": "INSTALLED",
    }), encoding="utf-8")
    assert mod.read_control_receipt(path)["status"] == "INSTALLED"


def test_checked_in_handoff_is_canonical():
    sys.path.insert(0, str(REPO / "src"))
    from operation_pancake.control_state import render_handoff
    state = json.loads((REPO / "docs/OPERATION_PANCAKE_CONTROL_STATE.json").read_text(encoding="utf-8"))
    actual = (REPO / "docs/OPERATION_PANCAKE_HANDOFF.md").read_text(encoding="utf-8")
    assert actual == render_handoff(state)


def test_expired_oauth_id_token_hint_is_omitted():
    mod = load_runner()

    def make_token(exp):
        header = mod.base64.urlsafe_b64encode(json.dumps({"alg": "RS256"}).encode()).rstrip(b"=").decode()
        payload = mod.base64.urlsafe_b64encode(json.dumps({"exp": exp}).encode()).rstrip(b"=").decode()
        return f"{header}.{payload}.AA"

    assert mod.oauth_id_token_hint_is_fresh(make_token(200), now=100)
    assert not mod.oauth_id_token_hint_is_fresh(make_token(120), now=100)
    assert not mod.oauth_id_token_hint_is_fresh("malformed", now=100)


def test_transient_oauth_refresh_failure_stays_fail_closed(monkeypatch, tmp_path: Path):
    mod = load_runner()
    store = mod.CredentialStore(
        tmp_path,
        protector=lambda data: data,
        unprotector=lambda data: data,
    )
    session = mod.OAuthSession(store)

    def fail_refresh(*args, **kwargs):
        raise mod.ControlError("HTTP 503 from token endpoint: service unavailable")

    monkeypatch.setattr(mod, "form_post", fail_refresh)
    with pytest.raises(mod.ControlError, match="transient ChatGPT OAuth refresh failure"):
        session._refresh({"refresh_token": "r", "client_id": "c"})


def test_rate_limit_delay_is_conservative():
    mod = load_runner()
    assert mod.rate_limit_delay(429, {"Retry-After": "30"}, now=100) >= mod.CONTROL_POLL_SECONDS
    assert mod.rate_limit_delay(403, {"X-RateLimit-Reset": "400"}, now=100) >= 305


def load_single_worktab_action():
    path = REPO / "scripts" / "pancake_single_worktab_action.py"
    spec = importlib.util.spec_from_file_location("pancake_single_worktab_action_tested", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_single_worktab_acceptance_is_registered_as_mutating_inbox_action():
    mod = load_runner()
    registry = mod.build_inbox_registry(REPO)
    assert mod.SINGLE_WORKTAB_ACCEPTANCE_ACTION in mod.INBOX_ACTIONS
    assert mod.SINGLE_WORKTAB_ACCEPTANCE_ACTION in mod.INBOX_MUTATING_ACTIONS
    assert mod.SINGLE_WORKTAB_ACCEPTANCE_ACTION in mod.DECISION_ACTION_TOKENS
    mutating, handler = registry[mod.SINGLE_WORKTAB_ACCEPTANCE_ACTION]
    assert mutating is True
    assert callable(handler)


def test_single_worktab_developer_toggle_selector_is_fail_closed_and_spatial():
    runner = load_runner()
    action = load_single_worktab_action()
    snapshot = {
        "Labels": [{"Name": "Developer mode", "X": 100, "Y": 50, "W": 110, "H": 24}],
        "Toggles": [
            {"Name": "", "AutomationId": "dev-toggle", "Enabled": True, "State": "Off", "X": 250, "Y": 50, "W": 36, "H": 22},
            {"Name": "", "AutomationId": "unrelated", "Enabled": True, "State": "On", "X": 250, "Y": 180, "W": 36, "H": 22},
        ],
    }
    chosen = action.select_developer_toggle(snapshot, runner)
    assert chosen["AutomationId"] == "dev-toggle"

    ambiguous = {
        "Labels": [{"Name": "Developer mode", "X": 100, "Y": 50, "W": 110, "H": 24}],
        "Toggles": [
            {"Name": "", "AutomationId": "a", "Enabled": True, "State": "Off", "X": 250, "Y": 48, "W": 36, "H": 22},
            {"Name": "", "AutomationId": "b", "Enabled": True, "State": "Off", "X": 255, "Y": 52, "W": 36, "H": 22},
        ],
    }
    with pytest.raises(runner.EvidenceGap, match="ambiguous"):
        action.select_developer_toggle(ambiguous, runner)

def test_single_worktab_runtime_loader_has_importlib_util_available():
    mod = load_runner()
    assert hasattr(mod.importlib, "util")
    assert callable(mod.importlib.util.spec_from_file_location)
    assert callable(mod.importlib.util.module_from_spec)

def test_single_worktab_action_revision_pin_matches_revision_26():
    action = load_single_worktab_action()
    assert action.EXPECTED_AUTHORITY_REVISION == 26

def test_single_worktab_launch_loader_resolves_sibling_server_import(tmp_path, monkeypatch):
    action = load_single_worktab_action()
    (tmp_path / "server.py").write_text("VALUE = 42\n", encoding="utf-8")
    (tmp_path / "launch.py").write_text("import server\nVALUE = server.VALUE\n", encoding="utf-8")
    monkeypatch.setattr(action, "APP", tmp_path)
    previous = sys.modules.pop("server", None)
    try:
        loaded = action.load_launch_module()
        assert loaded.VALUE == 42
    finally:
        sys.modules.pop("server", None)
        if previous is not None:
            sys.modules["server"] = previous

def test_single_worktab_extensions_root_uses_exact_installed_extensions_hyperlink():
    action = load_single_worktab_action()
    source = Path(action.__file__).read_text(encoding="utf-8")
    start = source.index("def open_extensions_root_and_snapshot")
    end = source.index("def select_developer_toggle", start)
    block = source[start:end]
    assert '"Installed extensions"' in block
    assert "ControlType]::Hyperlink" in block
    assert 'Name -eq "Back"' not in block


def test_single_worktab_r24_hardens_server_heartbeat_and_acceptance_boundary():
    action = load_single_worktab_action()
    source = Path(action.__file__).read_text(encoding="utf-8")
    assert action.EXPECTED_SERVER_PREPATCH_SHA256 == "bd2be6072354a91a37acc43a16783488abb700ac2784c10641cd4fb1b864dc37"
    assert action.EXPECTED_SERVER_SHA256 == "f073dfe2ca39a47076bf1c1663d6071a10cc5c7b5f6f2bab7cb003a5c5c615d2"
    assert "def patch_installed_server" in source
    assert "browser_helper_stale_heartbeat_ignored" in source
    assert "current.get(\"version\") == expected" in source
    assert "full_single_worktab_acceptance" in source
    assert "server cannot self-write" not in source  # implementation, not commentary-only authority prose


def test_single_worktab_r24_requires_real_saved_watch_cadence_before_acceptance():
    action = load_single_worktab_action()
    source = Path(action.__file__).read_text(encoding="utf-8")
    run_block = source[source.index("def run(repo: Path, control)"):]
    assert 'cadence_queue.get("status") != "WAITING"' in run_block
    assert "cadence_wait > 120.25" in run_block
    assert "cadence_delta < 120.0" in run_block
    assert "cadence_elapsed < 4.85" in run_block
    assert run_block.index("cadence_delta < 120.0") < run_block.index("write_full_acceptance(")
    assert run_block.index("write_full_acceptance(") < run_block.index("write_release_accepted(control)")


def test_single_worktab_r24_full_acceptance_is_transactional_and_restart_verified():
    action = load_single_worktab_action()
    source = Path(action.__file__).read_text(encoding="utf-8")
    run_block = source[source.index("def run(repo: Path, control)"):]
    assert "server_backup = server_path.read_bytes()" in run_block
    assert "acceptance_backup = acceptance_path.read_bytes()" in run_block
    assert "release_backup = release_path.read_bytes()" in run_block
    assert "write_server_bytes_in_place(server_path, server_backup, control)" in run_block
    assert "acceptance_path.write_bytes(acceptance_backup)" in run_block
    assert "release_path.write_bytes(release_backup)" in run_block
    assert 'health_final.get("release_status") != "PRODUCTION_ACCEPTED"' in run_block
    assert 'diagnostics_final.get("deployment_ready") is not True' in run_block
    assert 'acceptance_final.get("full_single_worktab_acceptance") is not True' in run_block


def test_single_worktab_r24_checks_stops_evaluator_and_five_fs_identity_gap():
    action = load_single_worktab_action()
    source = Path(action.__file__).read_text(encoding="utf-8")
    assert "def verify_installed_stop_conditions" in source
    assert "simple-evaluator:browser-work-stop" in source
    assert "market-timeout" in source
    assert "def evaluator_acceptance" in source
    assert "required_positions" in source
    for name in ("Jordan Allen", "Ashlynd Barker", "Kingston Lopa", "Earl Little Jr.", "Xavier Filsaime"):
        assert name in source
    assert "CURRENT_BROWSER_IDENTITIES_OBSERVED_PREVIOUSLY_BUT_NOT_YET_IMPORTED" in source

def test_single_worktab_r25_stops_server_before_atomic_patch_and_restarts_after():
    action = load_single_worktab_action()
    source = Path(action.__file__).read_text(encoding="utf-8")
    run_block = source[source.index("def run(repo: Path, control)"):]
    stop_call = "server_stopped_pid = stop_server(int(port), launch, control)"
    patch_call = "server_patch = patch_installed_server(control)"
    start_call = "port, _ = start_server(server_stopped_pid, launch, control)"
    assert stop_call in run_block
    assert patch_call in run_block
    assert start_call in run_block
    assert run_block.index(stop_call) < run_block.index(patch_call) < run_block.index(start_call)
    restart_block = source[source.index("def restart_server"):source.index("def write_release_accepted")]
    assert "old_pid = stop_server(port, launch, control)" in restart_block
    assert "return start_server(old_pid, launch, control)" in restart_block
    rollback = run_block[run_block.index("except Exception:"):]
    restore_stop = "rollback_pid = stop_server(int(current_port), launch, control)"
    assert restore_stop in rollback
    assert rollback.index(restore_stop) < rollback.index("write_server_bytes_in_place(server_path, server_backup, control)")

def test_single_worktab_r26_uses_verified_inplace_server_write_only_for_server_py():
    action = load_single_worktab_action()
    source = Path(action.__file__).read_text(encoding="utf-8")
    patch_start = source.index("def patch_installed_server")
    patch_end = source.index("def verify_installed_stop_conditions", patch_start)
    patch_block = source[patch_start:patch_end]
    assert "write_server_bytes_in_place(path, postimage, control)" in patch_block
    assert "os.replace(temp, path)" not in patch_block
    helper_start = source.index("def write_server_bytes_in_place")
    helper_block = source[helper_start:patch_start]
    assert 'path.open("wb")' in helper_block
    assert "handle.flush()" in helper_block
    assert "os.fsync(handle.fileno())" in helper_block
    assert "def process_exists" in source
    stop_start = source.index("def stop_server")
    stop_end = source.index("def start_server", stop_start)
    stop_block = source[stop_start:stop_end]
    assert "listener_gone and not process_exists(pid)" in stop_block
    # Controlled probes proved JSON atomic replacement works; retain it there.
    full_accept_start = source.index("def write_full_acceptance")
    release_start = source.index("def write_release_accepted")
    assert "os.replace(temp, path)" in source[full_accept_start:source.index("def find_controlled_edge", full_accept_start)]
    assert "os.replace(temp, path)" in source[release_start:source.index("def run(repo: Path, control)", release_start)]
