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

The repository now includes an OpenAI Responses API decision transport.
Direct ChatGPT web conversations still cannot be intercepted by repository
code; consequential Pancake decisions must go through this gateway.

The transport reads an API key from OPENAI_API_KEY or, on Windows, from
%LOCALAPPDATA%\\SimpleEvaluator\\openai_api_key.txt. The key is never written
to the repository or decision records. The default decision model is
gpt-5.6-sol and can be overridden with PANCAKE_OPENAI_MODEL.

If no key is available, the gateway remains fail-closed and returns
MODEL_TRANSPORT_REQUIRED. The API call uses structured JSON output, high
reasoning effort, no built-in web/tool calls, and a 1,200-output-token cap.

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

CI validates the OpenAI transport request/response boundary without making a
paid API call. A live-model acceptance run remains separate and must not be
claimed until the locally stored key is present and the gateway is exercised
against the real Responses API.

## OP-CONTROL-002 hardening

The production gateway now requires typed evidence. Contradictory trusted fact keys fail before the decision provider is called. Mutation decisions must cite trusted implementation fact keys. The gateway records obstacle classification, alternatives, selected reason, user-action requirement, and remaining executable routes.

A persistent hypothesis ledger blocks evidence-free retries and invalidates a theory after two failed attempts. A user-test gate prevents returning work to the user while executable technical routes remain.

`operation_pancake.tool_broker.ControlledToolBroker` is the mechanical execution boundary for model-controlled tools. Read-only tools can be exposed during preflight. Mutation tools require a current decision that was explicitly approved as a mutation decision.

The repository still cannot hard-intercept an arbitrary ordinary ChatGPT turn. The behavioral layer is therefore provided by `docs/CHATGPT_PROJECT_INSTRUCTIONS.md` plus `docs/CHATGPT_GLOBAL_CUSTOM_INSTRUCTION.md`, and completion is prohibited until installation and cross-surface acceptance are verified.
