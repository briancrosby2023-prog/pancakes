# Operation Pancake — Authoritative Handoff

State revision: 14
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
- MAP: Long-lived revision 13 / 08d8247c4ec6d270f5b784e2bbeb42fe22ec3f45 is deployed for OP-CATALOG-001 with the authoritative history-route guard active. | The durable Windows worker is READY on revision 13 / 08d8247c with worker SHA-256 37defb2bb4fac8bae2fedef4e6b1a1bbf39592a2ed1667672adee7c42b460f65. | Live post-merge authority validation, preflight, canonical handoff, runner self-test, and 62/62 focused controls pass; the stale provider-email route is blocked mechanically.
- HISTORY: Revision 13 corrected the stale-history defect and required catalog-historical-bulk-reconcile before any new source action. | The historical bulk program used public CFB.FAN listing pages plus /api/27/player-items/ in 50-card batches, preserved raw hashes/provenance, and performed no authentication, CAPTCHA, access-control, or rate-limit bypass. | The saved full-vector checkpoint contains 190 successful batches, 9,390 requested and 9,390 returned card IDs, zero failures, across 2026-08-14 through 2026-09-08. | The September 8 delta refresh ended at 9,233 exact cards with 14/14 missing IDs accepted, zero missing IDs, zero duplicates, and zero old IDs lost. | Installed Simple Evaluator remains at 9,206 cards and lacks the required newer Jordan Allen 91, Ashlynd Barker 91, Kingston Lopa 90, Earl Little Jr. 90, and Xavier Filsaime 90 versions.
- RESEARCH: Stormstrike Terms updated 2026-05-13 predate the August-September historical acquisitions and prohibit automated means such as bots, scrapers, or crawlers except where expressly permitted; historical successful unauthenticated access does not establish permission. | Current CFB.FAN public pages are reachable and current, but no public API documentation, export control, or express automation permission was found. | CFB27 Nation's public Player Cards Browser currently exposes zero official CUT item rows, its public repository contains no card dataset/source implementation, and its terms prohibit scraping/republishing without permission. | Official EA sources expose base-game ratings, editorial CUT player-item/program pages, and personal EA account-data download, but no current-complete structured CFB27 CUT catalog API/export was found. | An xpay AgentFeed listing exists for CFB.FAN but identifies a detected RSS/news feed with weekly T+3d delivery; it does not establish access to the CUT card database. | Local installed cards.json is 9,206 cards and stale. Normal Chrome history contains newer card/listing visits, including Kingston Lopa 90, but a bounded scan of 9,085 Chrome cache files / 548,567,485 bytes found no retained current card/API payload; the only Kingston hit was an analytics URL containing the page address. | Global public GitHub searches found no reusable current CFB27 CUT JSON/CSV dataset or public implementation of the historical CFB.FAN bulk endpoint.
- CAPABILITIES: Repository, Library, current web research, installed evaluator state, browser history/cache, GitHub alternatives, CFB27 Nation, official EA sources, and the recovered historical acquisition program were all inspected read-only. | No live CFB.FAN catalog/API collection request was issued during reconciliation. | No provider message, purchase, account creation, scoring mutation, market-lock clear, Browser Watch reopening, or evaluator product mutation occurred. | No legitimate executable technical route currently supplies a permitted current-complete structured CUT exact-card catalog or delta.

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
Await materially new evidence of an expressly permitted current structured CFB27 CUT catalog, delta, export, or feed. If such evidence appears, verify its permission, coverage, stable exact-card identity, and required ratings before import. Do not resume automated CFB.FAN/Stormstrike collection, use the rejected provider-email route, or ask the user to manually assemble the catalog.

## Remaining executable work
- None

## Completion rule
A commit, test, CI run, PR, package, screenshot, or progress report is only a checkpoint.
Continue until the user-facing objective is verified, executable work is exhausted, or one genuine external action remains.
