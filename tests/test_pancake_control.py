import copy
import json
from pathlib import Path

import pytest

from operation_pancake.control_state import (
    AUTHORITY_FILE,
    clone_with_decision,
    preflight_summary,
    render_handoff,
    validate_control_state,
)

ROOT = Path(__file__).resolve().parents[1]
STATE_PATH = ROOT / AUTHORITY_FILE


def load_state():
    return json.loads(STATE_PATH.read_text(encoding="utf-8"))


def test_authoritative_state_is_valid():
    state = load_state()
    assert validate_control_state(state) == []
    assert preflight_summary(state)["status"] == "PASS"


def test_missing_history_blocks_preflight():
    state = load_state()
    state["preflight"]["history"] = {"complete": False, "evidence": []}
    errors = validate_control_state(state)
    assert any("HISTORY" in error for error in errors)


def test_capability_failure_does_not_change_mission():
    state = clone_with_decision(
        load_state(),
        obstacle_classification="CAPABILITY_PROBLEM",
        proposed_action="Use another legitimate repository/browser route while preserving the mission.",
        changes_mission=False,
    )
    assert validate_control_state(state) == []
    assert state["current_decision"]["mission_id"] == state["active_mission"]["id"]


def test_silent_mission_drift_is_rejected():
    state = load_state()
    state["current_decision"]["mission_id"] = "OP-NEW-MISSION"
    errors = validate_control_state(state)
    assert any("may not silently replace the mission" in error for error in errors)


def test_rejected_lock_cannot_be_retried_without_new_evidence():
    state = load_state()
    state["current_decision"]["reopens_lock_ids"] = ["reject-hardcoded-8788"]
    state["current_decision"]["new_evidence_for_reopened_locks"] = {}
    errors = validate_control_state(state)
    assert any("reject-hardcoded-8788" in error and "new evidence" in error for error in errors)


def test_rejected_lock_can_be_reconsidered_with_material_new_evidence():
    state = load_state()
    state["current_decision"]["reopens_lock_ids"] = ["reject-hardcoded-8788"]
    state["current_decision"]["new_evidence_for_reopened_locks"] = {
        "reject-hardcoded-8788": ["A newly accepted runtime contract explicitly fixes the port and supersedes dynamic-port startup."]
    }
    assert validate_control_state(state) == []


def test_blocked_is_rejected_while_executable_routes_remain():
    state = load_state()
    state["status"] = "BLOCKED"
    state["blocker"] = {
        "type": "EXTERNAL_DEPENDENCY",
        "capabilities_checked": ["GitHub", "Files"],
        "adaptations_attempted": ["Tried alternate legitimate route"],
        "remaining_executable_routes": ["Use GitHub connector"],
        "user_action": "Enable required external permission",
    }
    errors = validate_control_state(state)
    assert any("executable routes remain" in error for error in errors)


def test_genuine_external_blocker_is_valid_after_routes_exhausted():
    state = load_state()
    state["status"] = "BLOCKED"
    state["blocker"] = {
        "type": "EXTERNAL_DEPENDENCY",
        "capabilities_checked": ["GitHub", "Files", "available browser connectors"],
        "adaptations_attempted": ["Completed all repository and cloud-side work"],
        "remaining_executable_routes": [],
        "user_action": "Perform the single physical action that cannot be executed by available tools.",
    }
    assert validate_control_state(state) == []


def test_checkpoint_cannot_be_called_complete_with_remaining_work():
    state = load_state()
    state["status"] = "COMPLETE"
    state["blocker"] = None
    state["active_mission"]["acceptance_criteria"][0]["passed"] = False
    state["completion"] = {
        "user_facing_objective_verified": True,
        "all_acceptance_criteria_passed": False,
        "remaining_executable_work": ["physical acceptance remains"],
    }
    state["active_mission"]["next_action"] = "complete"
    state["handoff"]["next_action"] = "complete"
    errors = validate_control_state(state)
    assert any("acceptance criterion" in error.lower() for error in errors)
    assert any("executable work remains" in error.lower() for error in errors)


def test_unresolved_conflict_blocks_planning_state():
    state = load_state()
    state["conflicts"].append({
        "id": "new-conflict",
        "status": "OPEN",
        "conflict": "Current evidence contradicts accepted history.",
        "resolution": "",
    })
    errors = validate_control_state(state)
    assert any("unresolved" in error.lower() for error in errors)


def test_handoff_must_match_authoritative_revision_and_next_action():
    state = load_state()
    state["handoff"]["state_revision"] = state["state_revision"] + 1
    state["handoff"]["next_action"] = "different action"
    errors = validate_control_state(state)
    assert any("handoff.state_revision" in error for error in errors)
    assert any("handoff.next_action" in error for error in errors)


def test_fresh_session_can_recover_required_state_from_authority_only():
    state = load_state()
    handoff = render_handoff(state)
    assert state["active_mission"]["id"] in handoff
    assert state["active_mission"]["objective"] in handoff
    assert state["active_mission"]["next_action"] in handoff
    assert "reject-hardcoded-8788" in handoff
    assert "reject-desktop-commander-retry" in handoff
    assert "MAP → HISTORY → RESEARCH → CAPABILITIES" in handoff


def test_completion_passes_only_when_every_criterion_and_work_item_is_done():
    state = load_state()
    for criterion in state["active_mission"]["acceptance_criteria"]:
        criterion["passed"] = True
    state["status"] = "COMPLETE"
    state["blocker"] = None
    state["active_mission"]["next_action"] = "complete"
    state["handoff"]["next_action"] = "complete"
    state["enforcement"]["behavioral_standard"]["project_instruction_installed"] = True
    state["enforcement"]["behavioral_standard"]["global_instruction_installed"] = True
    state["enforcement"]["mechanical_standard"]["regression_verified"] = True
    state["enforcement"]["cross_surface_acceptance_verified"] = True
    state["completion"] = {
        "user_facing_objective_verified": True,
        "all_acceptance_criteria_passed": True,
        "remaining_executable_work": [],
    }
    assert validate_control_state(state) == []


def test_complete_is_rejected_until_both_control_standards_are_verified():
    state = load_state()
    for criterion in state["active_mission"]["acceptance_criteria"]:
        criterion["passed"] = True
    state["status"] = "COMPLETE"
    state["blocker"] = None
    state["active_mission"]["next_action"] = "complete"
    state["handoff"]["next_action"] = "complete"
    state["enforcement"]["behavioral_standard"]["project_instruction_installed"] = False
    state["enforcement"]["behavioral_standard"]["global_instruction_installed"] = False
    state["enforcement"]["mechanical_standard"]["regression_verified"] = False
    state["enforcement"]["cross_surface_acceptance_verified"] = False
    state["completion"] = {
        "user_facing_objective_verified": True,
        "all_acceptance_criteria_passed": True,
        "remaining_executable_work": [],
    }
    errors = validate_control_state(state)
    assert any("project instruction installation" in error for error in errors)
    assert any("global instruction installation" in error for error in errors)
    assert any("mechanical enforcement regression" in error for error in errors)
    assert any("cross-surface acceptance" in error for error in errors)
