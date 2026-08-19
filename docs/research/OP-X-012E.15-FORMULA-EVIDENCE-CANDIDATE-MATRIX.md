# OP-X-012E.15 — Formula Evidence & Candidate Matrix

Status: ACTIVE SCIENTIFIC RECONSTRUCTION

This matrix records what is currently supported without inventing unexecuted exact-OVR accuracy.

| Family | Population / evidence | Hypothesis A | Hypothesis B | Current discrimination | Status | Prediction readiness |
| --- | --- | --- | --- | --- | --- | --- |
| Center / blocking | C = 315 canonical cards; historical Center weights recovered; Jeff Saturday supplies 22 independent 1-OVR transitions | Frozen Madden Center weights + calibration transfer directly | Structural weights partially transfer but CFB27 uses different thresholds/calibration and/or archetype logic | Frozen absolute Madden calibration is contradicted on all 22 Saturday transitions; direction of weighted movement remains compatible. Same-OVR Alpha evidence also shows very large variation in defensive/non-center ratings, supporting exclusion of obvious non-blocking noise. | A: REJECTED as absolute implementation. B: SURVIVES. | NOT YET MEASURED on 315-card exact OVR |
| TE | TE = 512 canonical cards; four native archetypes; recovered Madden-architecture priors | Archetype-specific Madden-derived receiving/blocking architecture substantially survives | CFB27 TE OVR is better explained by a new/shared generic TE score independent of native archetype | Historical blind cross-OVR ordering: Gritty Possession 82/83 (98.8%); Vertical Threat 124/133 (93.2%, partially falsified); Physical Route Runner 365/365 (100%); Pure Blocker insufficient sample. This strongly favors retaining archetype-specific priors for current Alpha validation rather than pooling immediately. These are ranking results, NOT 512-card exact-OVR accuracy. | A: SURVIVES strongly for GP/PRR, WEAKENED for VT, UNRESOLVED for blocker. B: WEAKENED. | Exact OVR NOT YET MEASURED |
| Coverage (CB/FS/SS) | CB 863 + FS 400 + SS 406 = 1,669 canonical cards | Shared coverage/recognition component with position/archetype scaling | Fully position-specific formulas with little reusable coverage architecture | E.14 explicitly preserved shared vs position-scaled vs archetype-scaled alternatives; current evidence is sufficient for systematic same-OVR/adjacent-boundary mining but not yet sufficient to choose the architecture without executing the new miner. Large population makes this the highest-information defensive family. | A: SURVIVES. B: SURVIVES. | RESEARCH_REQUIRED / unmeasured |
| Front seven (DT/LB/EDGE) | DT 635 + MLB 456 + SAM 165 + WILL 364 + LE 401 + RE 409 = 2,430 canonical cards | Shared BSH/pass-rush component with role scaling | Position/archetype-specific pass-rush formulas | E.14 BSH family contains 2,601 eligible cards and 499 native position/archetype/OVR strata and explicitly retained shared, position-scaled and archetype-scaled alternatives. That is strong evidence for continued component-level discrimination, not for declaring one universal coefficient. | Both SURVIVE pending discrimination. | RESEARCH_REQUIRED / unmeasured |

## Center conclusions now supported

1. The frozen historical Center model is not the literal CFB27 absolute implementation: Jeff Saturday validation marks all 22 observed transitions contradicted under the Madden calibration.
2. The historical weight direction is not useless. All Saturday transitions move the weighted score positively, so the structural blocking prior remains a viable ranking/component hypothesis.
3. The highest-value Center experiment is therefore calibration/threshold/archetype discrimination on the 315 ordinary CFB27 Centers, not another attempt to prove the old absolute calibration perfect.

## TE conclusions now supported

1. Archetype-specific architecture has meaningful prior support. Pooling all TEs into one generic formula before testing the native archetypes would discard strong evidence.
2. Gritty Possession and Physical Route Runner are the strongest inherited ranking priors; Vertical Threat deserves targeted repair rather than wholesale rejection; Pure Blocker needs population evidence.
3. The recovered Madden priors identify different emphasis patterns: Possession emphasizes CIT/SRR/CTH/AWR; Vertical raises SPD/ACC/MRR/DRR; Blocking emphasizes RBK/RBF/RBP plus IBL/LBK/PBK. These are candidate structures, not CFB27 facts until Alpha validation.

## Defensive conclusions now supported

1. Coverage should be attacked as a component family across CB/FS/SS before assuming three unrelated formulas.
2. Front-seven BSH evidence already spans thousands of eligible observations and hundreds of native strata. The live alternatives are shared contribution vs position scaling vs archetype scaling.
3. CFB27-native SAM/WILL and edge taxonomy must remain intact during discrimination.

## New deterministic experiment

`cfb27_e15_multi_family.py` mines the canonical population for each priority position using two independent signals:

- within-archetype same-OVR rating spread;
- median rating movement across adjacent OVR boundaries.

Large fixed-OVR spread with weak boundary direction weakens a rating as a dominant OVR driver. Repeated positive adjacent-boundary movement strengthens it as a candidate driver. The method produces constraints, not causal proof or an accuracy claim.

## Accuracy statement

No new exact-OVR percentage is claimed here. The TE 98.8% / 93.2% / 100% figures are historical **pair-ordering** validation rates and must not be represented as current 512-card exact-OVR prediction accuracy.
