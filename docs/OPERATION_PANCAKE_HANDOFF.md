# Operation Pancake — Authoritative Handoff

State revision: 18
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
- MAP: Revision 17 / 86541a7cb20cd508030794309edde59f40a52da0 was physically synchronized to the Windows durable worker through DECISION_ALLOWED runtime-rebind-r17-86541a7cb20cd508; the worker reported READY for OP-CATALOG-001 with unchanged SHA-256 37defb2b. | Post-rebind local verification found HEAD 86541a7cb20cd508030794309edde59f40a52da0, a clean worktree, control validation PASS, preflight PASS, canonical handoff output, and the runner self-test embedded in the install validation PASS. | Revision 15's player-items probe and revision 16's historical public-player-page probe each returned one-request HTTP 403 ACCESS_DENIAL with no retry. | Both established live acquisition routes remain fail-closed; the runtime synchronization does not reopen catalog collection.
- HISTORY: The bulk player-items route historically completed 190 batches / 9,390 requested and returned / zero failures and a successful September 8 delta. | The distinct public-player-page route historically fetched six fixed pages at <=12 requests/minute with no API calls and full_rating_vector_acquisition=GOOD. | The repository's listing parser is intentionally PARTIAL_LISTING_VECTOR and cannot replace the complete structured/detail vectors required by scoring. | Earlier OP-CATALOG-001 research already exhausted installed-state/cache recovery, CFB27 Nation, official EA, xpay AgentFeed, and public GitHub alternatives for a current-complete structured exact-card catalog.
- RESEARCH: OBSERVED: player-items exact-card request returned HTTP 403 from the Windows operational host. | OBSERVED: public player-page exact-card request through the historical CfbFanPublicAdapter also returned HTTP 403 from the same host. | EXTERNAL_RESEARCH: current CFB.FAN player/listing content remains externally indexed and current, including a September 27 Jordan Allen 91 FS page with a full displayed rating vector and a current players listing; the evidence does not support a general site outage. | INFERENCE supported by the two independent local denials plus external visibility: the blocker is current access for Operation Pancake's established acquisition clients, not absence of current CFB.FAN data. | No accepted route permits changing client identity or transport characteristics to evade the observed 403 responses.
- CAPABILITIES: The durable Gateway/Broker worker is synchronized to revision 17 with unchanged worker bytes and remains READY on the GitHub-inbox transport. | The historical bulk and public-page parsers remain intact, but both corresponding live request paths are currently denied by observed HTTP 403 responses. | Version-aware import, unchanged scoring models, conflict validation, and accepted Chrome exact-card pricing remain ready but are gated on acquiring a valid current exact-card delta. | No immediate non-bypass technical collection route is supported by current evidence.

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
Do not retry the denied player-items or public-player-page acquisition requests and do not change client identity, authentication, cookies, headers, proxy, or rate behavior to obtain access. Resume catalog acquisition only after materially new technical evidence establishes that one of the established routes is no longer denied, or a current structured exact-card source becomes available through a non-bypass route. Re-run MAP -> HISTORY -> RESEARCH -> CAPABILITIES before any new collection.

## Remaining executable work
- None

## Completion rule
A commit, test, CI run, PR, package, screenshot, or progress report is only a checkpoint.
Continue until the user-facing objective is verified, executable work is exhausted, or one genuine external action remains.
