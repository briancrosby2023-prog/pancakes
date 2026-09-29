# Operation Pancake — Project-Wide Working Protocol

## Authority

`docs/OPERATION_PANCAKE_CONTROL_STATE.json` is the sole project-wide decision authority.

Mission-specific checkpoint files are subordinate evidence. They may describe a component, release, or acceptance run, but they may not redefine the active Operation Pancake mission, reopen accepted work, or silently replace project-wide decisions.

## Mandatory SOP

MAP → HISTORY → RESEARCH → CAPABILITIES → PLAN → EXECUTE → ADAPT → VERIFY → UPDATE MAP → CONTINUE

No consequential plan or execution begins before MAP, HISTORY, RESEARCH, and CAPABILITIES are evidence-backed in the authoritative control state.

## Session start

Before consequential Operation Pancake work:

1. Read `docs/OPERATION_PANCAKE_CONTROL_STATE.json`.
2. Run or reproduce the equivalent of:
   `python scripts/pancake_control.py preflight`
3. Confirm the active mission, current next action, accepted locks, rejected locks, available capabilities, and unresolved conflicts.
4. Do not choose a direction from the latest chat message alone.
5. If the control state is stale or contradictory, update/reconcile the authority before planning.

## Decision boundary

A consequential direction change requires a decision record with:

- active mission ID;
- relevant history references;
- capabilities actually checked;
- alternatives considered;
- selected action and reason;
- obstacle classification;
- whether the mission changes;
- lock IDs being reopened, if any;
- materially new evidence for every reopened accepted/rejected lock.

A tool failure is not permission to change the mission.

## Obstacle classification

Every material problem is one of:

- `MISSION_PROBLEM`
- `IMPLEMENTATION_PROBLEM`
- `CAPABILITY_PROBLEM`
- `EXTERNAL_DEPENDENCY`
- `EVIDENCE_GAP`

Use `NONE` when no obstacle is active.

A browser failure, repository outage, or missing shell is normally a capability problem. The response is ADAPT: check history, inventory alternatives, and continue the same mission when another legitimate route exists.

## Accepted and rejected locks

Accepted work and rejected/superseded approaches are listed in the authority.

They may be reopened only when the current decision names the lock ID and records materially new evidence. A new chat, different model, failed tool, or inconvenience is not new evidence.

## BLOCKED rule

`BLOCKED` is valid only when:

- the dependency is genuinely external;
- relevant capabilities were actually checked;
- legitimate adaptations were attempted;
- no executable routes remain;
- the one user/external action required is stated precisely.

“Opera failed” or “a test failed” is not a valid blocked state when another executable route remains.

## Completion rule

A test, commit, CI run, PR, package, screenshot, browser tab, report, or successful checkpoint is not completion by itself.

`COMPLETE` requires:

- every mission acceptance criterion passed;
- the user-facing objective verified;
- no remaining executable work;
- a terminal next action.

## Contradictory evidence

Contradictory current/historical evidence must be recorded and resolved before planning. Do not silently choose the newest fact or the most convenient interpretation.

## Handoffs and new chats

The handoff is generated from the authority:

`python scripts/pancake_control.py handoff`

The checked-in `docs/OPERATION_PANCAKE_HANDOFF.md` must match the generated output. A new session reads the authority first; the handoff is a convenience snapshot, not a competing source of truth.

## Git / coding-agent behavior

Repository/Codex work must read the authority before consequential edits. `AGENTS.md` repeats this bootstrap for coding environments. CI validates the project-wide state and regression suite.

## Interaction rule

Do not ask the user “what next?” while executable work remains. Ask only for a genuine external action, credential/MFA/CAPTCHA, spending authorization, contractual permission, or product decision that cannot be resolved from existing evidence.

## Failure handling

When something fails:

1. Record what actually failed.
2. Classify the failure.
3. Check HISTORY for a proven route.
4. Check CAPABILITIES for alternatives.
5. Research unknowns when necessary.
6. Adapt without replacing the mission.
7. Verify the adapted path.
8. Update the authority and continue.

