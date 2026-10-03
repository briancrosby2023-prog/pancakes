# Operation Pancake — Authoritative Handoff

State revision: 26
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
- MAP: OBSERVED: revision 25 / 11c012a3 is live, clean and READY for OP-CATALOG-001. | OBSERVED: fresh immutable issue #62 reached brokered physical acceptance and failed with the same WinError 5 replacing server.py.r24.tmp over server.py as terminal issue #60. | OBSERVED: controlled recovery restored Simple Evaluator on dynamic port 8766 with the original server/release hashes and protected state unchanged.
- HISTORY: VERIFIED_HISTORY: revision 25 was broker-created, published as PR #61, passed SOP Gate, merged at 11c012a3 and rebound READY. | VERIFIED_HISTORY: issues #60 and #62 are terminal; two failures invalidate the running-listener/stop-order hypothesis as the sole root cause. | VERIFIED_HISTORY: denied raw routes, provider-email rejection, scoring, exact-card identity, watches and persistent 429 lock remain preserved.
- RESEARCH: OBSERVED: controlled filesystem diagnostic stopped the exact server and observed the old PID absent after 0.14 seconds; byte-identical os.replace to server.py still failed with WinError 5. | OBSERVED: in the same controlled diagnostic, a byte-identical in-place server.py write with flush/fsync succeeded, the app relaunched on the accepted dynamic port, and protected state remained unchanged. | OBSERVED: separate brokered byte-identical probes proved os.replace succeeds for RELEASE.json and PRODUCTION_WORKSTATION_ACCEPTANCE_3T.json, so the restriction is server.py-specific in the tested runtime.
- CAPABILITIES: OBSERVED: revision-25 Gateway/Broker and durable worker are healthy and authorized the controlled diagnostics and runtime recovery. | OBSERVED: a four-path revision-26 patch can change only the server.py application primitive/process-exit guard, focused tests, authority and canonical handoff. | OBSERVED: no user action, paid service, scoring change, catalog collection, source-access retry or JSON acceptance-write redesign is required.

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

## Next action
Deploy the evidence-backed revision-26 server-write correction through the existing Gateway/Broker path, then submit one fresh immutable complete_simple_single_worktab_acceptance request. Issues #60 and #62 are terminal and must not be replayed. Controlled Windows diagnostics proved that after the old Simple Evaluator PID is absent, atomic os.replace of server.py still fails with WinError 5 while a byte-identical in-place write succeeds and protected state survives; the same atomic replacement succeeds for RELEASE.json and PRODUCTION_WORKSTATION_ACCEPTANCE_3T.json. Revision 26 must therefore use a flushed/fsynced, hash-verified in-place write only for server.py, explicitly confirm the old PID is absent, keep the JSON atomic writes unchanged, and preserve all Browser Helper, scoring, exact-card identity, watches, source locks and persistent RATE_LIMITED protections.

## Remaining executable work
- Validate revision-26 with authority/handoff/self-test and focused tests.
- Obtain fresh Gateway/Broker authorization; create/publish/merge exact revision-26 and rebind the worker.
- Submit a fresh immutable full single-worktab acceptance request; do not replay issues #60 or #62.
- Verify server in-place postimage write, helper 1.4.13, one-tab dwell/cadence, protected state, evaluator and both restart proofs.
- Continue OP-CATALOG-001 because the five current FS versions still are not imported and catalog criteria remain open.

## Completion rule
A commit, test, CI run, PR, package, screenshot, or progress report is only a checkpoint.
Continue until the user-facing objective is verified, executable work is exhausted, or one genuine external action remains.
