# Operation Pancake coding-agent instructions

Before any consequential Operation Pancake coding, Git, packaging, recovery, or architecture decision:

1. Read `docs/OPERATION_PANCAKE_CONTROL_STATE.json`.
2. Run `python scripts/pancake_control.py preflight`.
3. Treat the active mission and accepted/rejected locks as controlling.
4. Follow MAP → HISTORY → RESEARCH → CAPABILITIES → PLAN → EXECUTE → ADAPT → VERIFY → UPDATE MAP → CONTINUE.
5. A failed tool is an ADAPT event, not a new mission.
6. Do not reopen accepted work or retry rejected paths without materially new evidence recorded against the lock ID.
7. Do not declare BLOCKED while executable routes remain.
8. Do not declare COMPLETE because tests, CI, a PR, package, or checkpoint passed.
9. After consequential work, update the authority, regenerate `docs/OPERATION_PANCAKE_HANDOFF.md`, and continue while executable work remains.
10. Mission-specific state such as `docs/SOP_STATE.json` is subordinate evidence and cannot replace the project-wide authority.

Do not use Desktop Commander until its allowance is restored. Do not use DigitalOcean for Operation Pancake. Do not hard-code the Simple Evaluator port or invent replacement state/launcher/runtime systems without evidence and an authorized decision record.

## OP-CONTROL-002 cross-surface enforcement

For any consequential change, classify evidence as OBSERVED, VERIFIED_HISTORY, EXTERNAL_RESEARCH, INFERENCE, or UNKNOWN. Do not mutate from UNKNOWN/INFERENCE-only reasoning. Stop on contradictory trusted facts.

Do not retry a failed implementation hypothesis without materially new evidence. Two failures invalidate that hypothesis. Do not ask the user to test while executable technical routes remain.

When the controlled Pancake runtime/tool broker is available, all consequential mutation must pass through it. Do not invoke an exposed direct mutation handler as a shortcut around the gateway.
