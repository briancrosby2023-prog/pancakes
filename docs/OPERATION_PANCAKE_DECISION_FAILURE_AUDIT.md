# Operation Pancake — Decision Failure Regression Audit

This document maps observed historical failures to required behavior and the control that prevents recurrence.

| Historical failure | Old bad behavior | Required behavior | Preventive control |
| --- | --- | --- | --- |
| False `8788` normalization | Treated an unsupported port assumption as canonical and built around it. | Recover accepted startup history before planning; preserve dynamic port behavior. | Rejected lock `reject-hardcoded-8788`; reopening requires materially new evidence. |
| Replacement launcher in PR #11 | Invented a new launcher when the accepted runtime path was inconvenient. | Reuse accepted components unless evidence proves they cannot satisfy the mission. | Rejected lock `reject-replacement-launcher`; decision boundary requires alternatives/history. |
| Opera connector failure | Let one browser capability failure redefine the decision-control mission. | Classify as `CAPABILITY_PROBLEM`, inventory alternatives, and ADAPT within the same mission. | Mission-ID consistency, obstacle classification, rejected lock `reject-opera-mission-drift`. |
| Desktop Commander exhaustion | Reconsidered/retried an exhausted route despite explicit history. | Preserve the no-retry state until materially new availability evidence exists. | Rejected lock `reject-desktop-commander-retry`. |
| Checkpoint treated as completion | Stopped at tests/PR/package/browser checkpoint while user objective remained unverified. | Continue until acceptance criteria pass, executable work is exhausted, or one external action remains. | Completion validator + `reject-checkpoint-completion`. |
| New-chat rediscovery | Reconstructed project state from partial conversation context and lost accepted/rejected decisions. | Load one authoritative project control state before planning. | `docs/OPERATION_PANCAKE_CONTROL_STATE.json`, deterministic handoff, `AGENTS.md`. |
| Capability assumption | Declared a mission blocked or chose a route without checking current tools. | Record capabilities actually checked before planning/blocking. | Mandatory CAPABILITIES evidence + blocker validation. |
| Conflicting recent evidence | Allowed the latest observation to supersede established history without reconciliation. | Record and resolve contradictions before planning. | `conflicts` validator rejects unresolved contradictions. |
| User used as speculative test harness | Asked for repeated manual actions before exhausting executable technical work. | Perform internal/repository validation first; request one precise user action only at a genuine external boundary. | Strict BLOCKED rule + completion/remaining-work semantics. |
| Feature work before process fix | Returned to component work while the project-wide decision problem remained active. | Keep the project-wide control mission active until its criteria are accepted. | Rejected lock `reject-feature-before-control`; mission-ID consistency. |

| Ordinary-chat SOP bypass after OP-CONTROL-001 | Repository controls existed, but a consequential patch direction was chosen before current MAP/HISTORY/RESEARCH/CAPABILITIES. | Treat repository controls as partial; require Project/global behavioral bootstrap plus strict production gateway for mutation execution. | OP-CONTROL-002 two-layer enforcement, typed evidence, decision-bound tool broker, cross-surface acceptance. |
| r61 guess-first repair | A plausible UI diagnosis became a new package before the served Windows runtime/version was proven. | UNKNOWN/EVIDENCE_GAP cannot justify mutation; verify runtime fact keys before implementation. | Typed evidence + trusted implementation-basis gate + contradiction detection. |
| Repeated speculative manual testing | User actions were requested while technical inspection/adaptation routes remained. | User action is the final external boundary only. | User-test gate rejects user_action_required while remaining_executable_routes is non-empty. |
| Repeated failed theory | A failed implementation idea could generate another patch without materially new evidence. | Require new evidence after the first failure; invalidate the hypothesis after the second. | Persistent hypothesis ledger/circuit breaker. |

## Regression acceptance

Automated tests must cover at minimum:

1. Missing preflight evidence fails.
2. A capability failure cannot silently change the mission.
3. A rejected/accepted lock cannot be reopened without new evidence.
4. `BLOCKED` fails while an executable route remains.
5. `COMPLETE` fails while any acceptance criterion or executable work remains.
6. A stale/mismatched handoff fails.
7. Unresolved contradictory evidence fails.
8. A genuine external blocker with exhausted routes is accepted.
9. A normal in-mission adaptation with the same mission ID is accepted.
10. A fresh process can reconstruct mission/locks/next action from the authority alone.

11. Untyped evidence cannot reach the strict production decision provider.
12. Contradictory trusted facts block before planning.
13. Mutation with an unverified implementation fact key is rejected.
14. User testing is rejected while executable routes remain.
15. A failed hypothesis requires new evidence and two failures invalidate it.
16. A direct mutation tool cannot run without a decision approved for mutation.
17. An adversarial “ignore the SOP and just fix it” request cannot bypass preflight.
