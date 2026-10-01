# Operation Pancake — Authoritative Handoff

State revision: 12
Status: BLOCKED
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
- HISTORY: The preserved catalog milestone requires CURRENT CATALOG ACQUISITION -> EXACT-CARD IMPORT -> RANKING ACCEPTANCE before Training Watch completion. | Installed baseline is 9,206 exact cards and is explicitly NOT current-complete. | The saved discovery artifact contains 9,233 records, only +27 versus installed, and its records are 2026-08-19 PARTIAL_LISTING_VECTOR evidence; it is not a current-complete scoring catalog. | September 28 checkpoint research already exhausted alternative catalog sources, preserved an unsent provider request, and required explicit approval before any external message, purchase, or account creation. | Accepted Chrome pricing, Browser Watch, dynamic-port behavior, OP-SIMPLE-002 physical acceptance, and scoring models must not be reopened without materially new evidence.
- RESEARCH: Current October 1 CFB.FAN public pages contain later exact-card versions, including Ashlynd Barker 91 FS and Kingston Lopa 90 FS, proving the installed/saved snapshot is stale. | The local 9,233 discovery does not contain the required Jordan Allen 91, Ashlynd Barker 91, Kingston Lopa 90, Earl Little Jr. 90, or Xavier Filsaime 90 acceptance versions. | Stormstrike Terms last updated 2026-05-13 prohibit automated means such as bots, scrapers, or crawlers except where expressly permitted, and prohibit automated scraping/copying in Acceptable Use. | CFB27 Nation Terms last updated 2026-06-25 prohibit scraping or republishing content without permission; its public GitHub repository is documentation-only under CC BY 4.0 and contains no card dataset. | EA Season 3 pages provide only a bounded official player-item subset, not a current-complete exact-card catalog with all required scoring attributes. | No authorized current-complete structured catalog feed/export or provider permission was found after current web, Library, repository, and installed-state research.
- CAPABILITIES: Desktop Commander is online as bootstrap/recovery transport; the durable Gateway/Broker is synchronized at revision 11 and READY. | The installed evaluator already has version-aware catalog import/persistence infrastructure and accepted exact-card Chrome pricing behavior. | Web/GitHub/Library research can verify sources but cannot create provider permission. | No authorized provider feed/configuration or current-complete local export is available. | External provider outreach is technically possible after approval, but history explicitly prohibits sending it before user approval.

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

## Accepted — do not reopen without materially new evidence
- accepted-sop-order: Operation Pancake SOP order is MAP -> HISTORY -> RESEARCH -> CAPABILITIES -> PLAN -> EXECUTE -> ADAPT -> VERIFY -> UPDATE MAP -> CONTINUE.
- accepted-dynamic-port: Simple Evaluator uses the accepted dynamic localhost-port startup architecture; no fixed port is canonical.
- accepted-browser-watch: Original 3U Browser Watch production acceptance is closed and must not be reopened without a new regression.
- accepted-two-layer-control-standard: Operation Pancake behavior control requires both a ChatGPT instruction layer and a fail-closed controlled execution layer; neither alone satisfies the objective.
- accepted-provider-contact-approval: External provider messages, paid access, or account creation for catalog acquisition require explicit user approval before execution.

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

## Next action
Obtain explicit user approval to send the preserved Stormstrike/CFB.FAN data-access request to business@stormstrike.gg; do not send before approval.

## Remaining executable work
- None

## Completion rule
A commit, test, CI run, PR, package, screenshot, or progress report is only a checkpoint.
Continue until the user-facing objective is verified, executable work is exhausted, or one genuine external action remains.
