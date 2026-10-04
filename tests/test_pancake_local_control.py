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



def test_single_worktab_r32_uses_exact_edge_refresh_button_identity():
    action = load_single_worktab_action()
    source = Path(action.__file__).read_text(encoding="utf-8")
    start = source.index("def choose_work_tab_and_reload")
    end = source.index("def parse_dt", start)
    block = source[start:end]
    assert '$aid -eq "view_1003"' in block
    assert "'^(Refresh|Reload|Reload this page)$'" in block
    assert "$e.Current.IsOffscreen" in block
    assert "InvokePattern" in block
    assert "enabled visible Edge refresh/reload button view_1003" in block


def test_single_worktab_r31_prefers_exact_dev_switch_when_uia_duplicates_developer_mode_name():
    runner = load_runner()
    action = load_single_worktab_action()
    snapshot = {
        "Labels": [
            {"Name": "Developer mode", "AutomationId": "", "X": 117, "Y": 661, "W": 165, "H": 31},
            {"Name": "Developer mode", "AutomationId": "dev-switch", "X": 435, "Y": 660, "W": 59, "H": 33},
        ],
        "Toggles": [
            {"Name": "Developer mode", "AutomationId": "dev-switch", "Enabled": True, "State": "On", "X": 435, "Y": 660, "W": 59, "H": 33},
            {"Name": "Allow extensions from other stores.", "AutomationId": "other-store-switch", "Enabled": True, "State": "Off", "X": 435, "Y": 740, "W": 59, "H": 33},
        ],
    }
    chosen = action.select_developer_toggle(snapshot, runner)
    assert chosen["AutomationId"] == "dev-switch"
    assert chosen["Name"] == "Developer mode"
    assert chosen["Selection"] == "ExactDeveloperModeDevSwitch"
    assert chosen["State"] == "On"

    duplicate_exact = {
        "Labels": snapshot["Labels"],
        "Toggles": [
            snapshot["Toggles"][0],
            {**snapshot["Toggles"][0], "X": 500},
        ],
    }
    with pytest.raises(runner.EvidenceGap, match="exact dev-switch remains ambiguous"):
        action.select_developer_toggle(duplicate_exact, runner)


def test_single_worktab_runtime_loader_has_importlib_util_available():
    mod = load_runner()
    assert hasattr(mod.importlib, "util")
    assert callable(mod.importlib.util.spec_from_file_location)
    assert callable(mod.importlib.util.module_from_spec)

def test_single_worktab_action_revision_pin_matches_revision_33():
    action = load_single_worktab_action()
    assert action.EXPECTED_AUTHORITY_REVISION == 44

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
    repo = Path(action.__file__).resolve().parents[1]
    server = (repo / "runtime" / "simple_evaluator" / "server.py").read_text(encoding="utf-8")
    assert action.EXPECTED_SERVER_PREPATCH_SHA256 == "bd2be6072354a91a37acc43a16783488abb700ac2784c10641cd4fb1b864dc37"
    assert action.EXPECTED_SERVER_SHA256 == "60cdcbfde9b306d28d0732968622c8759150bb4a07e57bf68548b4e61f5dad76"
    assert "browser_helper_stale_heartbeat_ignored" in server
    assert 'current.get("version") == expected' in server
    assert "full_single_worktab_acceptance" in server
    assert "def patch_installed_runtime" in Path(action.__file__).read_text(encoding="utf-8")


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
    assert "runtime_backups = {str(path): path.read_bytes() for path in runtime_paths}" in run_block
    assert "acceptance_backup = acceptance_path.read_bytes()" in run_block
    assert "release_backup = runtime_backups[str(release_path)]" in run_block
    assert "for raw_path, backup in runtime_backups.items()" in run_block
    assert "write_runtime_bytes(target, backup, control)" in run_block
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
    patch_call = "runtime_patch = patch_installed_runtime(repo, control)"
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
    assert rollback.index(restore_stop) < rollback.index("for raw_path, backup in runtime_backups.items()")



def test_single_worktab_r26_uses_verified_inplace_server_write_only_for_server_py():
    action = load_single_worktab_action()
    source = Path(action.__file__).read_text(encoding="utf-8")
    server_start = source.index("def write_server_bytes_in_place")
    runtime_start = source.index("def write_runtime_bytes", server_start)
    patch_start = source.index("def patch_installed_runtime", runtime_start)
    helper_block = source[server_start:runtime_start]
    runtime_block = source[runtime_start:patch_start]
    patch_block = source[patch_start:source.index("def reload_helper_extension", patch_start)]
    assert 'path.open("wb")' in helper_block
    assert "handle.flush()" in helper_block
    assert "os.fsync(handle.fileno())" in helper_block
    assert 'if path.name == "server.py":' in runtime_block
    assert "return write_server_bytes_in_place(path, data, control)" in runtime_block
    assert "os.replace(temp, path)" in runtime_block
    assert "repository runtime Git blob drift" in patch_block
    assert "installed runtime preimage drift" in patch_block
    assert "def process_exists" in source
    stop_start = source.index("def stop_server")
    stop_end = source.index("def start_server", stop_start)
    stop_block = source[stop_start:stop_end]
    assert "listener_gone and not process_exists(pid)" in stop_block



def test_single_worktab_r27_self_recovers_missing_controlled_edge_then_uses_dev_mode_path():
    action = load_single_worktab_action()
    source = Path(action.__file__).read_text(encoding="utf-8")
    assert action.DEBUG_PORT == 9255
    assert action.EXTENSION_ID == "fgocmjlihbapenekkflcofdjmdodmboe"
    assert "def controlled_edge_rows" in source
    assert "[pscustomobject]@{{Rows=@($p)}}" in source
    launch_start = source.index("def launch_controlled_edge")
    launch_end = source.index("def navigate_selected_url", launch_start)
    launch_block = source[launch_start:launch_end]
    assert 'f"--remote-debugging-port={DEBUG_PORT}"' in launch_block
    assert '"--remote-allow-origins=*"' in launch_block
    assert 'f"--load-extension={HELPER_DIR}"' in launch_block
    assert '"--no-first-run"' in launch_block
    assert '"--new-window"' in launch_block
    assert "--user-data-dir" not in launch_block
    run_block = source[source.index("def run(repo: Path, control)"):]
    assert "find_controlled_edge(control, allow_absent=True)" in run_block
    assert "edge = launch_controlled_edge(queue, control)" in run_block
    assert 'f"edge://extensions/?id={EXTENSION_ID}"' in run_block
    assert run_block.index("edge = launch_controlled_edge(queue, control)") < run_block.index("open_extensions_root_and_snapshot(edge_pid, control)")
    assert run_block.index("toggle_exact(edge_pid, chosen, control)") < run_block.index("reload_helper_extension(edge_pid, control)")
    assert run_block.index("reload_helper_extension(edge_pid, control)") < run_block.index("navigate_selected_url(edge_pid, NORMAL_SEARCH_URL, control)")
    assert run_block.index("navigate_selected_url(edge_pid, NORMAL_SEARCH_URL, control)") < run_block.index("helper = wait_helper(int(port), control, seconds=30)")
    assert "Revision 19 proved that --load-extension alone is not sufficient." in run_block


def test_single_worktab_r28_waits_for_installed_extensions_readiness_and_preserves_dev_mode_on():
    action = load_single_worktab_action()
    source = Path(action.__file__).read_text(encoding="utf-8")
    assert action.EXTENSIONS_LINK_READY_TIMEOUT_SECONDS == 12
    assert action.EXTENSIONS_LINK_POLL_MS == 250
    start = source.index("def open_extensions_root_and_snapshot")
    end = source.index("def select_developer_toggle", start)
    block = source[start:end]
    assert "$deadline=(Get-Date).AddSeconds({EXTENSIONS_LINK_READY_TIMEOUT_SECONDS})" in block
    assert "if($links.Count -gt 1)" in block
    assert "Start-Sleep -Milliseconds {EXTENSIONS_LINK_POLL_MS}" in block
    assert "while((Get-Date) -lt $deadline)" in block
    assert "before readiness deadline" in block
    toggle_start = source.index("def toggle_exact")
    toggle_end = source.index("def wait_helper", toggle_start)
    toggle_block = source[toggle_start:toggle_end]
    assert '$action="AlreadyOn"' in toggle_block
    assert 'ToggleState]::Off' in toggle_block


def test_single_worktab_r30_uses_uia_omnibox_focus_and_exact_foreground_verification():
    action = load_single_worktab_action()
    source = Path(action.__file__).read_text(encoding="utf-8")
    start = source.index("def navigate_selected_url")
    end = source.index("def uia_snapshot", start)
    block = source[start:end]
    assert "ShowWindow" in block
    assert "GetForegroundWindow" in block
    assert "$p.MainWindowHandle" in block
    assert "SW_RESTORE" in block
    assert "$addr.SetFocus()" in block
    assert "HasKeyboardFocus" in block
    assert "Target Edge address bar did not acquire foreground keyboard focus" in block
    assert "Start-Sleep -Milliseconds 100" in block
    assert "SetForegroundWindow" not in block
    assert "AppActivate" not in block
    assert block.index("$addr.SetFocus()") < block.index("$vp.SetValue")



def test_single_worktab_r33_preserves_saved_watch_on_prices_fragment_only():
    action = load_single_worktab_action()
    repo = Path(action.__file__).resolve().parents[1]
    server = (repo / "runtime" / "simple_evaluator" / "server.py").read_text(encoding="utf-8")
    assert action.EXPECTED_AUTHORITY_REVISION == 44
    assert action.EXPECTED_SERVER_PREPATCH_SHA256 == "bd2be6072354a91a37acc43a16783488abb700ac2784c10641cd4fb1b864dc37"
    assert action.EXPECTED_SERVER_SHA256 == "60cdcbfde9b306d28d0732968622c8759150bb4a07e57bf68548b4e61f5dad76"
    assert 'BROWSER_WORK_TAB_FRAGMENT in str(page_url or "")' in server
    assert 'urlsplit(str(page_url or "")).fragment.lower() == "prices"' in server
    assert "same exact-card page" in server


def test_single_worktab_r35_uses_normal_rendered_search_for_all_browser_work():
    action = load_single_worktab_action()
    source = Path(action.__file__).read_text(encoding="utf-8")
    repo = Path(action.__file__).resolve().parents[1]
    bg = (repo / "runtime" / "simple_evaluator" / "browser-helper" / "background.js").read_text(encoding="utf-8")
    watch = (repo / "runtime" / "simple_evaluator" / "browser-helper" / "watch.js").read_text(encoding="utf-8")
    server = (repo / "runtime" / "simple_evaluator" / "server.py").read_text(encoding="utf-8")
    manifest = json.loads((repo / "runtime" / "simple_evaluator" / "browser-helper" / "manifest.json").read_text(encoding="utf-8"))
    assert action.EXPECTED_AUTHORITY_REVISION == 44
    assert action.EXPECTED_HELPER_VERSION == "1.4.16"
    assert action.NORMAL_SEARCH_URL == "https://cfb.fan/27/players/#simple-evaluator-worktab"
    run_block = source[source.index("def run(repo: Path, control)"):]
    assert "navigate_selected_url(edge_pid, first_source, control)" not in run_block
    assert "navigate_selected_url(edge_pid, NORMAL_SEARCH_URL, control)" in run_block
    assert "reload_helper_extension(edge_pid, control)" in run_block
    assert "patch_installed_runtime(repo, control)" in run_block
    assert "const NORMAL_SEARCH_URL = 'https://cfb.fan/27/players/#simple-evaluator-worktab';" in bg
    assert "currentBrowserWork" in bg
    assert "simple-evaluator:get-browser-work" in bg
    assert "return NORMAL_SEARCH_URL;" in bg
    assert "normal-search-submitted" in watch
    assert "normal-search-result-selected" in watch
    assert "#f_name" in watch
    assert "#f_overall__gte" in watch and "#f_overall__lte" in watch
    assert "normalizedCardUrl(link.href) === expected" in watch
    assert "history.replaceState" in watch
    assert 'BROWSER_NORMAL_SEARCH_URL = "https://cfb.fan/27/players/#simple-evaluator-worktab"' in server
    assert '"current_program": card.get("program"), "source_url": _browser_work_url(card.get("source", ""))' in server
    assert server.count('self.send_header("Location", BROWSER_NORMAL_SEARCH_URL)') == 2
    assert manifest["version"] == "1.4.16"


def test_single_worktab_r36_checks_old_runtime_before_install_and_new_runtime_after():
    action = load_single_worktab_action()
    source = Path(action.__file__).read_text(encoding="utf-8")
    assert action.EXPECTED_AUTHORITY_REVISION == 44
    start = source.index("def verify_installed_stop_conditions")
    end = source.index("def evaluator_acceptance", start)
    block = source[start:end]
    assert "prepatch: bool = False" in block
    assert "if not prepatch:" in block
    assert '"normal-search-submitted"' in block
    assert '"normal-search-result-selected"' in block
    assert '"#f_name"' in block
    run_block = source[source.index("def run(repo: Path, control)"):]
    pre = "prepatch_stop_checks = verify_installed_stop_conditions(control, prepatch=True)"
    patch = "runtime_patch = patch_installed_runtime(repo, control)"
    post = "stop_checks = verify_installed_stop_conditions(control, prepatch=False)"
    assert pre in run_block and patch in run_block and post in run_block
    assert run_block.index(pre) < run_block.index(patch) < run_block.index(post)
    assert '"prepatch_stop_condition_checks": prepatch_stop_checks' in run_block


def test_single_worktab_r37_uses_canonical_git_blob_runtime_postimages():
    action = load_single_worktab_action()
    source = Path(action.__file__).read_text(encoding="utf-8")
    assert action.EXPECTED_AUTHORITY_REVISION == 44
    start = source.index("def repository_runtime_postimage_bytes")
    end = source.index("def patch_installed_runtime", start)
    helper = source[start:end]
    assert '["git", "-C", str(repo), "show", f"HEAD:{git_path}"]' in helper
    assert 'stdout=subprocess.PIPE' in helper
    patch_start = source.index("def patch_installed_runtime")
    patch_end = source.index("def reload_helper_extension", patch_start)
    patch = source[patch_start:patch_end]
    assert "postimage = repository_runtime_postimage_bytes(repo, rel, control)" in patch
    assert "hashlib.sha256(postimage).hexdigest() != post_hash" in patch
    assert "write_runtime_bytes(target, postimage, control)" in patch
    assert "source.read_bytes()" not in patch
    assert "sha256(source)" not in patch


def test_single_worktab_r38_writes_helper_postimages_in_place_without_atomic_replace():
    action = load_single_worktab_action()
    source = Path(action.__file__).read_text(encoding="utf-8")
    assert action.EXPECTED_AUTHORITY_REVISION == 44
    start = source.index("def write_helper_bytes_in_place")
    end = source.index("def write_runtime_bytes", start)
    helper = source[start:end]
    assert 'path.open("r+b")' in helper
    assert "handle.seek(0)" in helper
    assert "handle.write(data)" in helper
    assert "handle.truncate()" in helper
    assert "handle.flush()" in helper
    assert "os.fsync(handle.fileno())" in helper
    runtime_start = source.index("def write_runtime_bytes")
    runtime_end = source.index("def repository_runtime_postimage_bytes", runtime_start)
    runtime = source[runtime_start:runtime_end]
    assert "if path.parent == HELPER_DIR:" in runtime
    assert "return write_helper_bytes_in_place(path, data, control)" in runtime
    assert 'temp = path.with_name(path.name + ".r38.tmp")' in runtime
    assert "os.replace(temp, path)" in runtime


def test_single_worktab_r40_uses_exact_extensions_root_reload_not_enable_toggle():
    action = load_single_worktab_action()
    source = Path(action.__file__).read_text(encoding="utf-8")
    assert action.EXPECTED_AUTHORITY_REVISION == 44
    start = source.index("def reload_helper_extension")
    end = source.index("def verify_installed_stop_conditions", start)
    block = source[start:end]
    assert "open_extensions_root_and_snapshot(edge_pid, control)" in block
    assert 'Name -ne "Reload"' in block
    assert 'ControlType]::ListItem' in block
    assert 'label.Contains("Simple Evaluator Browser Watch")' in block
    assert 'label.Contains("{EXTENSION_ID}")' in block
    assert "ScrollItemPattern" in block
    assert "InvokePattern" in block
    assert "ReloadCount" in block
    assert "TogglePattern" not in block
    assert ".Toggle()" not in block


def test_single_worktab_r41_uses_installed_extensions_route_before_exact_reload():
    action = load_single_worktab_action()
    source = Path(action.__file__).read_text(encoding="utf-8")
    assert action.EXPECTED_AUTHORITY_REVISION == 44
    start = source.index("def reload_helper_extension")
    end = source.index("def verify_installed_stop_conditions", start)
    block = source[start:end]
    assert "open_extensions_root_and_snapshot(edge_pid, control)" in block
    assert 'navigate_selected_url(edge_pid, "edge://extensions/", control)' not in block
    assert 'if($button.Current.Name -ne "Reload" -or -not $button.Current.IsEnabled)' in block
    assert 'label.Contains("Simple Evaluator Browser Watch")' in block
    assert 'label.Contains("{EXTENSION_ID}")' in block
    assert "ScrollIntoView()" in block
    assert "$invoke.Invoke()" in block


def test_single_worktab_r42_accepts_canonical_players_redirect_for_normal_search():
    action = load_single_worktab_action()
    repo = Path(action.__file__).resolve().parents[1]
    watch = (repo / "runtime" / "simple_evaluator" / "browser-helper" / "watch.js").read_text(encoding="utf-8")
    manifest = json.loads((repo / "runtime" / "simple_evaluator" / "browser-helper" / "manifest.json").read_text(encoding="utf-8"))
    release = json.loads((repo / "runtime" / "simple_evaluator" / "RELEASE.json").read_text(encoding="utf-8"))
    source = Path(action.__file__).read_text(encoding="utf-8")
    assert action.EXPECTED_AUTHORITY_REVISION == 44
    assert action.EXPECTED_HELPER_VERSION == "1.4.16"
    assert "return path === '/27/players/' || path === '/players/';" in watch
    assert "async function driveNormalSearch(work)" in watch
    assert "normal-search-submitted" in watch
    assert "normal-search-result-selected" in watch
    assert manifest["version"] == "1.4.16"
    assert release["browser_helper_version"] == "1.4.16"
    assert action.NORMAL_SEARCH_URL == "https://cfb.fan/27/players/#simple-evaluator-worktab"
    assert "navigate_selected_url(edge_pid, NORMAL_SEARCH_URL, control)" in source
