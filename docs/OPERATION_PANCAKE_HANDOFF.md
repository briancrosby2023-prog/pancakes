# Operation Pancake — Authoritative Handoff

State revision: 27
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
- MAP: OBSERVED: revision 26 / 23a64231 is live, clean and READY for OP-CATALOG-001. | OBSERVED: fresh immutable issue #64 passed the Revision-26 server.py in-place write boundary and failed later with ControlError Windows UI Automation returned no JSON. | OBSERVED: post-#64 rollback restored original server/release hashes; current Windows process inventory contains no visible Edge root with --load-extension=*SimpleEvaluator*browser-helper*.
- HISTORY: VERIFIED_HISTORY: issues #60 and #62 are terminal Windows server.py replacement failures; revision 26 replaced only that blocked primitive with the controlled in-place write and #64 progressed beyond it. | VERIFIED_HISTORY: the Revision-19 Edge restart/--load-extension-only hypothesis failed because helper runtime remained 1.4.12; it is not sufficient activation and must not be retried as such. | VERIFIED_HISTORY: later Revision-19 evidence showed the installed 1.4.13 extension recognized but OFF with Developer mode required; enabling Developer mode on the controlled Edge window then produced live helper 1.4.13. Issues #60/#62/#64 remain terminal.
- RESEARCH: OBSERVED: revision-26 find_controlled_edge requires one visible Edge root whose command line contains --load-extension=*SimpleEvaluator*browser-helper*; with no matching process its PowerShell pipeline emitted no JSON, exactly matching #64. | OBSERVED: current process inspection shows only unrelated headless Edge profiles and no matching visible controlled helper window. | OBSERVED: historical bounded control used debugging port 9255, --remote-allow-origins=*, --load-extension=<installed browser-helper>, --no-first-run, --new-window and existing-profile reuse; the later successful activation navigated that same controlled tab to edge://extensions, enabled Developer mode, returned to the shared CFB.FAN URL and verified helper 1.4.13.
- CAPABILITIES: OBSERVED: revision-26 Gateway/Broker and durable worker remain healthy and READY after #64 rollback. | OBSERVED: the physical action can distinguish an absent controlled Edge window, create only the bounded historical helper window, navigate the same selected tab through the exact extensions surface and back to the current queue URL, and then reuse all existing acceptance checks. | OBSERVED: no user action, paid service, catalog collection, source-access retry, scoring change, broad browser termination or new database is required.

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

## Next action
Deploy the minimal revision-27 controlled-Edge recovery correction through the existing Gateway/Broker path, then submit one fresh immutable complete_simple_single_worktab_acceptance request. Issues #60, #62 and #64 are terminal and must not be replayed. Revision 26 fixed the server.py Windows write primitive and #64 progressed past that boundary, then failed because no visible Edge root process existed with the installed --load-extension Simple Evaluator helper; find_controlled_edge therefore produced no UI Automation JSON. Revision 27 must recreate only the bounded historical controlled Edge window when absent using debugging port 9255, the exact installed helper, existing-profile reuse and the current shared CFB.FAN queue URL; then it must run the already-proven Developer-mode activation sequence on that same tab before continuing the unchanged dwell/cadence/persistence/evaluator/restart acceptance. Preserve scoring, exact-card identity, watches, denied source locks and the persistent RATE_LIMITED value-probe lock.

## Remaining executable work
- Validate revision-27 with authority/handoff/self-test and focused tests.
- Obtain fresh Gateway/Broker authorization; create/publish/merge exact revision-27 and rebind the worker.
- Submit a fresh immutable full single-worktab acceptance request; do not replay issues #60, #62 or #64.
- Verify controlled Edge self-recovery, helper 1.4.13 activation, one-tab dwell/cadence, protected state, evaluator and both restart proofs.
- Continue OP-CATALOG-001 because the five current FS versions still are not imported and catalog criteria remain open.

## Completion rule
A commit, test, CI run, PR, package, screenshot, or progress report is only a checkpoint.
Continue until the user-facing objective is verified, executable work is exhausted, or one genuine external action remains.
