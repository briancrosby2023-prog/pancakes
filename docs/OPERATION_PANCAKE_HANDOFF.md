# Operation Pancake — Authoritative Handoff

State revision: 9
Status: COMPLETE
Mission ID: OP-CONTROL-002

## Mission
Enforce the Operation Pancake SOP across ChatGPT behavior and consequential execution so MAP -> HISTORY -> RESEARCH -> CAPABILITIES precede decisions, guessing/retry loops are fail-closed, user testing is last-resort, and controlled mutation cannot bypass a validated decision.

## Mandatory SOP
MAP → HISTORY → RESEARCH → CAPABILITIES → PLAN → EXECUTE → ADAPT → VERIFY → UPDATE MAP → CONTINUE

## Start-of-session rule
Read `docs/OPERATION_PANCAKE_CONTROL_STATE.json` first and validate it before making a consequential Pancake decision.
Do not let the newest obstacle replace the recorded mission.

## Preflight evidence
- MAP: Current authority revision 3 declared OP-CONTROL-001 COMPLETE even though its own gateway status records direct_chatgpt_interception=false. | Current failure reproduced the original behavior problem: a Simple Evaluator patch direction was chosen before MAP/HISTORY/RESEARCH/CAPABILITIES were restored. | The existing SOP gateway and repository CI are real controls but do not mechanically intercept ordinary ChatGPT turns. | Revision 7's Work/Codex-dependent next action became stale after the user explicitly required a no-Work/no-Codex solution and the durable Windows control worker passed physical acceptance.
- HISTORY: PR #11 false 8788 normalization, Opera mission drift, Desktop Commander retries, checkpoint-as-completion, and speculative user testing are already documented failure classes. | OP-CONTROL-001 created project-wide authority, locks, deterministic handoff, repository preflight and CI, but closed despite the acknowledged ordinary-chat interception gap. | During OP-SIMPLE-002, r61 was proposed before proving which Windows runtime was actually serving the application, demonstrating the unresolved cross-surface behavior gap. | Fresh ordinary ChatGPT adversarial test after initial global-instruction installation failed: the assistant supplied an r61-style code change before loading current authority/preflight. | The durable worker was reconstructed from preserved evidence, installed through two broker-authorized mutations, and verified with live RED/GREEN/restart tests on DESKTOP-M730I21. | Independent pre-publication verification of the first local revision-8 branch found docs/OPERATION_PANCAKE_HANDOFF.md had one extra trailing newline; publication was stopped before any push or merge. | After the corrected ad9acd8 revision-8 branch passed 57/57 tests, the first publication attempt was stopped with zero remote mutation when OAuth reauthorization returned 'Your session has ended'. | A live refresh diagnostic after D8 returned HTTP 503 Service Unavailable from the ChatGPT token endpoint; the publication process remained pre-decision and no remote branch existed. | PR #35 merged the exact D9 revision-8 candidate 440f26aaf235b5b23a3979a551c2ddeba26ea923 into the long-lived product branch as a295eeb7f271dcd8e45d3ab798e5fb74fb60e81b. | Post-merge GitHub checks on a295eeb7 passed: Operation Pancake SOP Gate success and C3PO Clean Room Acceptance success. | Independent Windows verification of the merge commit passed authority validate, preflight, canonical handoff, durable-runner self-test, and 59/59 focused regressions. | The stale revision-7 durable worker was replaced through DECISION_ALLOWED runtime-upgrade-ee5d8319bc0c7997f070 using ControlledToolBroker; the replacement worker is READY on revision 8 / a295eeb7. | Post-merge issue #36 completed through DECISION_ALLOWED inspect_control_state and returned clean revision-8 authority on a295eeb7 with zero mutation. | The first broker-authorized revision-9 closure commit attempt (close-r9-6e695770d612cfeea89b) failed before commit because the handler used strip() on git status output, removing the leading status-column space from the first path and misreading docs/... as ocs/...; cleanup removed the worktree and branch and left the product checkout clean.
- RESEARCH: OpenAI Projects support project instructions that apply within the project and override global custom instructions. | OpenAI Custom Instructions apply across chats and provide a global behavioral fallback. | OpenAI Responses/function calling supports allowed_tools restrictions; the Agents SDK is appropriate when the application owns tool implementations, state, approvals, and runtime behavior. | No current product documentation establishes Project or Custom Instructions as a hard execution interceptor; mechanical guarantees require the controlled runtime/tool layer. | OpenAI documentation says Custom Instructions are applied across chats, but does not document them as a hard execution interceptor; Project instructions apply only inside the project and override global instructions there. | The ChatGPT-plan OAuth Responses flow returned an observed HTTP 400 for unsupported max_output_tokens; removing only that parameter produced HTTP 200 and a valid structured decision response. | Windows core.autocrlf=true caused raw checked-out bytes to differ from trusted Git blob hashes; accepting only the exact LF-normalized blob hash fixed the false rejection while a real tamper still failed. | The canonical scripts/pancake_control.py handoff --check compares the checked-in handoff to render_handoff(state) exactly; adding a second trailing newline is invalid. | The stored ID token exp was observed older than current time by more than nine hours; the returning OAuth path unconditionally reused it as id_token_hint after refresh failure. Expired hints must be omitted while login_hint, client id, PKCE, and post-callback identity validation remain enforced. | Transient OAuth refresh failures (429/500/502/503/504) must remain fail-closed and must not trigger interactive reauthorization; non-transient refresh rejection may still fall back to the returning OAuth flow. | Canonical Git/LF SHA-256 for scripts/pancake_local_control.py at a295eeb7 is 412e14b0d6c3b637bff65278aceb0d1d4b92f9f3a7aaef94a9b16dcbc7f6d24d; the deployed Windows CRLF checkout normalizes to the same canonical bytes and has raw SHA-256 ee5d8319bc0c7997f070e42d32a59941fa684433944563889d9f2a4b5320d59f.
- CAPABILITIES: GitHub repository read/write and protected PR workflow are available. | Files/Library retrieval and web research are available. | The current chat can create repository control code and documentation but has no account-setting action for Project instructions or Custom Instructions. | The existing OpenAI decision transport is fail-closed when a programmatic credential is absent. | Desktop Commander allowance was restored on 2026-10-01, the user explicitly authorized its use, and DESKTOP-M730I21 was connected only as bootstrap/recovery transport. | A persistent Windows GitHub-inbox worker now provides ordinary-Project execution without Work or Codex and routes consequential actions through SOPDecisionGateway and ControlledToolBroker. | DigitalOcean remains prohibited. | The long-lived revision-8 branch, GitHub CI, merged Windows worktree, durable runtime, and live GitHub-inbox execution path were all independently re-verified after merge without Work or Codex.

## Available capabilities
- GitHub repository read/write and PR workflow
- Files/Library retrieval
- container/Python validation where available
- web research
- repository SOP gateway, OpenAI decision transport, and fail-closed tool-broker implementation
- Desktop Commander bootstrap/recovery transport while allowance is restored
- persistent Windows GitHub-inbox control worker with plan OAuth decision provider
- read-only loopback worker health surface with no mutation HTTP endpoint
- deployed revision-8 persistent Windows GitHub-inbox worker bound to long-lived merge a295eeb7

## Accepted — do not reopen without materially new evidence
- accepted-sop-order: Operation Pancake SOP order is MAP -> HISTORY -> RESEARCH -> CAPABILITIES -> PLAN -> EXECUTE -> ADAPT -> VERIFY -> UPDATE MAP -> CONTINUE.
- accepted-dynamic-port: Simple Evaluator uses the accepted dynamic localhost-port startup architecture; no fixed port is canonical.
- accepted-browser-watch: Original 3U Browser Watch production acceptance is closed and must not be reopened without a new regression.
- accepted-two-layer-control-standard: Operation Pancake behavior control requires both a ChatGPT instruction layer and a fail-closed controlled execution layer; neither alone satisfies the objective.

## Rejected/superseded — do not retry without materially new evidence
- reject-hardcoded-8788: Hard-code 127.0.0.1:8788 as the Simple Evaluator port.
- reject-replacement-launcher: Invent a replacement launcher/runtime merely because an existing component is inconvenient.
- reject-opera-mission-drift: Treat an Opera connector failure as a new mission or as proof the overall decision-control effort is blocked.
- reject-desktop-commander-retry: Retry or recheck Desktop Commander before its allowance is restored.
- reject-checkpoint-completion: Treat a test, commit, CI run, PR, package, screenshot, or intermediate checkpoint as completion while executable work remains.
- reject-feature-before-control: Resume Simple Evaluator/Price Watch/Training Watch feature work before the overall decision-process control mission is implemented and verified.
- reject-instruction-only-completion: Declare the control problem solved because Project/Custom Instructions exist without mechanical mutation enforcement.
- reject-guess-patch-loop: Create another implementation patch from an unverified root-cause hypothesis or retry a failed hypothesis without materially new evidence.
- reject-user-test-before-exhaustion: Ask the user to install/click/restart/test while legitimate executable technical routes remain.

## Next action
complete

## Remaining executable work
- None

## Completion rule
A commit, test, CI run, PR, package, screenshot, or progress report is only a checkpoint.
Continue until the user-facing objective is verified, executable work is exhausted, or one genuine external action remains.
