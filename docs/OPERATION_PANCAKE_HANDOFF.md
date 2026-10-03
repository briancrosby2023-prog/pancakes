# Operation Pancake — Authoritative Handoff

State revision: 24
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
- MAP: OBSERVED: revision 23 / 48cee181 is the live OP-CATALOG-001 authority and the durable Windows GitHub-inbox worker is READY on that exact head with worker SHA-256 4d2c0862. | OBSERVED: issue #58 received DECISION_ALLOWED for complete_simple_single_worktab_acceptance on catalog-rendered-browser-single-tab-integration and then failed closed inside physical acceptance with EVIDENCE_GAP 'expected one Developer mode label; observed 0' before any Developer-mode toggle. | OBSERVED: the controlled Edge process PID 52280 remains on the Simple Evaluator Browser Watch 1.4.13 extension-details surface at edge://extensions, with Extension off and the visible message 'To use this extension, turn on developer mode.' | OBSERVED: installed release 3T / 1.2.0 remains FROZEN_PENDING_PHYSICAL_ACCEPTANCE with all seven expected 1.4.13 file hashes present, but live helper status is still 1.4.12/version_matches=false and deployment_ready=false; no live activation or acceptance mutation has occurred.
- HISTORY: VERIFIED_HISTORY: revisions 21, 22 and 23 fixed the durable-loader import, stale authority pin and Simple Evaluator sibling-import loader defects respectively and are deployed through the controlled patch/publish/merge/rebind path. | VERIFIED_HISTORY: issues #49, #51, #53, #55, #56 and #58 are terminal and may not be replayed; issue #57 was a read-only decision-provider recovery probe and produced a valid DECISION_ALLOWED packet. | VERIFIED_HISTORY: both denied raw CFB.FAN acquisition routes remain fail-closed; provider-email remains rejected; scoring, exact-card identity, protected state and the persistent RATE_LIMITED value-probe lock remain unchanged. | VERIFIED_HISTORY: the historical workstation PASS is Browser Helper 1.4.9 and the October 1 production report is Browser Helper 1.4.12, so neither artifact can satisfy the pending 1.4.13 acceptance.
- RESEARCH: OBSERVED: current Windows UI Automation on the verified Edge extension-details surface exposes exactly one enabled 'Installed extensions' Hyperlink supporting InvokePattern and also a generic enabled Back button. | OBSERVED: revision-23 open_extensions_root_and_snapshot uses the generic Back button and immediately expects one exact Developer mode label; issue #58 observed zero labels after that navigation, so that navigation hypothesis failed. | EXTERNAL_RESEARCH: Microsoft Edge extension guidance places the Developer mode control on the Manage extensions / edge://extensions management page, consistent with navigating via the explicit Installed extensions breadcrumb/link. | OBSERVED: the narrow materially-new implementation hypothesis is to invoke the exact enabled Installed extensions Hyperlink, then perform the existing fail-closed Developer-mode label/toggle scan; no browser pricing, source access, scoring, persistence or identity logic needs to change. | OBSERVED: installed server.py stores one shared browser-helper heartbeat and unconditionally overwrites it on every Chromium heartbeat; therefore a stale Chrome 1.4.12 runtime can clobber a valid Edge 1.4.13 heartbeat and make readiness oscillate. | OBSERVED: installed server.py can self-write PRODUCTION_WORKSTATION_ACCEPTANCE_3T.json after one watched card has two expected-version observations >=120 seconds apart, while the revision-24 physical action can write RELEASE.json PRODUCTION_ACCEPTED without proving the full user completion outline. Both are premature acceptance paths. | OBSERVED: candidate-only isolation tests prove an exact server preimage bd2be607... -> postimage f073dfe2... hardening can preserve a fresh compatible 1.4.13 heartbeat against later stale 1.4.12 writers and suppress automatic narrow acceptance without changing scoring, market parsing, source access, watches, or the 429 lock. | OBSERVED: candidate-only evaluator checks pass deterministically across all 19 supported positions with Platinum Rare excluded; the installed 9,206-card catalog still has zero exact matches for Jordan Allen 91 FS, Ashlynd Barker 91 FS, Kingston Lopa 90 FS, Earl Little Jr. 90 FS, and Xavier Filsaime 90 FS, so the catalog mission remains IN_PROGRESS even if Browser Helper acceptance passes.
- CAPABILITIES: OBSERVED: revision-23 Gateway/Broker, immutable GitHub-inbox transport and durable worker are healthy; issue #58 reached the physical Browser Helper action under DECISION_ALLOWED. | OBSERVED: the repository can stage a four-path revision-24 correction: physical-acceptance management-page navigation/revision pin, focused regression tests, authority state and canonical handoff. | OBSERVED: bounded patch, exact publication/merge and rollback-capable runtime-rebind mechanisms remain available; no direct browser or installed-product mutation is required to create the correction. | OBSERVED: complete_simple_single_worktab_acceptance is already a registered mutating durable-worker action, so the exact installed-server acceptance hardening can remain inside the existing Gateway/Broker-controlled acceptance transaction with rollback rather than inventing a new mutation surface. | OBSERVED: the plan-backed Gateway currently returns subscription_sharing_usage_limit_exceeded for both default Sol and the supported Luna model override; no sanctioned cached/offline continuation exists and the separate API transport is not configured.

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
Deploy the superseding revision-24 single-worktab repair through a fresh Gateway/Broker authorization. Revision 24 must combine the exact Installed extensions Hyperlink navigation correction with the now-observed acceptance-boundary hardening: transactionally patch the exact installed server preimage so a live 1.4.13 heartbeat cannot be clobbered by stale 1.4.12 Chromium heartbeats and the server cannot self-write a narrow production PASS; then execute one fresh immutable complete_simple_single_worktab_acceptance request proving one reusable CFB.FAN tab, >=5-second dwell, exact-card persistence, a real >=120-second saved-watch cadence, fail-closed stop conditions, protected-state preservation, all-19-position evaluator determinism/Platinum Rare exclusion, explicit five-FS installed identity checks, browser cleanup, pending-state restart persistence, full transactional acceptance write, and a second restart that reports PRODUCTION_ACCEPTED. Do not replay terminal issue #58, retry denied raw HTTP routes, clear the persistent 429 lock, change scoring, or ask the user to test while this route remains executable.

## Remaining executable work
- Validate the superseding revision-24 candidate against an isolated copy of the live revision-23 repository, including authority/handoff checks and focused/full control tests.
- Obtain one fresh Gateway/Broker authorization for the superseding revision-24 bounded repository patch; do not reuse the prior navigation-only authorization.
- Publish/merge the exact authorized revision-24 head, rebind the durable worker, and verify READY/clean revision-24 health.
- Issue one fresh immutable complete_simple_single_worktab_acceptance request and let the revision-24 worker execute the transactional installed-server hardening plus full 1.4.13 physical acceptance.
- Verify live 1.4.13 remains stable despite stale Chromium heartbeats; exactly one CFB.FAN work tab; >=5-second dwell; >=120-second cadence; exact-card persistence; fail-closed stops; protected state; evaluator checks; five-FS installed identity checks; two restart proofs; cleanup; and comprehensive acceptance artifact.
- Continue OP-CATALOG-001 after Browser Helper acceptance because the five required newer FS versions are still not imported and all eight catalog mission acceptance criteria remain false.

## Completion rule
A commit, test, CI run, PR, package, screenshot, or progress report is only a checkpoint.
Continue until the user-facing objective is verified, executable work is exhausted, or one genuine external action remains.
