# Operation Pancake decision gate

## Purpose

This controller turns MAP → HISTORY → RESEARCH → CAPABILITIES into a fail-closed
precondition for consequential Operation Pancake decisions.

It is intentionally separate from prompt instructions. The model does not get
called until deterministic preflight succeeds.

## Runtime boundary

- Controller: `operation_pancake.sop_gateway.SOPDecisionGateway`
- Runtime records: `.operation_pancake/decisions/*.json`
- Schema: `schemas/sop_decision.schema.json`
- Shared policy: `operation_pancake.sop_policy`
- Repository enforcement: existing required `sop-gate` GitHub check

## Consequential decision flow

1. Load authoritative project state (MAP).
2. Recover relevant prior attempts/decisions (HISTORY).
3. Complete required research (RESEARCH).
4. Inventory actually available capabilities (CAPABILITIES).
5. Run deterministic preflight.
6. Only then invoke a decision provider.
7. Persist the structured decision packet.
8. Before an action executes, verify that it is listed in `allowed_actions`.
9. If the project-state fingerprint changed, reject the action and require a
   new preflight.
10. Repository changes still pass the downstream GitHub SOP gate.

## Model transport

The repository currently has a Google Gemini integration for screenshot
transcription, but no programmatic OpenAI/ChatGPT decision transport is
configured in this branch. Direct ChatGPT web conversations cannot be
intercepted by repository code.

The gateway therefore fails closed when no decision provider is configured.
A live OpenAI-backed decision path requires an explicitly authorized
programmatic credential before it can be enabled. The gate itself does not
create accounts, buy API access, or spend API credits.

## Acceptance

The regression suite proves:

- Missing MAP blocks before the provider is called.
- Missing HISTORY blocks before the provider is called.
- Missing RESEARCH blocks before the provider is called.
- Missing CAPABILITIES blocks before the provider is called.
- Unapproved actions are rejected.
- Changed project state invalidates an earlier decision.
- Completion is rejected while executable work remains.
- The 9,206-card database scenario is blocked when HISTORY is absent.
- Restoring HISTORY allows the intended trace-original-acquisition action and
  still blocks unrelated manual/provider-email work.

A local live-model acceptance run remains separate from CI and must not be
claimed until an authorized model transport is configured and exercised.
