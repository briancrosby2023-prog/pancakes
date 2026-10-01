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
