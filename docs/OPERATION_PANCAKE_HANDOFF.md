# Operation Pancake — Authoritative Handoff

State revision: 23
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
- MAP: OBSERVED: revision 22 / e8173bcc is the live OP-CATALOG-001 authority and the durable Windows GitHub-inbox worker is READY on that exact head with worker SHA-256 4d2c0862. | OBSERVED: fresh immutable issue #53 was accepted and reached the revision-22 physical-acceptance action, then terminated before browser mutation with ModuleNotFoundError: No module named 'server'. | OBSERVED: all installed Browser Helper 1.4.13 single-worktab files remain at their accepted candidate hashes and the persistent RATE_LIMITED lock remains protected.
- HISTORY: VERIFIED_HISTORY: revision 21 fixed the durable runner importlib.util loader defect; revision 22 fixed the stale action authority pin; both are deployed and verified. | VERIFIED_HISTORY: failed issues #49, #51 and #53 are terminal and may not be replayed. | VERIFIED_HISTORY: both denied raw CFB.FAN acquisition routes remain fail-closed; provider-email remains rejected; scoring, exact-card identity and protected-state locks remain unchanged.
- RESEARCH: OBSERVED: pancake_single_worktab_action.load_launch_module executes Simple Evaluator launch.py with importlib.util.spec_from_file_location without putting the Simple Evaluator APP directory on sys.path. | OBSERVED: installed Simple Evaluator launch.py imports sibling module server at top level; without APP on sys.path that exact import raises ModuleNotFoundError before browser mutation. | OBSERVED: the narrow correction is to expose APP on sys.path only while launch.py executes, then remove the temporary path, with a focused sibling-import regression test. | INFERENCE supported by the exact receipt and source inspection: browser automation logic, source access, scoring, identity, persistence and market-lock behavior do not need to change.
- CAPABILITIES: OBSERVED: revision-22 Gateway/Broker, immutable GitHub-inbox transport and durable worker are healthy and processed issue #53 to the physical-action loader boundary. | OBSERVED: the repository can stage a four-path revision-23 correction: physical-action launch loader/revision pin, focused regression tests, authority state and canonical handoff. | OBSERVED: bounded patch, exact publication/merge and rollback-capable runtime-rebind mechanisms remain available.

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
Deploy the revision-23 single-worktab launch-loader sibling-import fix, then submit one fresh immutable complete_simple_single_worktab_acceptance request through the READY durable GitHub-inbox -> SOPDecisionGateway -> ControlledToolBroker route. Request single-worktab-accept-r22-final-e8173bcc is terminal and must not be replayed. Revision 23 fixes only the verified load_launch_module failure to resolve Simple Evaluator sibling imports while loading launch.py, plus updates the action revision pin, focused regression coverage and authority/handoff bookkeeping; browser behavior, source access, scoring, exact-card identity, protected state and locks remain unchanged.

## Remaining executable work
- Create, validate, publish and merge the minimal revision-23 single-worktab launch-loader sibling-import repair with focused regression coverage.
- Rebind the Windows durable worker to revision 23 and verify READY health, clean product branch and control validation.
- Create one fresh immutable GitHub control issue for complete_simple_single_worktab_acceptance and let the revision-23 worker execute it through Gateway/Broker.
- Verify the physical-acceptance receipt: live Browser Helper 1.4.13, one reusable CFB.FAN work tab, minimum five-second rendered-page dwell, exact-card price persistence, saved-watch serialization, fail-closed protections, protected state, tab hygiene and dynamic-port restart persistence.
- Advance the authority only with verified physical-acceptance evidence, synchronize the durable worker, then hand Simple Evaluator to the user for normal product acceptance only if no executable technical debugging remains.

## Completion rule
A commit, test, CI run, PR, package, screenshot, or progress report is only a checkpoint.
Continue until the user-facing objective is verified, executable work is exhausted, or one genuine external action remains.
