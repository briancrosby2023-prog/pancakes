# Operation Pancake — Authoritative Handoff

State revision: 15
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
- MAP: Long-lived revision 14 / 4fd202b262a5f4debc467cd46cfc1036dcaf19f3 is deployed and READY for OP-CATALOG-001. | Revision 14 is BLOCKED solely because it converted a terms interpretation into an external permission dependency. | The user has explicitly directed Operation Pancake to continue the same acquisition method previously used rather than invent a new route.
- HISTORY: The historical CFB.FAN bulk adapter uses public unauthenticated GET https://cfb.fan/api/27/player-items/?ids=... with 50-card batches and a 12 requests/minute ceiling. | Saved provenance records 190 successful batches, 9,390 requested and 9,390 returned exact-card IDs, zero failures, from August 14 through September 8. | The September 8 delta refresh advanced the canonical population from 9,219 to 9,233 exact cards with 14/14 additions accepted, zero duplicates, zero old IDs lost, and no conflicts. | The historical method used no authentication bypass, CAPTCHA bypass, access-control bypass, or rate-limit evasion.
- RESEARCH: No technical evidence establishes that the public endpoint or historical acquisition method was withdrawn or changed after the successful September 8 refresh. | Revision 14's external-dependency conclusion depended on an interpretation of provider terms rather than a source denial, endpoint failure, access-control challenge, or account enforcement event. | Current reachability of the exact established endpoint remains an executable evidence gap and can be tested with a single bounded request before any broader refresh.
- CAPABILITIES: The existing CfbFanBulkAdapter and refresh_cfb27_canonical_delta.py implementation remain present and unchanged. | The route can fail closed on HTTP/access denial and can stop rather than evade 429 or access-control responses. | Version-aware import, provenance hashing, conflict checks, and the accepted Chrome exact-card pricing path remain available after acquisition.

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

## Accepted — do not reopen without materially new evidence
- accepted-sop-order: Operation Pancake SOP order is MAP -> HISTORY -> RESEARCH -> CAPABILITIES -> PLAN -> EXECUTE -> ADAPT -> VERIFY -> UPDATE MAP -> CONTINUE.
- accepted-dynamic-port: Simple Evaluator uses the accepted dynamic localhost-port startup architecture; no fixed port is canonical.
- accepted-browser-watch: Original 3U Browser Watch production acceptance is closed and must not be reopened without a new regression.
- accepted-two-layer-control-standard: Operation Pancake behavior control requires both a ChatGPT instruction layer and a fail-closed controlled execution layer; neither alone satisfies the objective.
- accepted-provider-contact-approval: External provider messages, paid access, or account creation for catalog acquisition require explicit user approval before execution.
- accepted-authoritative-history-route-guard: Consequential strict decisions must independently load structured REQUIRED_NEXT/REJECTED route constraints from the project authority; caller-supplied history cannot omit or override them.
- accepted-existing-catalog-acquisition-route: OP-CATALOG-001 may use the already-established public unauthenticated CFB.FAN acquisition route with its existing conservative batching, provenance, validation, and fail-closed behavior; this does not authorize new bypass or evasion methods.

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
Run one bounded reachability probe of the existing public unauthenticated CFB.FAN player-items endpoint using the already-established acquisition method. If it returns normally and exact-card identity/ratings validate, resume the existing delta-refresh pipeline with the same batching and conservative rate limits. Stop on explicit denial, authentication/CAPTCHA/access-control challenge, or HTTP 429; do not bypass or evade.

## Remaining executable work
- catalog-existing-acquisition-probe
- If the probe passes, run the existing exact-card delta refresh and continue the remaining OP-CATALOG-001 acceptance criteria.

## Completion rule
A commit, test, CI run, PR, package, screenshot, or progress report is only a checkpoint.
Continue until the user-facing objective is verified, executable work is exhausted, or one genuine external action remains.
