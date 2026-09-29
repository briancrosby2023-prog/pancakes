"""Project-wide Operation Pancake decision-control state and validation."""
from __future__ import annotations

import copy
from collections.abc import Mapping, Sequence
from typing import Any

AUTHORITY_FILE = "docs/OPERATION_PANCAKE_CONTROL_STATE.json"
PROJECT_NAME = "Operation Pancake"
STATUS_VALUES = {"IN_PROGRESS", "BLOCKED", "COMPLETE"}
OBSTACLE_TYPES = {
    "NONE",
    "MISSION_PROBLEM",
    "IMPLEMENTATION_PROBLEM",
    "CAPABILITY_PROBLEM",
    "EXTERNAL_DEPENDENCY",
    "EVIDENCE_GAP",
}
PREFLIGHT_STAGES = ("map", "history", "research", "capabilities")
TERMINAL_NEXT_ACTIONS = {
    "",
    "none",
    "n/a",
    "complete",
    "completed",
    "await external input",
    "awaiting external input",
}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, Sequence) and not isinstance(value, (str, bytes)) else []


def _string_list(value: Any) -> list[str]:
    return [_text(item) for item in _list(value) if _text(item)]


def _require_mapping(value: Any, label: str, errors: list[str]) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        errors.append(f"{label} must be an object.")
        return {}
    return value


def _validate_stage(stage: Any, label: str, errors: list[str]) -> None:
    stage = _require_mapping(stage, label, errors)
    if not stage:
        return
    if stage.get("complete") is not True:
        errors.append(f"{label} must be complete before consequential planning/execution.")
    if not _string_list(stage.get("evidence")):
        errors.append(f"{label} requires evidence.")


def lock_index(state: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    result: dict[str, Mapping[str, Any]] = {}
    enforcement = _require_mapping(state.get("enforcement"), "enforcement", errors)
    if enforcement:
        behavioral = _require_mapping(
            enforcement.get("behavioral_standard"),
            "enforcement.behavioral_standard",
            errors,
        )
        mechanical = _require_mapping(
            enforcement.get("mechanical_standard"),
            "enforcement.mechanical_standard",
            errors,
        )
        if behavioral:
            for field in ("project_instruction_artifact", "global_instruction_artifact"):
                if not _text(behavioral.get(field)):
                    errors.append(f"enforcement.behavioral_standard.{field} is required.")
        if mechanical:
            for field in ("decision_gateway", "typed_evidence_module", "tool_broker"):
                if not _text(mechanical.get(field)):
                    errors.append(f"enforcement.mechanical_standard.{field} is required.")
        if enforcement.get("hard_limitations_acknowledged") is not True:
            errors.append("enforcement.hard_limitations_acknowledged must be true.")
        if not _text(enforcement.get("authorized_consequential_execution_route")):
            errors.append("enforcement.authorized_consequential_execution_route is required.")
        if not _text(enforcement.get("cross_surface_acceptance_file")):
            errors.append("enforcement.cross_surface_acceptance_file is required.")

    for field in ("accepted_locks", "rejected_locks"):
        for item in _list(state.get(field)):
            if isinstance(item, Mapping) and _text(item.get("id")):
                result[_text(item.get("id"))] = item
    return result


def validate_control_state(state: Mapping[str, Any]) -> list[str]:
    """Validate the sole project-wide Operation Pancake control state."""
    errors: list[str] = []
    if not isinstance(state, Mapping):
        return ["Control state root must be an object."]

    if state.get("schema_version") != 2:
        errors.append("schema_version must be 2.")
    if _text(state.get("project")) != PROJECT_NAME:
        errors.append(f"project must be {PROJECT_NAME!r}.")

    authority = _require_mapping(state.get("authority"), "authority", errors)
    if authority:
        if _text(authority.get("file")) != AUTHORITY_FILE:
            errors.append(f"authority.file must be {AUTHORITY_FILE}.")
        if authority.get("sole_project_wide_authority") is not True:
            errors.append("authority.sole_project_wide_authority must be true.")
        if not _string_list(authority.get("subordinate_state_files")):
            errors.append("authority.subordinate_state_files must identify mission-specific evidence files.")

    revision = state.get("state_revision")
    if not isinstance(revision, int) or revision < 1:
        errors.append("state_revision must be a positive integer.")

    status = _text(state.get("status")).upper()
    if status not in STATUS_VALUES:
        errors.append(f"status must be one of {sorted(STATUS_VALUES)}.")

    mission = _require_mapping(state.get("active_mission"), "active_mission", errors)
    mission_id = _text(mission.get("id")) if mission else ""
    if mission:
        if not mission_id:
            errors.append("active_mission.id is required.")
        if not _text(mission.get("objective")):
            errors.append("active_mission.objective is required.")
        criteria = _list(mission.get("acceptance_criteria"))
        if not criteria:
            errors.append("active_mission.acceptance_criteria must not be empty.")
        else:
            seen: set[str] = set()
            for idx, criterion in enumerate(criteria):
                label = f"active_mission.acceptance_criteria[{idx}]"
                criterion = _require_mapping(criterion, label, errors)
                if not criterion:
                    continue
                cid = _text(criterion.get("id"))
                if not cid:
                    errors.append(f"{label}.id is required.")
                elif cid in seen:
                    errors.append(f"Duplicate acceptance criterion id: {cid}.")
                seen.add(cid)
                if not _text(criterion.get("description")):
                    errors.append(f"{label}.description is required.")
                if not isinstance(criterion.get("passed"), bool):
                    errors.append(f"{label}.passed must be boolean.")

    preflight = _require_mapping(state.get("preflight"), "preflight", errors)
    if preflight:
        for stage_name in PREFLIGHT_STAGES:
            _validate_stage(preflight.get(stage_name), stage_name.upper(), errors)

    capabilities = _require_mapping(state.get("capabilities_snapshot"), "capabilities_snapshot", errors)
    if capabilities:
        if not _string_list(capabilities.get("checked")):
            errors.append("capabilities_snapshot.checked must record actually checked capabilities.")
        if not _string_list(capabilities.get("available")):
            errors.append("capabilities_snapshot.available must not be empty.")
        if not isinstance(capabilities.get("unavailable_or_excluded"), list):
            errors.append("capabilities_snapshot.unavailable_or_excluded must be an array.")

    for field in ("accepted_locks", "rejected_locks"):
        items = _list(state.get(field))
        seen: set[str] = set()
        for idx, item in enumerate(items):
            label = f"{field}[{idx}]"
            item = _require_mapping(item, label, errors)
            if not item:
                continue
            lid = _text(item.get("id"))
            if not lid:
                errors.append(f"{label}.id is required.")
            elif lid in seen:
                errors.append(f"Duplicate {field} id: {lid}.")
            seen.add(lid)
            if not _text(item.get("subject")):
                errors.append(f"{label}.subject is required.")
            if not _string_list(item.get("evidence")):
                errors.append(f"{label}.evidence is required.")
            policy_field = "reopen_policy" if field == "accepted_locks" else "retry_policy"
            if _text(item.get(policy_field)) != "NEW_EVIDENCE_REQUIRED":
                errors.append(f"{label}.{policy_field} must be NEW_EVIDENCE_REQUIRED.")

    conflicts = _list(state.get("conflicts"))
    for idx, conflict in enumerate(conflicts):
        label = f"conflicts[{idx}]"
        conflict = _require_mapping(conflict, label, errors)
        if not conflict:
            continue
        if _text(conflict.get("status")).upper() != "RESOLVED":
            errors.append(f"{label} is unresolved; contradictory evidence must be reconciled before planning.")
        if not _text(conflict.get("resolution")):
            errors.append(f"{label}.resolution is required.")

    decision = _require_mapping(state.get("current_decision"), "current_decision", errors)
    locks = lock_index(state)
    if decision:
        if _text(decision.get("mission_id")) != mission_id:
            errors.append("current_decision.mission_id must match active_mission.id; obstacles may not silently replace the mission.")
        if not _text(decision.get("decision_id")):
            errors.append("current_decision.decision_id is required.")
        if not _text(decision.get("proposed_action")):
            errors.append("current_decision.proposed_action is required.")
        obstacle = _text(decision.get("obstacle_classification")).upper() or "NONE"
        if obstacle not in OBSTACLE_TYPES:
            errors.append(f"current_decision.obstacle_classification must be one of {sorted(OBSTACLE_TYPES)}.")
        if not _string_list(decision.get("history_refs")):
            errors.append("current_decision.history_refs is required.")
        if not _string_list(decision.get("capabilities_checked")):
            errors.append("current_decision.capabilities_checked is required.")
        if not _string_list(decision.get("alternatives_considered")):
            errors.append("current_decision.alternatives_considered is required.")
        if not _text(decision.get("selected_reason")):
            errors.append("current_decision.selected_reason is required.")
        if decision.get("changes_mission") is True:
            if not _text(decision.get("mission_change_reason")):
                errors.append("Mission changes require an explicit mission_change_reason.")
            if not _string_list(decision.get("mission_change_evidence")):
                errors.append("Mission changes require mission_change_evidence.")
        reopened = _string_list(decision.get("reopens_lock_ids"))
        new_evidence = decision.get("new_evidence_for_reopened_locks")
        new_evidence = new_evidence if isinstance(new_evidence, Mapping) else {}
        for lid in reopened:
            if lid not in locks:
                errors.append(f"current_decision reopens unknown lock: {lid}.")
                continue
            if not _string_list(new_evidence.get(lid)):
                errors.append(f"Reopening lock {lid} requires materially new evidence.")

    journal = _list(state.get("decision_journal"))
    for idx, entry in enumerate(journal):
        label = f"decision_journal[{idx}]"
        entry = _require_mapping(entry, label, errors)
        if not entry:
            continue
        for field in ("decision_id", "decision", "evidence", "history", "alternatives", "result", "next"):
            if field in {"evidence", "history", "alternatives"}:
                if not _string_list(entry.get(field)):
                    errors.append(f"{label}.{field} is required.")
            elif not _text(entry.get(field)):
                errors.append(f"{label}.{field} is required.")

    blocker = state.get("blocker")
    if status == "BLOCKED":
        blocker = _require_mapping(blocker, "blocker", errors)
        if blocker:
            if _text(blocker.get("type")).upper() != "EXTERNAL_DEPENDENCY":
                errors.append("BLOCKED status is allowed only for a genuine EXTERNAL_DEPENDENCY.")
            if not _string_list(blocker.get("capabilities_checked")):
                errors.append("blocker.capabilities_checked is required.")
            if not _string_list(blocker.get("adaptations_attempted")):
                errors.append("blocker.adaptations_attempted is required.")
            if _string_list(blocker.get("remaining_executable_routes")):
                errors.append("BLOCKED status is invalid while executable routes remain.")
            if not _text(blocker.get("user_action")):
                errors.append("blocker.user_action must name the one precise external action required.")
    elif blocker not in (None, {}):
        errors.append("blocker must be null unless status is BLOCKED.")

    handoff = _require_mapping(state.get("handoff"), "handoff", errors)
    if handoff:
        if _text(handoff.get("mission_id")) != mission_id:
            errors.append("handoff.mission_id must match active_mission.id.")
        if handoff.get("state_revision") != revision:
            errors.append("handoff.state_revision must match state_revision.")
        mission_next = _text(mission.get("next_action")) if mission else ""
        if _text(handoff.get("next_action")) != mission_next:
            errors.append("handoff.next_action must match active_mission.next_action.")
        if AUTHORITY_FILE not in _string_list(handoff.get("must_read")):
            errors.append(f"handoff.must_read must include {AUTHORITY_FILE}.")
        if not _string_list(handoff.get("prohibited_restarts")):
            errors.append("handoff.prohibited_restarts must preserve rejected/superseded paths.")

    completion = _require_mapping(state.get("completion"), "completion", errors)
    if completion:
        remaining = _string_list(completion.get("remaining_executable_work"))
        verified = completion.get("user_facing_objective_verified") is True
        all_passed = False
        if mission:
            criteria = [c for c in _list(mission.get("acceptance_criteria")) if isinstance(c, Mapping)]
            all_passed = bool(criteria) and all(c.get("passed") is True for c in criteria)
        if completion.get("all_acceptance_criteria_passed") is not all_passed:
            errors.append("completion.all_acceptance_criteria_passed must match the acceptance criteria.")
        if status == "COMPLETE":
            enforcement = state.get("enforcement") if isinstance(state.get("enforcement"), Mapping) else {}
            behavioral = enforcement.get("behavioral_standard") if isinstance(enforcement.get("behavioral_standard"), Mapping) else {}
            mechanical = enforcement.get("mechanical_standard") if isinstance(enforcement.get("mechanical_standard"), Mapping) else {}
            if behavioral.get("project_instruction_installed") is not True:
                errors.append("COMPLETE requires project instruction installation.")
            if behavioral.get("global_instruction_installed") is not True:
                errors.append("COMPLETE requires global instruction installation.")
            if mechanical.get("regression_verified") is not True:
                errors.append("COMPLETE requires mechanical enforcement regression verification.")
            if enforcement.get("cross_surface_acceptance_verified") is not True:
                errors.append("COMPLETE requires cross-surface acceptance verification.")
            if remaining:
                errors.append("COMPLETE status is invalid while executable work remains.")
            if not verified:
                errors.append("COMPLETE requires user_facing_objective_verified=true.")
            if not all_passed:
                errors.append("COMPLETE requires every acceptance criterion to pass.")
            next_action = _text(mission.get("next_action")).lower() if mission else ""
            if next_action not in TERMINAL_NEXT_ACTIONS:
                errors.append("COMPLETE requires a terminal active_mission.next_action.")
        elif status == "IN_PROGRESS":
            next_action = _text(mission.get("next_action")).lower() if mission else ""
            if next_action in TERMINAL_NEXT_ACTIONS:
                errors.append("IN_PROGRESS requires an executable active_mission.next_action.")
    return list(dict.fromkeys(errors))


def preflight_summary(state: Mapping[str, Any]) -> dict[str, Any]:
    errors = validate_control_state(state)
    mission = state.get("active_mission") if isinstance(state.get("active_mission"), Mapping) else {}
    return {
        "status": "PASS" if not errors else "FAIL",
        "project": state.get("project"),
        "state_revision": state.get("state_revision"),
        "mission_id": mission.get("id"),
        "mission": mission.get("objective"),
        "next_action": mission.get("next_action"),
        "errors": errors,
    }


def render_handoff(state: Mapping[str, Any]) -> str:
    """Render deterministic handoff text from the authoritative control state."""
    errors = validate_control_state(state)
    if errors:
        raise ValueError("Cannot render handoff from invalid control state: " + "; ".join(errors))
    mission = state["active_mission"]
    preflight = state["preflight"]
    capabilities = state["capabilities_snapshot"]
    accepted = state.get("accepted_locks", [])
    rejected = state.get("rejected_locks", [])
    completion = state["completion"]

    lines = [
        "# Operation Pancake — Authoritative Handoff",
        "",
        f"State revision: {state['state_revision']}",
        f"Status: {state['status']}",
        f"Mission ID: {mission['id']}",
        "",
        "## Mission",
        mission["objective"],
        "",
        "## Mandatory SOP",
        "MAP → HISTORY → RESEARCH → CAPABILITIES → PLAN → EXECUTE → ADAPT → VERIFY → UPDATE MAP → CONTINUE",
        "",
        "## Start-of-session rule",
        f"Read `{AUTHORITY_FILE}` first and validate it before making a consequential Pancake decision.",
        "Do not let the newest obstacle replace the recorded mission.",
        "",
        "## Preflight evidence",
    ]
    for stage in PREFLIGHT_STAGES:
        lines.append(f"- {stage.upper()}: " + " | ".join(preflight[stage]["evidence"]))
    lines += ["", "## Available capabilities"]
    lines += [f"- {item}" for item in capabilities["available"]]
    lines += ["", "## Accepted — do not reopen without materially new evidence"]
    lines += [f"- {item['id']}: {item['subject']}" for item in accepted]
    lines += ["", "## Rejected/superseded — do not retry without materially new evidence"]
    lines += [f"- {item['id']}: {item['subject']}" for item in rejected]
    lines += [
        "",
        "## Next action",
        mission["next_action"],
        "",
        "## Remaining executable work",
    ]
    remaining = completion.get("remaining_executable_work", [])
    lines += [f"- {item}" for item in remaining] if remaining else ["- None"]
    lines += [
        "",
        "## Completion rule",
        "A commit, test, CI run, PR, package, screenshot, or progress report is only a checkpoint.",
        "Continue until the user-facing objective is verified, executable work is exhausted, or one genuine external action remains.",
        "",
    ]
    return "\n".join(lines)


def clone_with_decision(state: Mapping[str, Any], **decision_updates: Any) -> dict[str, Any]:
    """Test/helper utility: deep-copy state and update current_decision."""
    result = copy.deepcopy(dict(state))
    result.setdefault("current_decision", {}).update(decision_updates)
    return result
