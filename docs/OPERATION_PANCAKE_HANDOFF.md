# Operation Pancake — Authoritative Handoff

State revision: 16
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
- MAP: Long-lived revision 15 / 5f88f934421b3b36123b2cb6a8c48c1c8a762e41 is deployed and the durable worker reports READY for OP-CATALOG-001. | The authority-required one-request probe of https://cfb.fan/api/27/player-items/?ids=110000178 returned HTTP 403 at 2026-10-02T03:43:56Z and correctly stopped without retry. | The failed structured-endpoint probe blocks the existing bulk-endpoint delta path but does not establish that every historically used public CFB.FAN acquisition path is unavailable.
- HISTORY: The repository contains the earlier CfbFanPublicAdapter and run_cfb_fan_controlled_pilot.py historical path for fixed public player pages. | The historical controlled pilot fetched six fixed public player pages sequentially at <=12 requests/minute with no API calls and recorded full_rating_vector_acquisition=GOOD. | The public-player-page parser extracts exact season card ID, player identity, position, overall, program, archetype, team/date when present, and displayed ratings; cards with ratings are marked COMPLETE. | The global listing parser remains explicitly partial and is not itself a substitute for a complete rating vector.
- RESEARCH: OBSERVED: the revision-15 bulk player-items probe received HTTP 403 and persisted ACCESS_DENIAL evidence outside the repository. | OBSERVED: run_cfb27_population_v3.py labels listing summaries PARTIAL_LISTING_VECTOR and explicitly does not claim a full vector. | VERIFIED_HISTORY: the older public-player-page adapter previously acquired complete rating vectors without using the API. | UNKNOWN: current reachability and current parser compatibility of the public player-page route; one bounded probe can resolve that evidence gap without retry or bypass.
- CAPABILITIES: CfbFanPublicAdapter remains present with public HTML parsing and a 12 requests/minute access policy. | Saved listing records retain stable public player-page source_reference URLs containing exact 27-* card IDs. | A fixed-purpose one-page probe can use the historical public-page method, validate exact identity/ratings, persist evidence, and stop on denial without invoking the blocked player-items API. | Version-aware import, conflict checks, unchanged scoring models, and accepted Chrome exact-card pricing remain available only after a valid current delta is acquired.

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
- bounded reachability probe of the existing public unauthenticated CFB.FAN player-items endpoint
- existing conservative 12-requests/minute 50-card bulk adapter
- existing version-aware CFB27 delta refresh with hashed provenance and conflict checks
- existing CfbFanPublicAdapter public-player-page parser and fixed-page acquisition path
- one bounded public-player-page reachability/validation probe with no API and no retry
- saved exact-card public player-page source_reference URLs from established listing discovery

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

## Next action
Run one bounded reachability/validation probe of one known exact-card CFB.FAN public player page using the already-existing CfbFanPublicAdapter. Use one unauthenticated request with the historical public-page method, no API call and no retry; validate exact-card identity and a nonempty/full displayed rating vector. Stop on explicit denial, authentication/CAPTCHA/access-control challenge, HTTP 429, unexpected page shape, identity conflict, or incomplete ratings; do not bypass or evade. If the probe passes, reconcile the existing listing-discovery URLs with this historical public-page adapter before authorizing any broader delta refresh.

## Remaining executable work
- catalog-existing-public-player-page-probe
- If the public-player-page probe passes, reconcile the existing listing-discovery URLs with CfbFanPublicAdapter and authorize only the smallest validated delta-acquisition step needed for current exact-card vectors.
- If the public-player-page probe fails with denial/challenge/429 or incompatible/incomplete data, classify the observed failure and update the authority without bypass or repeat.

## Completion rule
A commit, test, CI run, PR, package, screenshot, or progress report is only a checkpoint.
Continue until the user-facing objective is verified, executable work is exhausted, or one genuine external action remains.
