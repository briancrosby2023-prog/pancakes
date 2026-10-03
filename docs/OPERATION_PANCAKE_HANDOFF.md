# Operation Pancake — Authoritative Handoff

State revision: 31
Status: IN_PROGRESS
Mission ID: OP-CATALOG-001

## Mission
Obtain a permitted current CFB27 exact-card catalog or delta, import missing exact-card versions without replacing older versions, and revalidate current Top 5 and Best Value results on unchanged scoring models.

## Mandatory SOP
MAP → HISTORY → RESEARCH → CAPABILITIES → PLAN → EXECUTE → ADAPT → VERIFY → UPDATE MAP → CONTINUE

## Start-of-session rule
Read `docs/OPERATION_PANCAKE_CONTROL_STATE.json` first and validate it before making a consequential Pancake decision.
Do not let the newest obstacle replace the recorded mission.

## Preflight evidence
- MAP: OBSERVED: Revision 30 / eae7c051 is merged, deployed and READY for OP-CATALOG-001. | OBSERVED: fresh immutable issue #73 passed request freeze and Gateway/Broker authorization, progressed past Revision-30 foreground handling, and failed only because select_developer_toggle observed two nodes named Developer mode. | OBSERVED: the exact controlled Edge PID 29544 / handle 55643466 remains available with Browser Helper 1.4.13 and the extensions surface.
- HISTORY: VERIFIED_HISTORY: issues #60/#62/#64/#66/#69/#71/#73 are terminal and must not be replayed. | VERIFIED_HISTORY: Revision 30 replaced the failed SetForegroundWindow dependency with UIA address-bar focus and progressed acceptance to the later Developer-mode selector. | VERIFIED_HISTORY: denied source routes, provider-email rejection, exact-card identity, watches, persistent RATE_LIMITED lock, dynamic-port architecture and scoring remain unchanged.
- RESEARCH: OBSERVED: current UIA tree contains exactly two elements named Developer mode: one ControlType.Text at X117/Y661 with empty AutomationId and one ControlType.Button at X435/Y660 with AutomationId dev-switch. | OBSERVED: the Button node is the sole enabled visible Developer mode TogglePattern control, state On, and has the same RuntimeId as the dev-switch toggle entry; the other same-name node has no TogglePattern. | OBSERVED: three other TogglePattern controls are distinct by name/AutomationId/geometry; exact dev-switch identity removes the false label ambiguity without broadening selection.
- CAPABILITIES: OBSERVED: select_developer_toggle already receives toggle Name, AutomationId, Enabled, State and geometry, so Revision 31 needs no broader browser/UI mutation surface. | OBSERVED: Revision 31 can prefer the exact dev-switch TogglePattern control, fail closed on duplicate exact matches, and preserve the existing spatial fallback for older UI trees. | OBSERVED: the recorded-chat DecisionProvider route remains available through the unchanged strict SOPDecisionGateway and ControlledToolBroker without paid API credits, Work or Codex.

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
- Desktop Commander for current Windows Simple Evaluator inspection/restart acceptance
- existing accepted dynamic-port Simple Evaluator launcher/check path
- physically accepted Simple Evaluator 3T / 1.2.0 r61 installation with persistent 429 safety lock and Browser Helper 1.4.12
- version-aware installed catalog importer/persistence path
- accepted Chrome/browser-helper exact-card price observation path after catalog import
- historical CFB27 bulk acquisition adapter and saved provenance
- read-only reconciliation of permitted-use basis and source reachability
- read-only monitoring for materially new authorized structured CUT-source evidence
- version-aware exact-card import and accepted Chrome pricing path once a permitted source exists
- existing conservative 12-requests/minute 50-card bulk adapter
- existing version-aware CFB27 delta refresh with hashed provenance and conflict checks
- existing CfbFanPublicAdapter public-player-page parser and fixed-page acquisition path
- saved exact-card public player-page source_reference URLs from established listing discovery
- normal rendered CFB.FAN exact-card page inspection for known source pages through the connected browser, bounded and fail-closed
- existing Browser Helper same-tab value-price batch navigation with five-second dwell and exact-card URL matching
- brokered installed Simple Evaluator hotfix/rollback and physical acceptance path
- revision-20 durable inbox action for fixed single-worktab browser activation and physical acceptance through Gateway/Broker
- fail-closed Windows UI Automation inside the durable worker with exact installed-helper/protected-state preconditions
- revision-21 minimal durable-loader repair through bounded patch/publish/merge/rebind
- fresh immutable GitHub-inbox request for the unchanged complete_simple_single_worktab_acceptance action after corrected worker deployment
- revision-22 minimal single-worktab action authority-pin repair through bounded patch/publish/merge/rebind
- fresh immutable GitHub-inbox request for complete_simple_single_worktab_acceptance after revision-22 deployment
- revision-23 minimal single-worktab launch-loader sibling-import repair through bounded patch/publish/merge/rebind
- fresh immutable GitHub-inbox request for complete_simple_single_worktab_acceptance after revision-23 deployment
- revision-24 minimal single-worktab management-page navigation repair through bounded patch/publish/merge/rebind
- fresh immutable GitHub-inbox request for complete_simple_single_worktab_acceptance after revision-24 deployment
- revision-27 bounded self-recovery of the controlled Edge helper window followed by same-tab Developer-mode activation and queue return
- revision-28 bounded exact Installed extensions readiness polling with Developer-mode AlreadyOn preservation

## Accepted — do not reopen without materially new evidence
- accepted-sop-order: Operation Pancake SOP order is MAP -> HISTORY -> RESEARCH -> CAPABILITIES -> PLAN -> EXECUTE -> ADAPT -> VERIFY -> UPDATE MAP -> CONTINUE.
- accepted-dynamic-port: Simple Evaluator uses the accepted dynamic localhost-port startup architecture; no fixed port is canonical.
- accepted-browser-watch: Original 3U Browser Watch production acceptance is closed and must not be reopened without a new regression.
- accepted-two-layer-control-standard: Operation Pancake behavior control requires both a ChatGPT instruction layer and a fail-closed controlled execution layer; neither alone satisfies the objective.
- accepted-provider-contact-approval: External provider messages, paid access, or account creation for catalog acquisition require explicit user approval before execution.
- accepted-authoritative-history-route-guard: Consequential strict decisions must independently load structured REQUIRED_NEXT/REJECTED route constraints from the project authority; caller-supplied history cannot omit or override them.
- accepted-existing-catalog-acquisition-route: OP-CATALOG-001 may use historically established public unauthenticated CFB.FAN acquisition methods already present in the repository: the bulk player-items adapter when reachable and the fixed public-player-page CfbFanPublicAdapter. Both remain bounded by existing conservative rate, provenance, validation, and fail-closed rules; no bypass or evasion is authorized.

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
- reject-provider-email-as-catalog-next-action: Treat the preserved Stormstrike/CFB.FAN provider-email request as the current or only next action for OP-CATALOG-001.
- reject-catalog-access-bypass: Bypass authentication, CAPTCHA, access controls, explicit denial, or rate limits; change identity/rate behavior to evade source restrictions.
- reject-catalog-denied-route-retry: Retry either observed-denied CFB.FAN acquisition request, or change client identity/authentication/cookies/headers/proxy/rate behavior to regain access, without materially new evidence that the denial condition changed.
- reject-issue64-replay: Replay issue #64 or depend on an already-open controlled Edge helper window without materially new evidence.
- reject-issue66-replay: Replay issue #66 or replace the exact Installed extensions condition with an unbounded/generic delay.
- reject-issue69-replay: Replay issue #69 or retry WScript.Shell.AppActivate by PID/title without materially new evidence.

## Next action
Deploy the minimal Revision-31 exact Developer-mode toggle identity correction through the existing Gateway/Broker path, then submit one fresh immutable complete_simple_single_worktab_acceptance request against deployed Revision 31. Do not replay issues #60, #62, #64, #66, #69, #71 or #73. Issue #73 is terminal after Revision 30 passed the foreground-navigation boundary and failed only because the UIA snapshot contained two nodes named Developer mode. A bounded read-only probe proved those are not two controls: one is ControlType.Text with no AutomationId, while the other is the single enabled visible TogglePattern button named Developer mode with AutomationId dev-switch and state On. Revision 31 must prefer exactly one enabled usable TogglePattern Developer mode control with exact AutomationId dev-switch and fail closed if that exact control is duplicated; retain the existing spatial-label selector only as a fallback when the exact dev-switch control is absent. Preserve every existing foreground, readiness, server, helper, one-tab, dwell/cadence, exact-card, protected-state, evaluator, restart, denied-source, persistent RATE_LIMITED and unchanged-scoring guard.

## Remaining executable work
- Publish/merge/rebind the exact Revision-31 four-path dev-switch selector correction through fresh Gateway/Broker authorization.
- Submit one fresh immutable full single-worktab acceptance request; do not replay issues #60, #62, #64, #66, #69, #71 or #73.
- Verify exact dev-switch selection plus helper 1.4.13, one-tab dwell/cadence, protected state, evaluator and both restart proofs.
- Continue OP-CATALOG-001 because the five current FS versions still are not imported and catalog criteria remain open.

## Completion rule
A commit, test, CI run, PR, package, screenshot, or progress report is only a checkpoint.
Continue until the user-facing objective is verified, executable work is exhausted, or one genuine external action remains.
