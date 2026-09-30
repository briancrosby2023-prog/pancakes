import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "verify_sop_gate.py"


def run_gate(tmp_path, state, *args):
    state_path = tmp_path / "sop_state.json"
    state_path.write_text(json.dumps(state), encoding="utf-8")
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--state", str(state_path), *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def stage(complete=True, evidence=None):
    return {"complete": complete, "evidence": evidence or ["evidence"]}


def evidence_ref(kind="file", ref="docs/SOP_STATE.json"):
    return [{"kind": kind, "ref": ref}]


def valid_state():
    return {
        "mission": "SOP gate acceptance",
        "status": "IN_PROGRESS",
        "map": stage(),
        "history": stage(),
        "research": stage(),
        "capabilities": stage(),
        "plan": {"complete": True, "evidence": ["approved design"], "next_action": "execute"},
        "execute": stage(),
        "adapt": stage(),
        "verify": stage(),
        "update_map": stage(),
        "continue": {"complete": True, "evidence": ["next action evaluated"]},
        "next_action": "continue project work",
    }


def valid_decision_state():
    state = valid_state()
    state["map"] = stage(evidence=evidence_ref("state", "docs/SOP_STATE.json#sha256:abc"))
    state["history"] = stage(evidence=evidence_ref("history", "decision:prior-001"))
    state["research"] = stage(evidence=evidence_ref("source", "https://example.invalid/source"))
    state["capabilities"] = stage(evidence=evidence_ref("runtime", "capability-snapshot:001"))
    state["plan"] = {
        "complete": True,
        "evidence": evidence_ref("plan", "plan:001"),
        "next_action": "decision",
    }
    return state


def test_valid_state_passes(tmp_path):
    result = run_gate(tmp_path, valid_state(), "--action", "commit")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "SOP GATE: PASS" in result.stdout


def test_missing_history_fails(tmp_path):
    state = valid_state()
    state["history"] = stage(False)
    result = run_gate(tmp_path, state, "--action", "plan")
    assert result.returncode != 0
    assert "HISTORY" in result.stdout


def test_missing_research_evidence_fails_blocked_state(tmp_path):
    state = valid_state()
    state["status"] = "BLOCKED"
    state["research"] = {"complete": True, "evidence": []}
    result = run_gate(tmp_path, state, "--action", "blocked")
    assert result.returncode != 0
    assert "RESEARCH" in result.stdout
    assert "evidence" in result.stdout.lower()


def test_package_requires_verify(tmp_path):
    state = valid_state()
    state["verify"] = stage(False)
    result = run_gate(tmp_path, state, "--action", "package")
    assert result.returncode != 0
    assert "VERIFY" in result.stdout


def test_complete_mission_cannot_have_executable_next_action(tmp_path):
    state = valid_state()
    state["status"] = "COMPLETE"
    state["next_action"] = "run importer"
    result = run_gate(tmp_path, state, "--action", "complete")
    assert result.returncode != 0
    assert "next_action" in result.stdout


def test_decision_requires_map_history_research_capabilities_and_plan(tmp_path):
    valid = run_gate(tmp_path, valid_decision_state(), "--action", "decision")
    assert valid.returncode == 0, valid.stdout + valid.stderr

    for stage_name in ("map", "history", "research", "capabilities", "plan"):
        state = valid_decision_state()
        state[stage_name]["complete"] = False
        result = run_gate(tmp_path, state, "--action", "decision")
        assert result.returncode != 0
        assert stage_name.upper() in result.stdout


def test_decision_rejects_empty_history_evidence(tmp_path):
    state = valid_decision_state()
    state["history"] = {"complete": True, "evidence": []}
    result = run_gate(tmp_path, state, "--action", "decision")
    assert result.returncode != 0
    assert "HISTORY" in result.stdout
    assert "evidence" in result.stdout.lower()


def test_decision_rejects_synthetic_evidence_without_reference(tmp_path):
    state = valid_decision_state()
    state["history"] = {"complete": True, "evidence": ["history checked"]}
    result = run_gate(tmp_path, state, "--action", "decision")
    assert result.returncode != 0
    assert "HISTORY" in result.stdout
    assert "reference" in result.stdout.lower() or "evidence" in result.stdout.lower()


def test_model_stage_waiver_cannot_satisfy_required_stage(tmp_path):
    state = valid_decision_state()
    state["history"] = {
        "complete": True,
        "evidence": [{"kind": "model-waiver", "ref": "model said history was unnecessary"}],
    }
    result = run_gate(tmp_path, state, "--action", "decision")
    assert result.returncode != 0
    assert "HISTORY" in result.stdout
