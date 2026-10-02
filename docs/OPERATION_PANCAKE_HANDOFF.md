# Operation Pancake — Authoritative Handoff

State revision: 19
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
- MAP: OBSERVED: revision 18 / 1fd712f2 is the live OP-CATALOG-001 authority and the durable Windows GitHub-inbox worker is READY on that exact head. | OBSERVED: the installed Simple Evaluator remains release 3T / 1.2.0 PRODUCTION_ACCEPTED with Browser Helper 1.4.12 and accepted dynamic-port startup. | OBSERVED: one normal connected-browser CFB.FAN tab successfully rendered Jordan Allen 91 FS, Ashlynd Barker 91 FS, Kingston Lopa 90 FS, Earl Little Jr. 90 FS, and Xavier Filsaime 90 FS with stable exact-card IDs and displayed rating vectors; no 403, CAPTCHA, or login/access challenge appeared on those rendered pages. | OBSERVED: the user exposed tab-clutter as a regression and requires one reusable CFB.FAN work tab with temporary tabs closed when work finishes.
- HISTORY: VERIFIED_HISTORY: the player-items raw request and historical CfbFanPublicAdapter raw public-page request each returned one-request HTTP 403 ACCESS_DENIAL and remain fail-closed with no retry or bypass. | VERIFIED_HISTORY: Browser Watch 1.4.12 and the Simple Evaluator dynamic-port runtime were physically accepted; accepted scoring models, watches, price identity, and protected state must remain intact. | OBSERVED: Browser Helper 1.4.12 already uses one value-price probe tab, navigates that same tab with chrome.tabs.update after VALUE_PROBE_NAVIGATION_DELAY_MS=5000, and closes the probe tab on completion or 429. | OBSERVED: normal saved card watches still use per-tab alarm/reload behavior and the UI opens new source tabs, which conflicts with the newly explicit single-work-tab requirement.
- RESEARCH: OBSERVED: normal rendered CFB.FAN exact-card pages are reachable through the connected browser for all five required FS examples while the two denied raw HTTP acquisition clients remain denied. | EXTERNAL_RESEARCH: Stormstrike terms currently restrict automated scraping/access except where expressly permitted; therefore the rendered-browser path is not promoted to a provider-authorized current-complete catalog source and may not be used to evade the denied clients. | OBSERVED: the installed browser helper reads visible PlayStation Live Auctions DOM state, stops on HTTP 429 or user-action-required preflight, and records only exact-card URL-matched FOUND/NO_LISTING observations. | INFERENCE supported by installed code and browser evidence: the immediate product gap is shared-tab orchestration/tab hygiene for already accepted rendered browser price observations, not a need to alter scoring or retry denied catalog clients.
- CAPABILITIES: OBSERVED: Browser Helper 1.4.12 has Chromium tabs permission and already performs same-tab five-second value-probe navigation and tab removal. | OBSERVED: server.py already owns exact-card URL matching, bounded value-probe batches, progress/terminal states, observation persistence, alerts, and 429 fail-closed behavior. | OBSERVED: Simple-Evaluator.html already provides Top 5, Best Value, Price Watch, Training Watch, exact-card identity, and progress UI; the current Update Prices path is a bounded comparison-card batch rather than a full 9,000-card scan. | OBSERVED: the Gateway/ControlledToolBroker, rollback-capable Windows mutation handlers, accepted launcher, and physical acceptance probes are available for a bounded installed-product hotfix.

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
Implement and physically verify the bounded single-tab normal-rendered CFB.FAN browser work queue in the accepted Simple Evaluator runtime for known exact-card page and price observations only: reuse one work tab, preserve a minimum five-second navigation dwell, validate exact card identity, and stop on 403/429/CAPTCHA/login/access challenge or unexpected page state. Preserve both denied raw-request locks, provider-email rejection, unchanged scoring, exact-card persistence, and catalog authorization limits. Complete installed-app acceptance before asking the user to test.

## Remaining executable work
- Integrate a single reusable rendered CFB.FAN work-tab queue for user-started exact-card price checks and saved Price Watch cycles using the existing five-second navigation primitive.
- Remove app-driven new-tab sprawl for exact-card browser checks and preserve stop-on-403/429/CAPTCHA/login/access-challenge behavior.
- Run focused internal tests and brokered installed-product deployment with rollback and protected-state preservation.
- Physically verify dynamic-port startup, Browser Helper behavior, exact-card price persistence, saved watches, tab hygiene, progress/terminal states, and restart persistence before user testing.
- Update the authority with verified product acceptance results and the next genuine catalog boundary.

## Completion rule
A commit, test, CI run, PR, package, screenshot, or progress report is only a checkpoint.
Continue until the user-facing objective is verified, executable work is exhausted, or one genuine external action remains.
