# Operation Pancake — Authoritative Handoff

State revision: 8
Status: IN_PROGRESS
Mission ID: OP-CONTROL-002

## Mission
Enforce the Operation Pancake SOP across ChatGPT behavior and consequential execution so MAP -> HISTORY -> RESEARCH -> CAPABILITIES precede decisions, guessing/retry loops are fail-closed, user testing is last-resort, and controlled mutation cannot bypass a validated decision.

## Mandatory SOP
MAP → HISTORY → RESEARCH → CAPABILITIES → PLAN → EXECUTE → ADAPT → VERIFY → UPDATE MAP → CONTINUE

## Start-of-session rule
Read `docs/OPERATION_PANCAKE_CONTROL_STATE.json` first and validate it before making a consequential Pancake decision.
Do not let the newest obstacle replace the recorded mission.

## Preflight evidence
- MAP: Current authority revision 3 declared OP-CONTROL-001 COMPLETE even though its own gateway status records direct_chatgpt_interception=false. | Current failure reproduced the original behavior problem: a Simple Evaluator patch direction was chosen before MAP/HISTORY/RESEARCH/CAPABILITIES were restored. | The existing SOP gateway and repository CI are real controls but do not mechanically intercept ordinary ChatGPT turns.
- HISTORY: PR #11 false 8788 normalization, Opera mission drift, Desktop Commander retries, checkpoint-as-completion, and speculative user testing are already documented failure classes. | OP-CONTROL-001 created project-wide authority, locks, deterministic handoff, repository preflight and CI, but closed despite the acknowledged ordinary-chat interception gap. | During OP-SIMPLE-002, r61 was proposed before proving which Windows runtime was actually serving the application, demonstrating the unresolved cross-surface behavior gap. | Fresh ordinary ChatGPT adversarial test after initial global-instruction installation failed: the assistant supplied an r61-style code change before loading current authority/preflight.
- RESEARCH: OpenAI Projects support project instructions that apply within the project and override global custom instructions. | OpenAI Custom Instructions apply across chats and provide a global behavioral fallback. | OpenAI Responses/function calling supports allowed_tools restrictions; the Agents SDK is appropriate when the application owns tool implementations, state, approvals, and runtime behavior. | No current product documentation establishes Project or Custom Instructions as a hard execution interceptor; mechanical guarantees require the controlled runtime/tool layer. | OpenAI documentation says Custom Instructions are applied across chats, but does not document them as a hard execution interceptor; Project instructions apply only inside the project and override global instructions there.
- CAPABILITIES: GitHub repository read/write and protected PR workflow are available. | Files/Library retrieval and web research are available. | The current chat can create repository control code and documentation but has no account-setting action for Project instructions or Custom Instructions. | Desktop Commander remains prohibited and DigitalOcean remains prohibited. | The existing OpenAI decision transport is fail-closed when a programmatic credential is absent.

## Available capabilities
- GitHub repository read/write and PR workflow
- Files/Library retrieval
- container/Python validation where available
- web research
- repository SOP gateway, OpenAI decision transport, and fail-closed tool-broker implementation

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
Verify the Codex/repository surface and deterministic handoff surface against the same adversarial SOP-bypass scenario, then close OP-CONTROL-002 only if those remaining surfaces pass.

## Remaining executable work
- Verify the Codex/repository adversarial surface without relying on a direct-write bypass.
- Verify deterministic handoff preserves active mission, locks, preflight requirement, and next action.
- Record final cross-surface results and close OP-CONTROL-002 only if both remaining surfaces pass.
- Resume OP-SIMPLE-002 only after OP-CONTROL-002 is accepted.

## Completion rule
A commit, test, CI run, PR, package, screenshot, or progress report is only a checkpoint.
Continue until the user-facing objective is verified, executable work is exhausted, or one genuine external action remains.
