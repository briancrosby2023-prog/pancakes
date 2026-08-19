# OP-X-012E.15 — Formula Reconstruction & Model Discrimination Protocol

Status: ACTIVE

Starting checkpoint: `10297df6a580595e41321e275d0370888c6d72d9`

## Objective

Convert the validated CFB27 Alpha population and canonical E.14 cross-position evidence into reproducible position/archetype OVR formula candidates without reopening E.14 scientific work.

## Authoritative inputs

- `data/research/cfb27_alpha/readiness.json`
- `data/research/cfb27_e14/evidence_matrix.json`
- existing inheritance research under `data/research/cfb27_inheritance_phase*`
- existing center exact/practical validation artifacts

The Alpha population is 8,838 / 8,838. E.15 consumes established evidence; it does not regenerate E.14 merely to begin formula reconstruction.

## E.15 research contract

For each position/archetype with sufficient evidence:

1. Build a static-native candidate population using the existing Alpha eligibility policy.
2. Treat displayed OVR as the target and displayed ratings as candidate explanatory variables.
3. Use same-position, same-archetype, same-OVR natural experiments to eliminate or bound attributes that can vary substantially without changing OVR.
4. Use adjacent-OVR contrasts to identify attributes whose changes are consistent with crossing an OVR boundary.
5. Preserve archetype-specific hypotheses when evidence does not justify pooling archetypes.
6. Score candidate formulas on exact displayed-OVR agreement, absolute error, boundary consistency, and outlier count.
7. Test plausible rounding/quantization behavior separately from attribute weighting.
8. Preserve multiple surviving hypotheses when the evidence is underdetermined. Do not label a formula solved solely because it fits the training population.

## Required model outputs

Each evaluated position/archetype must record:

- eligible card count and OVR range;
- candidate attribute set;
- excluded/bounded attributes with evidence references;
- candidate weights or component structure;
- rounding/quantization rule;
- exact-OVR match count and rate;
- mean and maximum absolute OVR error;
- residual/outlier card IDs;
- natural-experiment contradictions;
- confidence classification: `EXACT`, `HIGH_CONFIDENCE`, `PROVISIONAL`, `UNDERDETERMINED`, or `REJECTED`.

## First-pass priority

Start with positions where prior research and Alpha natural experiments provide the strongest constraints. Center is the calibration position because exact/practical center validation already exists. Then expand to TE, CB, FS/SS, DT, and CFB27-native linebacker/edge groups as evidence supports them.

## Scientific guardrails

- Do not infer causality from simple correlation alone.
- Do not use dynamic/projected card states in native formula fitting.
- Do not silently normalize CFB27-native position labels into Madden/NFL aliases.
- Do not generalize Legendary/reset behavior to ordinary cards without independent evidence.
- Keep source evidence, extraction state, model inference, and GM recommendation layers distinct.
- A low-error regression is a candidate model, not proof of EA's implementation.

## Completion gate

E.15 is complete only when the repository contains a deterministic formula-reconstruction artifact and implementation that can reproduce its candidate-model metrics from canonical inputs, with tests covering model scoring, rounding behavior, evidence preservation, and deterministic output.

Current state: E.15 protocol established; implementation/model fitting remains active.
