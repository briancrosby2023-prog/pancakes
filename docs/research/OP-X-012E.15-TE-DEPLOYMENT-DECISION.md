# OP-X-012E.15 — TE Deployment Decision

Status: GM RANKING READY / EXACT OVR CALIBRATION OPEN

## Decision

Do not reopen the three validated TE archetype ranking models merely because E.15 exact displayed-OVR calibration is unfinished.

The historical TE work and the Phase III inheritance artifact independently preserve strong cross-OVR ordering performance for the three major TE archetypes. Under Operation Pancake's decision-quality policy, that evidence is already useful for ranking and Moneyball comparisons. Exact-OVR prediction is a separate question and remains unmeasured on the current 512-card Alpha TE population.

## Reconciled evidence

### Gritty Possession

Frozen model: `TE-MODEL-001 v1.1 — M19 Possession weights`.

Blind cross-OVR ordering: 82/83 = 98.8% in the original holdout record. Phase III records cross-OVR accuracy 0.9897959184 and the same 82/83 independent validation, with one narrow inversion (Jalen Hoffman 81 vs Christian Bentancur 80).

Classification: `GM_READY_FOR_RANKING`; `EXACT_OVR_NOT_MEASURED`.

### Physical Route Runner

Frozen model: `TE-MODEL-003 v1.1 — 71% VT + 29% Possession`.

Blind unique-profile ordering: 304/304 = 100%. Phase III also records cross-OVR accuracy 1.0 and no observed cross-OVR inversions.

Classification: `GM_READY_FOR_RANKING`; `EXACT_OVR_NOT_MEASURED`.

### Vertical Threat

Original frozen M19 VT holdout produced 124/133 = 93.2%, establishing systematic but incomplete inheritance. The later frozen `TE-MODEL-006 v1.3 — M19 VT +2 LBK +3 IBL` is recorded in Phase III at 0.9857142857 cross-OVR accuracy with 17/17 independent validation and two retained isolated inversions.

Classification: `GM_READY_FOR_RANKING` under the current >=95% practical policy, with a prospective watch flag; `EXACT_OVR_NOT_MEASURED`.

### Pure Blocker

Historical structured evidence had only one Pure Blocker card, so no defensible pairwise formula was validated there.

Classification: `RESEARCH_REQUIRED` until the current Alpha population establishes sufficient Pure Blocker support.

## What the percentages mean

The 98.8%, 100%, and 98.57% figures above are **cross-OVR ordering/ranking performance**, not exact displayed-OVR prediction accuracy. They answer a GM-relevant question: whether the model tends to rank a higher-OVR TE above a lower-OVR TE using the candidate hidden-score architecture.

They do not establish that the model predicts the exact integer OVR on the 512-card Alpha population.

## E.15 consequence

TE should no longer be treated as wholly unsolved. Three major archetypes have sufficiently strong ranking evidence to feed GM/Moneyball comparisons now while E.15 separately tests exact OVR calibration and current-population stability. This avoids wasting the phase chasing perfection that is not required for useful roster decisions.

The highest-value TE work is now:

1. prospective/current-Alpha validation of the frozen three-archetype ranking models;
2. exact-OVR calibration only if it materially improves GM decisions;
3. Pure Blocker reconstruction if the 512-card Alpha population contains enough examples;
4. preservation of Core/Platinum duplicate identities during validation to prevent leakage.

No new accuracy measurement is claimed by this decision artifact; it reconciles already measured historical evidence and defines its permitted GM use.
