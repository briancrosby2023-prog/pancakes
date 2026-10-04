# Operation Pancake — Authoritative Handoff

State revision: 43
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
- MAP: OBSERVED: long-lived branch/runtime is Revision 34 at 7a9df794 with OP-CATALOG-001 IN_PROGRESS and normal rendered search REQUIRED_NEXT. | OBSERVED: current acceptance source still contains direct stored-player acquisition and installed background scheduler still navigates queued source URLs. | OBSERVED: Revision-35 acceptance issue #83 is terminal with EVIDENCE_GAP before runtime installation. | OBSERVED: Revision-36 acceptance issue #85 is terminal after reaching the registered action but before any installed runtime postimage write. | OBSERVED: Revision-37 acceptance issue #88 is terminal after atomic background.js replacement failed; rollback restored every exact preimage and worker/server health. | OBSERVED: Revision-38 acceptance issue #90 is terminal after runtime postimages installed but Browser Helper runtime stayed 1.4.13 instead of expected 1.4.14; rollback restored exact preimages. | OBSERVED: Revision-40 issue #94 is terminal at exact Reload lookup; rollback restored exact prepatch runtime hashes, 2 watches, 130 observations, persistent RATE_LIMITED and READY Revision-40 worker. | OBSERVED: Revision-41 acceptance issue #96 is terminal after Helper 1.4.14 activation and normal-search navigation, with no exact-card observation within 90 seconds; rollback restored protected state. | OBSERVED: Clean HEAD 89e3d505 authority Revision 42 OP-CATALOG-001, preflight PASS, all acceptance false. Live gateway health READY matches. Next-action text predates terminal issue98; reconcile with newer checkpoint while retaining route and every lock.
- HISTORY: VERIFIED_HISTORY: issue #80 and prior listed acceptance issues are terminal and must not be replayed. | VERIFIED_HISTORY: October 2-3 accepted workflow requires normal rendered CFB.FAN search for searches and price checks; denied raw routes, scoring, exact-card and persistent RATE_LIMITED locks remain unchanged. | VERIFIED_HISTORY: r19 proved process restart/--load-extension did not reload changed unpacked-extension bytes; successful recovery required an explicit unpacked-extension Reload action. | VERIFIED_HISTORY: issue #94 must not be replayed; Revision-40 exact Reload selector and prior Revision-35/36/37/38 fixes remain selected. | VERIFIED_HISTORY: issue #96 must not be replayed; Revision-41 extension-root/Reload activation, Revision-38 in-place writes, Revision-37 canonical blobs and normal rendered search remain selected. | VERIFIED_HISTORY: Issue98 terminal FAILED after exact Jaleel #prices market-parsed NO_LISTING. User forbids replay of 98/99. Prepared search-readiness r43 invalidated and must remain unexecuted. All accepted and rejected locks retained.
- RESEARCH: OBSERVED: rendered CFB27 Players controls are f_name, f_overall__gte, f_overall__lte and one visible Apply Filters control. | OBSERVED: normal rendered search for Jaleel Skinner returned two 81 OVR cards, Core Rare 27-2002557 and Platinum Rare 27-9002557, proving name+OVR alone is ambiguous. | OBSERVED: selecting the rendered exact Core Rare result opened the correct exact-card page; after >=5-second dwell the player-local PRICES control class sub-nav__link js-scroll-link exposed PlayStation Live Auctions. | OBSERVED: exact result identity can fail closed by comparing the rendered result href to queued source_url while never navigating to that stored URL. | OBSERVED: verify_installed_stop_conditions ran before patch_installed_runtime but required Revision-35 postimage tokens, proving the failure is harness ordering rather than normal-search runtime behavior. | OBSERVED: issue #85 repository postimage drift is Windows line-ending conversion: working-tree server.py SHA 8e3a9980... with 1,934 CRLF versus canonical Git blob SHA bc0582bf... with zero CRLF, exactly equal to the frozen expected postimage. | OBSERVED: issue #88 failed specifically on os.replace(background.js.r35.tmp, background.js) with WinError 5; no helper postimage was accepted. | OBSERVED: current Edge 153 extension details UI for fgocmjlihbapenekkflcofdjmdodmboe exposes Developer mode, Extension on and Remove but no Reload button, so the historical r19 details-surface Reload selector is stale. | OBSERVED: current Edge 153 extensions root exposes exactly one enabled Reload Button; its ListItem ancestor contains Simple Evaluator Browser Watch, version 1.4.13, Unpacked extension and exact ID fgocmjlihbapenekkflcofdjmdodmboe. | OBSERVED: exact foreground-focused address-bar SetValue/Enter of edge://extensions/ leaves Edge on edge://extensions/?id=fgocmjlihbapenekkflcofdjmdodmboe; polling for >10 seconds shows zero root Reload controls. | OBSERVED: invoking the exact enabled Installed extensions hyperlink changes the URL to edge://extensions and exposes one enabled Reload control. | OBSERVED: on the resulting root page, the unchanged Revision-40 exact matcher returns exactly one Reload whose ListItem contains Simple Evaluator Browser Watch and exact extension ID fgocmjlihbapenekkflcofdjmdodmboe. | OBSERVED: operational events during issue #96 show Edge Helper 1.4.14 version_matches=true before the observation timeout, proving extension Reload/activation succeeded. | OBSERVED: Edge history for the issue #96 window records /27/players/#simple-evaluator-worktab and canonical /players/#simple-evaluator-worktab at the same visit time, with no exact-card URL afterward. | OBSERVED: direct physical navigation to https://cfb.fan/27/players/#simple-evaluator-worktab ends at https://cfb.fan/players/#simple-evaluator-worktab. | OBSERVED: Helper 1.4.14 isNormalSearchPage() returns true only for /27/players/, so driveNormalSearch() is skipped on the observed canonical /players/ route. | OBSERVED: process_payload replaces state with only schema updated_at observations watches; record_browser_observation uses its returned state. watch.js catches sendObservation without page diagnostic. Isolated recorded function and HTTP evidence persisted copied observations 130 to131. Exact live exception still unknown; no search behavior correction justified.
- CAPABILITIES: OBSERVED: Browser Helper content scripts match https://cfb.fan/*, so they run on /27/players/ and exact-card pages. | OBSERVED: exact Edge Extension on TogglePattern can reload the unpacked helper without restarting the browser. | OBSERVED: saved-watch queue already provides card_id/name/ovr/program/source_url; Revision-35 server postimage adds source_url/program to active value-probe status. | OBSERVED: exact Revision-35 runtime postimages pass node --check / server py_compile and can be installed/rolled back transactionally by exact hashes. | OBSERVED: Revision-36 can separate prepatch legacy stop checks from postpatch normal-search stop checks without changing any Revision-35 runtime postimage bytes. | OBSERVED: local git show HEAD:runtime/simple_evaluator/server.py returns the exact canonical frozen postimage bytes independent of Windows working-tree line-ending conversion. | OBSERVED: RELEASE.json/background.js/watch.js/manifest.json each opens r+b successfully with no byte/hash change; background.js is owner FullControl, Archive, not read-only. | OBSERVED: the exact controlled Edge PID/window remains available for read-only UI Automation inspection of edge://extensions/ root without user action. | OBSERVED: the exact current Reload Button supports both ScrollItemPattern and InvokePattern; it can be selected fail-closed by exact extension card identity without proximity or enable toggling. | OBSERVED: existing open_extensions_root_and_snapshot already performs the proven fail-closed Installed extensions hyperlink navigation and can be reused without new selector/proximity logic. | OBSERVED: the correction is bounded to watch.js canonical-route recognition plus helper identity/hash updates; background scheduler, server routing, exact-card selection, persistence, scoring and protected locks remain unchanged. | OBSERVED: Desktop Commander allowance restored in authority. Python -B read-only preflight PASS. Existing SOPDecisionGateway strict typed evidence, authority guard and ControlledToolBroker available. Use recorded current model decision as in prior authorized executors; mutations confined to registered handler. | OBSERVED: two behavioral regressions RED on Revision42 and GREEN after bounded server preservation and watch.js diagnostic correction; Node syntax PASS.

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
- revision-27 bounded self-recovery of the controlled Edge helper window followed by same-tab Developer-mode activation and queue return
- revision-28 bounded exact Installed extensions readiness polling with Developer-mode AlreadyOn preservation
- normal rendered CFB.FAN site search -> exact-card selection -> >=5-second dwell -> player-level Prices/Live Auctions -> observation persistence

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
- reject-issue64-replay: Replay issue #64 or depend on an already-open controlled Edge helper window without materially new evidence.
- reject-issue66-replay: Replay issue #66 or replace the exact Installed extensions condition with an unbounded/generic delay.
- reject-issue69-replay: Replay issue #69 or retry WScript.Shell.AppActivate by PID/title without materially new evidence.

## Next action
Deploy only the validated Revision43 observation-integrity correction through SOPDecisionGateway -> ControlledToolBroker, then run one fresh full single-worktab acceptance. Preserve protected value_probe_rate_limit/value_probe_status on browser-observation writes and publish exact sendObservation exception through existing durable heartbeat diagnostics. No acquisition/search behavior changes. Revision42 reached exact Jaleel #prices and parsed NO_LISTING; copied function/HTTP persistence 130->131 is verified. Issues98/99 are terminal and must not be replayed; prepared search-readiness r43 is invalidated and must remain unexecuted. Preserve every accepted/rejected lock, exact identity, normal rendered search, one tab, >=5-second dwell, >=120-second cadence, persistent RATE_LIMITED and unchanged scoring. Adapt only from fresh exact evidence and continue catalog acceptance criteria.

## Remaining executable work
- Publish deploy and validate bounded Revision43 integrity/diagnostic correction.
- Run one fresh full acceptance, adapt from exact evidence.
- Complete OP-CATALOG-001 catalog import/revalidation criteria.

## Completion rule
A commit, test, CI run, PR, package, screenshot, or progress report is only a checkpoint.
Continue until the user-facing objective is verified, executable work is exhausted, or one genuine external action remains.
