# Operation Pancake SOP Decision Controller — Design

Date: 2026-09-28
Status: Design for review

## Purpose

Operation Pancake needs mechanical enforcement of its SOP at the **decision boundary**, not merely as prose instructions and not only at the GitHub merge boundary.

The governing SOP remains:

`MAP → HISTORY → RESEARCH → CAPABILITIES → PLAN → EXECUTE → ADAPT → VERIFY → UPDATE MAP → CONTINUE`

The controller must make it impossible for a consequential Pancake decision to become authoritative unless the required prerequisite stages have completed with real evidence.

## Success criteria

A consequential Pancake request cannot produce an authoritative project decision unless:

1. The controller has loaded the current authoritative project map/state.
2. Relevant project history has been retrieved.
3. Required research has been completed or explicitly established as unnecessary for that request.
4. Available capabilities/tools have been enumerated from real runtime capability sources.
5. A plan has been produced from those verified inputs.
6. A deterministic validator approves the stage transition.

The same controller must also block execution when an action is not backed by an approved decision record, and GitHub remains the final enforcement layer for repository changes.

## Scope

The controller governs consequential Operation Pancake work, including:

- source/tool selection;
- architecture or workflow changes;
- blocker declarations;
- requests for user work or external permission;
- changes to project scope;
- code/data changes;
- package/release decisions;
- acceptance and completion claims;
- next-step decisions that alter the authoritative project state.

Ordinary non-project conversation and purely informational chat do not need to create a project decision record.

## Non-goals

The controller does not attempt to inspect or control a model's hidden chain of thought.

The controller does not mechanically govern a message sent directly to ChatGPT.com outside the Pancake-controlled interface. Mechanical enforcement applies only when Operation Pancake work enters through the controller.

The controller does not replace the existing evaluator, database, price watcher, roster tools, or GitHub gate.

## Placement

The controller will live inside the existing `operation_pancake` Python package rather than as a second standalone application.

Proposed primary module:

`src/operation_pancake/sop_gateway.py`

Supporting modules may be split out if needed for testability, but the user-facing entry point remains part of the existing Pancake launcher/application.

The existing local HTTP application remains the user surface. The controller sits between that surface and any model/tool invocation that can produce a consequential project decision.

## Enforcement model

### 1. Request classification

Every Pancake request is classified as either:

- `informational`: no authoritative project decision or action is being created; or
- `consequential`: the request can change project direction, state, code, data, tooling, external actions, acceptance, or completion.

Classification is owned by the controller, not by the model that will later make the decision. The model cannot downgrade a request from consequential to informational.

Classification is fail-closed: if the controller cannot confidently establish that a request is informational, it is treated as consequential and must enter the full decision state machine.

A consequential request must enter the state machine below.

### 2. Deterministic state machine

The controller owns stage progression. The model cannot advance itself to a later stage.

Allowed progression:

`MAP → HISTORY → RESEARCH → CAPABILITIES → PLAN → DECISION → EXECUTE → ADAPT → VERIFY → UPDATE_MAP → CONTINUE`

`DECISION` is an explicit enforcement boundary inserted between PLAN and EXECUTE.

The existing validator will be extended to support a `decision` action. `decision` requires, at minimum, completed MAP, HISTORY, RESEARCH, CAPABILITIES, and PLAN evidence.

The controller rejects illegal jumps, such as HISTORY → EXECUTE or MAP → DECISION.

### 3. Evidence, not booleans

A stage cannot pass merely because a field says `complete: true`.

Each stage record must contain evidence references appropriate to the stage.

Examples:

- MAP: exact checkpoint/state file and version/hash.
- HISTORY: exact prior decision records, commits, checkpoint sections, or retrieved conversation/project history used.
- RESEARCH: source identifiers, files, URLs, queries, or a controller-recorded determination that no external research was required.
- CAPABILITIES: actual tools/connections available at runtime, not assumptions.
- PLAN: proposed next action tied to the preceding evidence.
- VERIFY: test/run/browser evidence tied to the executed action.

A model cannot waive a required stage. Any stage-specific determination that work is unnecessary must come from controller policy, be recorded with a reason, and still satisfy the validator.

Evidence references must be serializable and auditable.

### 4. Decision records

Every consequential decision receives a durable record.

Proposed location:

`.operation_pancake/decisions/<timestamp>-<decision-id>.json`

Each record contains:

- request summary;
- consequential/informational classification;
- current mission;
- MAP evidence;
- HISTORY evidence;
- RESEARCH evidence;
- CAPABILITIES evidence;
- PLAN;
- proposed DECISION;
- validator result;
- approved execution scope;
- execution results;
- verification evidence;
- resulting map update;
- final status.

The record is append-oriented. Prior evidence is not silently rewritten to justify a later action.

## Model boundary

The model does not receive unrestricted authority to decide what comes next.

For a consequential request, the controller calls the model in stage-specific mode. The model is given only the current stage objective plus verified evidence from earlier stages.

Example:

- HISTORY stage: recover relevant prior work; do not recommend a solution.
- RESEARCH stage: investigate unresolved facts; do not execute.
- PLAN stage: produce candidate plan from validated evidence.
- DECISION stage: produce the project decision constrained by validated evidence.

Any output that tries to perform a later-stage action is discarded or treated as non-authoritative until the controller reaches that stage.

## Tool/action boundary

All consequential tool actions initiated through the Pancake controller require an approved decision ID.

Before execution, the controller checks:

1. the decision record exists;
2. the `decision` validator passed;
3. the requested tool/action is inside the approved execution scope;
4. any user-only approval or permission required by the action has been satisfied;
5. the decision has not been superseded or invalidated by newer project state.

If any check fails, the action is blocked.

## GitHub boundary

The existing protected branch and `sop-gate` required status check remain the final repository enforcement layer.

The new controller complements that gate:

- Controller: prevents unsupported decisions/actions before they occur.
- GitHub ruleset: prevents repository changes from becoming authoritative without the required check.

Neither replaces the other.

## Project state integration

`docs/SOP_STATE.json` remains a high-level authoritative SOP state artifact.

The controller will update it only through a normal branch/PR path protected by the existing ruleset when repository state must change.

Detailed per-decision evidence lives in the decision-record store so `SOP_STATE.json` does not become an unmanageably large audit log.

## Failure behavior

The controller is fail-closed for consequential work.

If required evidence cannot be retrieved, a required capability is unavailable, or validation fails:

- no authoritative decision is produced;
- no consequential tool action runs;
- the user receives the exact missing prerequisite or external dependency;
- the blocked state and evidence are recorded.

A model statement cannot override the controller's failed validation.

## User experience

The user should not have to manually operate the SOP.

Normal experience:

1. Open the existing Operation Pancake interface/launcher.
2. Submit a Pancake request normally.
3. The controller performs the required SOP stages automatically.
4. The user sees the final decision/result plus a concise explanation of the evidence path when useful.
5. User interaction is requested only for a genuine product decision, credential/permission, or other user-only action.

The user does not manually click MAP, HISTORY, RESEARCH, or other stages.

## Provider/model integration

Mechanical decision enforcement requires the Pancake controller to own the model call. The implementation therefore needs a model provider accessible from local code.

The controller will use a provider abstraction so enforcement logic is independent of the specific model backend.

No paid API usage, new account creation, or credential creation is authorized by this design approval alone. Enabling any provider that requires new spending or credentials is a separate user decision before activation.

## Security and safety

- No authentication bypass.
- No hidden credential storage in the repository.
- Secrets are read from an approved local secret mechanism/environment.
- No automatic purchases, sends, publishing, or account creation without the applicable user approval.
- Decision records must not store raw secrets.
- Existing browser and repository protections remain in place.

## Tests

Implementation must use TDD and include at least these acceptance cases:

1. Consequential decision fails when HISTORY is missing.
2. Consequential decision fails when HISTORY evidence is empty or synthetic.
3. Consequential decision fails when CAPABILITIES are assumed rather than runtime-verified.
4. Ambiguous request classification defaults to consequential.
5. The model cannot downgrade a consequential request to informational.
6. PLAN cannot execute directly without DECISION approval.
7. A tool action outside approved execution scope is blocked.
8. A blocker declaration fails unless required research/capability checks completed.
9. Completion fails unless VERIFY and UPDATE_MAP are complete.
10. Informational requests can complete without creating unnecessary execution state.
11. A stale decision is invalidated when authoritative project state changes materially.
12. GitHub merge remains blocked when the repository `sop-gate` fails.
13. Decision record preserves exact evidence references used for the decision.
14. Direct model output cannot change controller state without validator acceptance.
15. A model-requested stage waiver cannot bypass controller policy or validator requirements.

## Rollout

Phase 1: implement the controller and validator extension behind a local feature flag; no existing Pancake workflow is removed.

Phase 2: run controlled acceptance tests on known historical failure cases, including the 9,206-card database-acquisition decision where HISTORY was previously skipped.

Phase 3: make the controller the required entry point for consequential Operation Pancake work in the local app.

Phase 4: verify that the protected GitHub branch, controller decision gate, and action gate all work together end-to-end.

## Acceptance test based on the historical failure

Prompt/task: determine how to obtain or update the current card database.

Expected behavior:

- MAP loads the current catalog checkpoint.
- HISTORY must recover the actual origin/acquisition path of the 9,206-card database or explicitly report that it remains unresolved.
- The controller must not allow a provider-permission request, manual recording request, or replacement acquisition method to become the authoritative decision merely because HISTORY retrieval was incomplete.
- If the original acquisition path remains unresolved after the permitted retrieval/research work is exhausted, the system may declare the specific unresolved dependency, with evidence.

This acceptance case is mandatory because it directly represents the failure the controller is intended to prevent.

## Open implementation decision

The controller architecture is approved in principle, but activation requires choosing the local model provider/credential path. That choice will be made after the written spec is reviewed and the implementation plan identifies the exact provider requirements and any cost/credential impact.
