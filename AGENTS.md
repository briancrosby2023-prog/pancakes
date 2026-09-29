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
