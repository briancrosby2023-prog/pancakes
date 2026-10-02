# Operation Pancake — Authoritative Handoff

State revision: 13
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
- MAP: Long-lived revision 11 / eacf147918554a29bca94f76277670779559fec9 is COMPLETE for OP-SIMPLE-002 with all seven criteria passed. | The durable Windows control worker was broker-rebound on 2026-10-01 and now reports revision 11, exact head eacf147918554a29bca94f76277670779559fec9, OP-SIMPLE-002, READY, with worker SHA-256 ee5d8319bc0c7997f070e42d32a59941fa684433944563889d9f2a4b5320d59f unchanged. | Installed Simple Evaluator remains 3T / 1.2.0 PRODUCTION_ACCEPTED with Browser Helper 1.4.12 and the protected persistent RATE_LIMITED 10/31 market lock.
- HISTORY: OP-SIMPLE-002 revision 11 remains COMPLETE; revision 12 selected OP-CATALOG-001 but incorrectly reopened an older provider-email approval branch. | Verified September 28 history records the user direction: Find another way; provider-email route not approved and not sent. | The later September 28 historical_bulk_acquisition_correction identified src/operation_pancake/acquisition/cfb_fan_bulk.py plus scripts/refresh_cfb27_canonical_delta.py as the actual saved bulk acquisition/refresh program. | That correction explicitly says the unsent provider request is not the only investigative path and requires continuing from the recovered acquisition program and provenance. | Installed baseline remains 9,206 exact cards; the saved September 8 canonical population is 9,233 and is not current-complete. | Accepted Chrome pricing, Browser Watch, dynamic-port behavior, OP-SIMPLE-002 physical acceptance, and scoring models remain closed absent regression.
- RESEARCH: The recovered bulk adapter uses the public CFB.FAN /api/27/player-items/ route, batches up to 50 IDs, records hashed raw JSON/provenance, and historically ran at 12 requests/minute. | The recovered delta refresh reconciles current listing discovery to canonical exact IDs and uses the bulk adapter only for missing IDs; the September 8 saved refresh reached 9,233 with zero missing IDs, duplicates, old IDs lost, or rejected conflicts. | Historical successful access alone does not establish current permission; current Stormstrike terms restrict automated access except where expressly permitted. | No evidence establishes that a new permission requirement arose after the successful saved acquisitions; the permitted-use basis and source reachability therefore remain an evidence gap to reconcile before any live collection. | The recovered adapter's generic retry behavior must not be used to evade an access-control or rate-limit response.
- CAPABILITIES: Desktop Commander is available as bootstrap/recovery transport and the durable Gateway/Broker is READY on revision 12. | The live repository contains the historical CFB27 bulk adapter, delta-refresh script, saved provenance reports, and version-aware evaluator catalog importer. | Read-only repository, Library, and current-source research can reconcile the historical acquisition path without user action or live collection. | Consequential mutations remain broker-only; provider messaging remains approval-gated if ever selected later.

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

## Accepted — do not reopen without materially new evidence
- accepted-sop-order: Operation Pancake SOP order is MAP -> HISTORY -> RESEARCH -> CAPABILITIES -> PLAN -> EXECUTE -> ADAPT -> VERIFY -> UPDATE MAP -> CONTINUE.
- accepted-dynamic-port: Simple Evaluator uses the accepted dynamic localhost-port startup architecture; no fixed port is canonical.
- accepted-browser-watch: Original 3U Browser Watch production acceptance is closed and must not be reopened without a new regression.
- accepted-two-layer-control-standard: Operation Pancake behavior control requires both a ChatGPT instruction layer and a fail-closed controlled execution layer; neither alone satisfies the objective.
- accepted-provider-contact-approval: External provider messages, paid access, or account creation for catalog acquisition require explicit user approval before execution.
- accepted-authoritative-history-route-guard: Consequential strict decisions must independently load structured REQUIRED_NEXT/REJECTED route constraints from the project authority; caller-supplied history cannot omit or override them.

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
- reject-prohibited-catalog-scraping: Automate collection from CFB.FAN/Stormstrike or scrape/republish CFB27 Nation without express permission.
- reject-provider-email-as-catalog-next-action: Treat the preserved Stormstrike/CFB.FAN provider-email request as the current or only next action for OP-CATALOG-001.

## Next action
Reconcile the recovered historical CFB27 bulk acquisition program, its provenance, current permitted-use basis, and source reachability; do not send a provider request or perform live collection until that read-only reconciliation is complete.

## Remaining executable work
- catalog-historical-bulk-reconcile
- After reconciliation, choose only an authority-permitted source acquisition route and continue OP-CATALOG-001.

## Completion rule
A commit, test, CI run, PR, package, screenshot, or progress report is only a checkpoint.
Continue until the user-facing objective is verified, executable work is exhausted, or one genuine external action remains.
