# Operation Pancake — Authoritative Handoff

State revision: 10
Status: IN_PROGRESS
Mission ID: OP-SIMPLE-002

## Mission
Repair Player Evaluator Update All Prices value-probe lifecycle so 429, source failure, helper silence, or restart cannot leave an indefinite RUNNING batch or falsely report completion.

## Mandatory SOP
MAP → HISTORY → RESEARCH → CAPABILITIES → PLAN → EXECUTE → ADAPT → VERIFY → UPDATE MAP → CONTINUE

## Start-of-session rule
Read `docs/OPERATION_PANCAKE_CONTROL_STATE.json` first and validate it before making a consequential Pancake decision.
Do not let the newest obstacle replace the recorded mission.

## Preflight evidence
- MAP: OP-CONTROL-002 is COMPLETE on long-lived revision 9 / 88b5009674686ee4050bb2ab75b0a1410a185b98 and the durable worker reports revision 9 READY. | Library checkpoint Operation-Pancake-OP-SIMPLE-002-checkpoint.json records OP-SIMPLE-002 as frozen at physical acceptance: r60 rate-limit path passed and restart/state-preservation remained. | Current Windows RELEASE.json reports 3T / 1.2.0 / helper 1.4.12 with status R61_RATE_LIMIT_UI_FIX_PENDING_PHYSICAL_ACCEPTANCE.
- HISTORY: The OP-SIMPLE-002 checkpoint objective is to prevent indefinite RUNNING or false completion on 429/source/helper/restart failures. | r60 restored the persistent 429 lock, explicit terminal states, bounded per-card timeout, startup recovery of abandoned RUNNING metadata, and protected-state persistence. | r61 is an internally verified UI-only follow-up: Update All Prices remains actionable during a persistent 429 lock so the existing client guard can explain the lock; server value-probe state machine, Browser Watch 1.4.12, Price Watch, Training Watch, and saved state are unchanged. | Original Browser Watch production acceptance is closed/accepted and must not be reopened without a new regression. | Training Watch engineering is complete; unattended current-price collection still requires an expressly authorized provider source and is not part of this restart acceptance.
- RESEARCH: Current Windows app-state reports value_probe_status=RATE_LIMITED with persistent_lock=true, not RUNNING, after the prior 429 failure. | Current app-state retains two user Price Watches and current launch.py --check reports deployment_ready=true. | Browser helper heartbeat is current, Edge-based, version 1.4.12, and version_matches=true. | No evidence supports clearing the persistent market-source lock or starting another bulk refresh as part of restart acceptance.
- CAPABILITIES: Desktop Commander is online and explicitly authorized as Windows execution transport. | The current accepted Simple Evaluator dynamic-port launcher/check path is available; fixed localhost port assumptions remain prohibited. | The Operation Pancake revision-9 Gateway/Broker is READY for consequential authority/product execution decisions. | Work and Codex remain unnecessary and are excluded by current user directive.

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
Restart the current installed Simple Evaluator once through the existing accepted dynamic-port launcher/start path without clearing the persistent market-source lock or starting another bulk refresh; then verify restart recovery and protected-state preservation.

## Remaining executable work
- Capture the current protected-state baseline without clearing the market-source lock.
- Restart Simple Evaluator through the existing accepted dynamic-port launcher/start path.
- Verify no zombie value-probe RUNNING/temp watch returns and persistent RATE_LIMITED lock survives.
- Verify saved prices, user Price Watches, Player Evaluator Top 5, r61 lock feedback, Training Watch, and Browser Watch remain intact.
- Record physical acceptance and close OP-SIMPLE-002 only if every bounded criterion passes.

## Completion rule
A commit, test, CI run, PR, package, screenshot, or progress report is only a checkpoint.
Continue until the user-facing objective is verified, executable work is exhausted, or one genuine external action remains.
