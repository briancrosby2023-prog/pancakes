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
