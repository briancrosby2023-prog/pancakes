# Operation Pancake — Authoritative Handoff

State revision: 20
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
- MAP: OBSERVED: revision 19 / 9c886fe8 is the live OP-CATALOG-001 authority and the durable Windows GitHub-inbox worker is READY on that exact head. | OBSERVED: the broker-authorized browser-helper/watch.js repair completed successfully; all seven installed single-worktab integration files now match the validated 1.4.13 candidate, including explicit MIN_PAGE_DWELL_MS = 5000. | OBSERVED: protected Simple Evaluator state remains intact after the repair: two saved Price Watches, 130 state observations, 100 feed observations, unchanged alerts/runtime hashes, and the persistent RATE_LIMITED value-probe lock. | OBSERVED: the live browser-helper heartbeat still reports runtime 1.4.12 while expected_version is 1.4.13, so physical browser activation/acceptance remains unfinished.
- HISTORY: VERIFIED_HISTORY: both raw CFB.FAN acquisition clients remain denied with one-request HTTP 403 ACCESS_DENIAL and may not be retried or emulated. | VERIFIED_HISTORY: the normal rendered-page path previously loaded all five required FS examples without 403/CAPTCHA/login challenge and exposed stable exact-card identities and displayed rating vectors. | VERIFIED_HISTORY: the first Edge restart hypothesis did not reload the unpacked helper, the direct Reload-control hypothesis found no Reload control while the extension was off, and two AppActivate-based UI Automation attempts failed; those failed hypotheses are not being retried. | VERIFIED_HISTORY: Edge currently recognizes Simple Evaluator Browser Watch 1.4.13 from the exact installed folder but reports the extension off with an explicit Developer-mode requirement.
- RESEARCH: OBSERVED: the exact on-disk single-worktab implementation gap is closed; the remaining gap is browser-runtime activation plus physical acceptance, not scoring, catalog identity, or another product redesign. | OBSERVED: ordinary-chat Remote Desktop Commander can still inspect the exact Edge extension surface but current UI mutation/foreground execution is blocked or unreliable on this surface, while the persistent Windows worker already provides the sanctioned GitHub-inbox -> Gateway -> Broker execution path. | OBSERVED: scripts/pancake_local_control.py supports a fixed symbolic inbox registry with mutating actions authorized individually through SOPDecisionGateway and ControlledToolBroker; extending that registry avoids arbitrary shell exposure and does not bypass the control architecture. | INFERENCE supported by the live control architecture: moving the bounded browser acceptance handler into the durable worker is the narrowest legitimate route to finish physical acceptance without handing the debugging loop to the user.
- CAPABILITIES: OBSERVED: revision-19 Gateway/Broker is healthy and successfully executed the exact one-file watch.js repair with preimage/candidate hash checks, backup, post-hash verification, syntax validation and protected-state verification. | OBSERVED: the durable GitHub-inbox worker runs in the authorized Windows environment and already executes registered symbolic mutations through its own SOPDecisionGateway -> ControlledToolBroker. | OBSERVED: the staged revision-20 worker adds exactly one fixed mutating symbolic action, complete_simple_single_worktab_acceptance, backed by a repository-controlled handler that contains no arbitrary command/user input surface and fails closed on ambiguous UI identity. | OBSERVED: the staged handler verifies installed 1.4.13 hashes and protected state, uses exact Edge/UI Automation evidence to identify Developer mode, requires one reusable CFB.FAN work tab, measures rendered-page dwell against persisted exact-card observations, preserves the persistent rate-limit lock, restarts via the dynamic-port launcher, and marks release acceptance only after physical checks pass.

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
Deploy the revision-20 durable GitHub-inbox worker extension and execute its fixed complete_simple_single_worktab_acceptance action through SOPDecisionGateway -> ControlledToolBroker. The action must preserve both denied raw-request locks and the persistent RATE_LIMITED value-probe lock, activate the already-installed Browser Helper 1.4.13 without touching source authentication, physically prove one reusable CFB.FAN work tab with the minimum five-second rendered-page dwell and exact-card price persistence, restart through the accepted dynamic-port launcher, and return verified evidence before the authority is advanced again. Do not ask the user to test while this durable route remains executable.

## Remaining executable work
- Publish and merge the tested revision-20 worker/authority change that registers complete_simple_single_worktab_acceptance as a fixed mutating GitHub-inbox action.
- Rebind the durable Windows worker to revision 20 and verify the exact new worker bytes, READY health, clean product branch, and control self-test.
- Submit one bounded revision-20 control request for complete_simple_single_worktab_acceptance and let the durable worker execute it through SOPDecisionGateway -> ControlledToolBroker.
- Verify the action evidence: live Browser Helper 1.4.13, exact one-tab rendered-page observations with minimum five-second dwell, exact-card price persistence, saved-watch serialization, fail-closed protections, protected state, tab hygiene, and dynamic-port restart persistence.
- Advance the authority only with the verified physical-acceptance receipt, synchronize the durable worker again, and then hand the installed Simple Evaluator to the user for normal product acceptance if no executable technical debugging remains.

## Completion rule
A commit, test, CI run, PR, package, screenshot, or progress report is only a checkpoint.
Continue until the user-facing objective is verified, executable work is exhausted, or one genuine external action remains.
