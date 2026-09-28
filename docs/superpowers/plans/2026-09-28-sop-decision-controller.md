# Operation Pancake SOP Decision Controller Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local, fail-closed Operation Pancake controller that makes MAP → HISTORY → RESEARCH → CAPABILITIES → PLAN a mechanical prerequisite for consequential project decisions, then guards execution and leaves the existing GitHub `sop-gate` as the final repository boundary.

**Architecture:** Add a deterministic SOP state machine and durable decision-record store inside the existing `operation_pancake` Python package. The controller owns request classification, stage progression, evidence validation, decision approval, and tool-action authorization; a provider adapter supplies stage-specific model outputs but cannot advance controller state itself. The existing local HTTP app becomes the entry point behind a feature flag first, then the required route after acceptance.

**Tech Stack:** Python 3.11+, pytest, existing `http.server` local app, JSON decision records, existing `scripts/verify_sop_gate.py`; provider abstraction with optional OpenAI Responses API activation after explicit credential/spend approval.

**Spec:** `docs/superpowers/specs/2026-09-28-sop-decision-controller-design.md`

## Global Constraints

- Governing SOP remains `MAP → HISTORY → RESEARCH → CAPABILITIES → PLAN → EXECUTE → ADAPT → VERIFY → UPDATE MAP → CONTINUE`.
- Insert explicit `DECISION` enforcement boundary between PLAN and EXECUTE.
- Classification is controller-owned and fail-closed; ambiguity means consequential.
- Stage completion requires auditable evidence references, not only `complete: true`.
- Model output cannot mutate controller state or waive a required stage.
- Consequential tool actions require an approved decision ID and approved execution scope.
- Detailed decision records live under `.operation_pancake/decisions/`; `docs/SOP_STATE.json` remains the high-level repository state artifact.
- Existing evaluator/database/price-watch/roster behavior is not rebuilt or replaced.
- Existing protected branch and required `sop-gate` remain in force.
- No API spending, credential creation, account creation, purchase, send, publish, or authentication bypass is authorized by implementation work alone.
- TDD for every behavior change; RED → GREEN → regression suite → commit.

## Review Focus

1. **Classifier ambiguity:** unclear or mixed requests must be treated as consequential, never downgraded by model output.
2. **Synthetic evidence:** strings such as `"history checked"` without a verifiable source reference must fail validation.
3. **State drift:** a decision approved against one authoritative state fingerprint must become stale when that state materially changes.
4. **Action widening:** execution must reject tools/arguments outside the exact approved scope even when the model requests them.
5. **Provider/tool mismatch:** runtime capabilities must describe tools actually configured in the controller runtime; ChatGPT.com Plugins are not assumed to exist locally.

---

### Task 1: Extend the deterministic validator with a real decision boundary

**Files:**
- Modify: `scripts/verify_sop_gate.py`
- Modify: `tests/test_sop_gate.py`

**Interfaces:**
- Consumes: existing SOP-state JSON shape and existing CLI `--action` argument.
- Produces: `validate(state: dict, action: str) -> list[str]` supporting `action="decision"`; helper validation that rejects missing/non-verifiable evidence for required stages.

- [ ] **Step 1: Write failing validator tests**

Add tests named:
- `test_decision_requires_map_history_research_capabilities_and_plan`
- `test_decision_rejects_empty_history_evidence`
- `test_decision_rejects_synthetic_evidence_without_reference`
- `test_model_stage_waiver_cannot_satisfy_required_stage`

Assertions: each incomplete or non-verifiable prerequisite returns nonzero and names the failing stage; a complete referenced-evidence state passes `--action decision`.

- [ ] **Step 2: Run the focused tests and verify RED**

Run: `python -m pytest -q tests/test_sop_gate.py`
Expected: new decision/evidence tests fail because `decision` and reference validation do not yet exist.

- [ ] **Step 3: Implement minimal validator changes**

Add `decision` to `ACTION_REQUIREMENTS` with prerequisites `map`, `history`, `research`, `capabilities`, `plan`.

Define evidence-reference acceptance so stage evidence must contain at least one structured reference with a non-empty `kind` and `ref` (or equivalent exact persisted source identity); plain free-text completion claims alone do not satisfy `decision`.

Preserve compatibility for current `commit` CI validation until repository state records are migrated in a later task.

- [ ] **Step 4: Run validator tests and existing gate regression**

Run: `python -m pytest -q tests/test_sop_gate.py`
Expected: PASS.

- [ ] **Step 5: Commit**

Commit message: `feat: add SOP decision validation boundary`

---

### Task 2: Add typed SOP records and append-oriented decision persistence

**Files:**
- Create: `src/operation_pancake/sop_models.py`
- Create: `src/operation_pancake/sop_decision_store.py`
- Create: `tests/test_sop_decision_store.py`

**Interfaces:**
- Produces `RequestClass(str, Enum)` values `INFORMATIONAL`, `CONSEQUENTIAL`.
- Produces `Stage(str, Enum)` values `MAP`, `HISTORY`, `RESEARCH`, `CAPABILITIES`, `PLAN`, `DECISION`, `EXECUTE`, `ADAPT`, `VERIFY`, `UPDATE_MAP`, `CONTINUE`.
- Produces immutable `EvidenceRef(kind: str, ref: str, digest: str | None, metadata: dict[str, object])`.
- Produces `DecisionRecord` containing request ID, request text/summary, classification, mission, authoritative-state fingerprint, stage entries, approved execution scope, status, timestamps.
- Produces `DecisionRecordStore(root: Path)` with `create(record)`, `load(decision_id)`, `append_stage(decision_id, stage, entry)`, and `finalize(decision_id, status)`.

- [ ] **Step 1: Write failing persistence tests**

Cover: new record creation under `.operation_pancake/decisions`, append-only stage history, exact evidence references preserved, duplicate decision IDs rejected, malformed JSON fails closed, and secrets-shaped fields are rejected from persisted evidence metadata.

- [ ] **Step 2: Run focused tests and verify RED**

Run: `python -m pytest -q tests/test_sop_decision_store.py`
Expected: import/file-not-found failures.

- [ ] **Step 3: Implement models and store**

Use atomic temp-file replacement for each persisted update; preserve prior stage entries rather than rewriting history in place.

- [ ] **Step 4: Run focused tests**

Run: `python -m pytest -q tests/test_sop_decision_store.py`
Expected: PASS.

- [ ] **Step 5: Commit**

Commit message: `feat: persist auditable SOP decision records`

---

### Task 3: Build controller-owned classification and deterministic stage progression

**Files:**
- Create: `src/operation_pancake/sop_provider.py`
- Create: `src/operation_pancake/sop_gateway.py`
- Create: `tests/test_sop_gateway.py`

**Interfaces:**
- `DecisionProvider.run_stage(stage: Stage, request: str, context: GatewayContext) -> StageOutput` protocol.
- `RequestClassifier.classify(request: str) -> RequestClass`; controller policy owns the final class.
- `SOPGateway.handle(request: str) -> GatewayResult`.
- `SOPGateway.advance(decision_id: str, stage: Stage, evidence: tuple[EvidenceRef, ...], payload: dict[str, object]) -> DecisionRecord`.

- [ ] **Step 1: Write failing classification/state-machine tests**

Cover: ambiguous request defaults to consequential; explicit informational request can bypass execution state only when policy proves it informational; provider output cannot downgrade classification; illegal stage jumps are rejected; HISTORY-stage provider output containing a recommendation cannot create a DECISION; DECISION cannot be reached until Task 1 validator passes.

- [ ] **Step 2: Run focused tests and verify RED**

Run: `python -m pytest -q tests/test_sop_gateway.py -k 'classification or stage or decision'`
Expected: import/not-implemented failures.

- [ ] **Step 3: Implement classifier, provider protocol, and state machine**

The controller, not provider output, sets classification and current stage. Stage-specific provider outputs are data only; state advances only through `SOPGateway.advance(...)` after validator acceptance.

- [ ] **Step 4: Run focused tests**

Run: `python -m pytest -q tests/test_sop_gateway.py -k 'classification or stage or decision'`
Expected: PASS.

- [ ] **Step 5: Commit**

Commit message: `feat: add fail-closed SOP decision controller`

---

### Task 4: Add authoritative state, history, research, and capability evidence sources

**Files:**
- Create: `src/operation_pancake/sop_evidence.py`
- Modify: `src/operation_pancake/sop_gateway.py`
- Modify: `tests/test_sop_gateway.py`

**Interfaces:**
- `ProjectStateSource.load() -> tuple[dict[str, object], EvidenceRef, str]` where final string is the authoritative state fingerprint.
- `HistorySource.retrieve(request: str, state: dict[str, object]) -> tuple[EvidenceRef, ...]`.
- `ResearchSource.research(request: str, state: dict[str, object], history: tuple[EvidenceRef, ...]) -> tuple[EvidenceRef, ...]`.
- `CapabilityRegistry.snapshot() -> tuple[EvidenceRef, ...]` from tools actually configured in the local runtime.

- [ ] **Step 1: Write failing evidence-source tests**

Cover: MAP records exact state file plus hash; HISTORY with no source reference blocks DECISION; capability claims absent from runtime registry are rejected; state fingerprint change invalidates a pending decision; a controller-recorded `research-not-required` reference is allowed only when policy marks that request class as not requiring external research.

- [ ] **Step 2: Run focused tests and verify RED**

Run: `python -m pytest -q tests/test_sop_gateway.py -k 'evidence or history or capability or stale'`
Expected: FAIL.

- [ ] **Step 3: Implement evidence-source interfaces and filesystem-backed project-state source**

Initial MAP source reads `docs/SOP_STATE.json` plus configured authoritative checkpoint paths. Capability registry enumerates only configured local tools/adapters; it must not import assumptions from ChatGPT.com.

- [ ] **Step 4: Run focused tests**

Run: `python -m pytest -q tests/test_sop_gateway.py -k 'evidence or history or capability or stale'`
Expected: PASS.

- [ ] **Step 5: Commit**

Commit message: `feat: ground SOP stages in runtime evidence`

---

### Task 5: Guard tool execution with approved decision scope

**Files:**
- Create: `src/operation_pancake/sop_actions.py`
- Modify: `src/operation_pancake/sop_gateway.py`
- Create: `tests/test_sop_actions.py`

**Interfaces:**
- `ActionRequest(tool: str, operation: str, arguments: dict[str, object], decision_id: str)`.
- `ActionAuthorizer.authorize(request: ActionRequest, current_state_fingerprint: str) -> AuthorizationResult`.
- `AuthorizationResult(allowed: bool, reason: str)`.

- [ ] **Step 1: Write failing action-guard tests**

Cover: missing decision ID blocked; validator-not-passed blocked; tool outside approved scope blocked; argument widening blocked; required user-only permission absent blocked; superseded/stale decision blocked; exact approved action allowed.

- [ ] **Step 2: Run focused tests and verify RED**

Run: `python -m pytest -q tests/test_sop_actions.py`
Expected: FAIL.

- [ ] **Step 3: Implement exact-scope authorization**

Scope matching must compare normalized tool, operation, and allowed argument constraints. No wildcard-all default for consequential actions.

- [ ] **Step 4: Run focused tests**

Run: `python -m pytest -q tests/test_sop_actions.py`
Expected: PASS.

- [ ] **Step 5: Commit**

Commit message: `feat: require approved SOP decision for actions`

---

### Task 6: Add provider adapter without silently enabling spending

**Files:**
- Create: `src/operation_pancake/sop_openai_provider.py`
- Modify: `pyproject.toml`
- Create: `tests/test_sop_openai_provider.py`

**Interfaces:**
- `OpenAIResponsesDecisionProvider(api_key: str | None = None, model: str | None = None, tools: tuple[dict[str, object], ...] = ())` implementing `DecisionProvider.run_stage(...)`.
- Provider reads `OPENAI_API_KEY` only from environment/approved secret source; no key is written to repository or decision records.
- Provider is inactive unless `PANCAKE_SOP_PROVIDER=openai` is explicitly configured.

- [ ] **Step 1: Write failing adapter tests using a fake client**

Cover: no live network call in tests; stage prompt contains only current-stage objective and validated prior evidence; tool list comes from controller capability registry; raw secret absent from logs/records; missing key produces a clear inactive-provider error before any API call.

- [ ] **Step 2: Run focused tests and verify RED**

Run: `python -m pytest -q tests/test_sop_openai_provider.py`
Expected: FAIL.

- [ ] **Step 3: Implement minimal Responses API adapter**

Use the official OpenAI Python SDK and Responses API. Do not enable billing, create an API key, add credits, or make live requests during implementation without separate user approval.

- [ ] **Step 4: Run focused tests**

Run: `python -m pytest -q tests/test_sop_openai_provider.py`
Expected: PASS without live API use.

- [ ] **Step 5: Commit**

Commit message: `feat: add opt-in OpenAI decision provider adapter`

**Activation note:** OpenAI API activation requires an API key and separate API billing/credits; it is not automatically supplied by the ChatGPT subscription. Current API documentation confirms the Responses API can use built-in tools, function tools, and remote MCP, but each local capability must be configured for this controller runtime rather than assumed from ChatGPT.com.

---

### Task 7: Integrate the controller into the existing local Pancake HTTP app behind a feature flag

**Files:**
- Create: `src/operation_pancake/sop_http.py`
- Modify: `src/operation_pancake/c3po_roster_app.py`
- Create: `tests/test_sop_http.py`

**Interfaces:**
- `create_sop_routes(gateway: SOPGateway) -> SOPRoutes` (or equivalent focused handler helper).
- Feature flag: `PANCAKE_SOP_GATEWAY_ENABLED=1` exposes the controlled request surface.
- Required-mode flag for post-acceptance rollout: `PANCAKE_SOP_GATEWAY_REQUIRED=1` rejects consequential Pancake decision requests that arrive through an ungated legacy decision route.

- [ ] **Step 1: Write failing HTTP integration tests**

Cover: flag off leaves current app behavior unchanged; flag on routes consequential requests through `SOPGateway.handle`; informational request can return without decision execution; failed gate returns exact missing prerequisite; no provider secret rendered; required mode rejects ungated consequential path.

- [ ] **Step 2: Run focused tests and verify RED**

Run: `python -m pytest -q tests/test_sop_http.py`
Expected: FAIL.

- [ ] **Step 3: Implement minimal local routes and feature-flag wiring**

Keep SOP HTTP code separate from the already-large `c3po_roster_app.py`; only wire construction/routing there.

- [ ] **Step 4: Run focused plus existing app regression tests**

Run: `python -m pytest -q tests/test_sop_http.py tests/test_c3po_clean_room_roster.py tests/test_c3po_partial_update.py`
Expected: PASS.

- [ ] **Step 5: Commit**

Commit message: `feat: route Pancake decisions through SOP gateway`

---

### Task 8: Reproduce the historical database-acquisition failure as a mandatory acceptance test

**Files:**
- Create: `tests/test_sop_historical_acceptance.py`
- Add fixture: `tests/fixtures/sop_database_history_unresolved.json`
- Modify: `src/operation_pancake/sop_gateway.py` only if acceptance reveals a controller defect.

**Interfaces:**
- Uses public `SOPGateway.handle(...)` and fake evidence/provider adapters only.

- [ ] **Step 1: Write the historical regression test**

Prompt: determine how to obtain/update the current card database.

Fixture state establishes known catalog status but leaves the original 9,206-card acquisition path unresolved.

Assert the controller cannot authorize provider-permission email, manual-recording request, or replacement acquisition method until HISTORY either recovers that origin or records an exhausted, evidenced unresolved dependency.

- [ ] **Step 2: Run and verify RED if any bypass remains**

Run: `python -m pytest -q tests/test_sop_historical_acceptance.py`
Expected: PASS only if the earlier failure path is mechanically blocked; otherwise RED identifies the remaining loophole.

- [ ] **Step 3: Make only the minimal controller fix required by the regression**

No scoring/database changes in this task.

- [ ] **Step 4: Run focused and complete SOP suites**

Run: `python -m pytest -q tests/test_sop_gate.py tests/test_sop_decision_store.py tests/test_sop_gateway.py tests/test_sop_actions.py tests/test_sop_openai_provider.py tests/test_sop_http.py tests/test_sop_historical_acceptance.py`
Expected: PASS.

- [ ] **Step 5: Commit**

Commit message: `test: lock historical SOP failure behind decision gate`

---

### Task 9: End-to-end rollout verification and protected-branch acceptance

**Files:**
- Modify: `docs/SOP_STATE.json`
- Modify: `.github/workflows/sop-gate.yml` only if the new deterministic tests are not already covered by existing invocation.
- Modify: `docs/superpowers/specs/2026-09-28-sop-decision-controller-design.md` only for factual as-built notes, not scope changes.

**Interfaces:**
- Existing `sop-gate` GitHub required status check.
- Existing protected branch `product/c3po-clean-room-roster`.

- [ ] **Step 1: Run complete local regression suite**

Run: `python -m pytest -q`
Expected: existing suite plus new SOP suites PASS; pre-existing skips/warnings documented, no new unexplained failures.

- [ ] **Step 2: Run deterministic validator directly**

Run: `python scripts/verify_sop_gate.py --state docs/SOP_STATE.json --action decision`
Expected: PASS after state artifact is migrated to referenced evidence format.

- [ ] **Step 3: Run controlled local gateway acceptance with fake provider/tools**

Verify: ambiguous request is gated; missing HISTORY blocks; approved exact action succeeds; out-of-scope action is blocked; state drift invalidates prior decision.

- [ ] **Step 4: Optional live-provider smoke test only after explicit user approval**

Prerequisites: user-approved provider, API key/credential path, and spending authorization if required. Without those prerequisites, record this step as externally blocked rather than substituting a synthetic claim.

- [ ] **Step 5: Open implementation PR and let required `sop-gate` run**

Do not bypass the protected branch. Merge only after the required check passes and the user-approved execution workflow reaches the integration step.

- [ ] **Step 6: Update `docs/SOP_STATE.json` and decision evidence**

Record controller acceptance state, remaining provider/tool parity limitations, and exact next action. Do not claim ChatGPT.com direct-message enforcement.

- [ ] **Step 7: Commit**

Commit message: `docs: record SOP decision controller acceptance`

## Execution Boundary

Implementation can complete Tasks 1–5 and the non-live portions of Tasks 6–9 without API spending or new credentials. **Activation as the actual Operation Pancake conversational entry point requires a separate provider decision** because a local OpenAI-backed controller needs an API key and API billing, and local tool parity must be explicitly configured. Direct messages sent to ChatGPT.com remain outside this controller and cannot be mechanically intercepted by repository code.
