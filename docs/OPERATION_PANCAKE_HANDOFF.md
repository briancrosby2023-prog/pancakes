# Operation Pancake — Authoritative Handoff

State revision: 3
Status: COMPLETE
Mission ID: OP-CONTROL-001

## Mission
Fix the overall Operation Pancake decision-making process so every consequential project decision follows MAP -> HISTORY -> RESEARCH -> CAPABILITIES -> PLAN -> EXECUTE -> ADAPT -> VERIFY -> UPDATE MAP -> CONTINUE across chats, tools, failures, handoffs, and future features.

## Mandatory SOP
MAP → HISTORY → RESEARCH → CAPABILITIES → PLAN → EXECUTE → ADAPT → VERIFY → UPDATE MAP → CONTINUE

## Start-of-session rule
Read `docs/OPERATION_PANCAKE_CONTROL_STATE.json` first and validate it before making a consequential Pancake decision.
Do not let the newest obstacle replace the recorded mission.

## Preflight evidence
- MAP: User clarified that the target is the overall Operation Pancake working process, not the Simple Evaluator gateway. | Current long-lived repository branch is product/c3po-clean-room-roster. | Existing docs/SOP_STATE.json is mission-specific and currently scoped to the r56 Simple Evaluator gateway, so it cannot be the sole project-wide authority.
- HISTORY: PR #11 incorrectly normalized Simple Evaluator to 127.0.0.1:8788 and added a replacement launcher; PR #12 reverted that after HISTORY recovered the accepted dynamic-port path. | An Opera connector failure was allowed to replace the active decision-control mission instead of being classified as a capability problem and adapted around. | Desktop Commander was repeatedly reconsidered after its allowance was exhausted despite an explicit no-retry directive. | Tests, PRs, packages, and browser checkpoints were repeatedly treated as if they completed the user-facing objective. | User has repeatedly required the SOP and project history to survive chat/mode handoffs.
- RESEARCH: The existing repository SOP gateway can mechanically gate requests routed through it but cannot intercept ordinary ChatGPT web turns. | The existing repository SOP validator already enforces evidence-backed stages for Git changes but is mission-specific and lacks project-wide mission/lock/handoff/blocker semantics. | A project-wide source of truth plus deterministic preflight/handoff validation can make repository/Codex work durable while remaining honest that ordinary ChatGPT still depends on consulting that source.
- CAPABILITIES: GitHub connector provides read/write access to the Pancake repository and protected PR workflow. | Files/Library provides authoritative historical checkpoints across prior chats. | Container/Python execution can validate new control logic before repository publication. | Desktop Commander remains excluded until its allowance is restored. | No authorized direct Windows shell/process channel is assumed in this chat. | Opera is a browser capability only and must never be treated as the project mission or sole decision-control mechanism.

## Available capabilities
- GitHub repository read/write and protected PR workflow
- Files/Library retrieval
- container/Python validation
- web research when current external facts materially affect a decision

## Accepted — do not reopen without materially new evidence
- accepted-sop-order: Operation Pancake SOP order is MAP -> HISTORY -> RESEARCH -> CAPABILITIES -> PLAN -> EXECUTE -> ADAPT -> VERIFY -> UPDATE MAP -> CONTINUE.
- accepted-dynamic-port: Simple Evaluator uses the accepted dynamic localhost-port startup architecture; no fixed port is canonical.
- accepted-browser-watch: Original 3U Browser Watch production acceptance is closed and must not be reopened without a new regression.

## Rejected/superseded — do not retry without materially new evidence
- reject-hardcoded-8788: Hard-code 127.0.0.1:8788 as the Simple Evaluator port.
- reject-replacement-launcher: Invent a replacement launcher/runtime merely because an existing component is inconvenient.
- reject-opera-mission-drift: Treat an Opera connector failure as a new mission or as proof the overall decision-control effort is blocked.
- reject-desktop-commander-retry: Retry or recheck Desktop Commander before its allowance is restored.
- reject-checkpoint-completion: Treat a test, commit, CI run, PR, package, screenshot, or intermediate checkpoint as completion while executable work remains.
- reject-feature-before-control: Resume Simple Evaluator/Price Watch/Training Watch feature work before the overall decision-process control mission is implemented and verified.

## Next action
complete

## Remaining executable work
- None

## Completion rule
A commit, test, CI run, PR, package, screenshot, or progress report is only a checkpoint.
Continue until the user-facing objective is verified, executable work is exhausted, or one genuine external action remains.
