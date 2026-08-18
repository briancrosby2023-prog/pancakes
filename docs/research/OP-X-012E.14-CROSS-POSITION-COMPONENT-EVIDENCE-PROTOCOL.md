# OP-X-012E.14 — Cross-Position Component Evidence Protocol

Status: EXECUTION STANDARD / E.15 BLOCKED

This protocol operationalizes the corrected E.14 work order. No component verdict may be promoted merely because code runs or an in-sample association is strong.

## Target component families

- BSH: Safety vs LB vs EDGE
- PRC: Safety vs CB vs LB
- SPD: CB vs Safety vs LB
- PMV: MIKE vs EDGE vs DT
- FMV: MIKE vs EDGE vs DT

## Required experiment cycle

For every family, the reproducible analysis must: (1) build and fingerprint the exact eligible population; (2) stratify native position × archetype × OVR; (3) enumerate scientifically comparable same-OVR contrasts; (4) enumerate adjacent-OVR boundary contrasts; (5) construct matched cross-position experiments; (6) quantify imbalance/confounding in the remaining rating vector; (7) compare at least two plausible explanations; (8) run leave-one-position-out validation where identifiable; (9) run archetype-group holdouts where sample size permits; (10) rerun materially different matching/caliper/control specifications; (11) exhaustively identify strongest contradictory cards/pairs; (12) run negative controls through the identical pipeline; (13) separate repeated observations from independent replication families; and (14) retain failures/contradictions rather than averaging them away.

## Candidate specifications

At minimum each surviving conclusion must be tested under three materially different reasonable specifications:

1. Strict: same OVR; exact native-position target contrast; archetype exact/compatible; standardized remaining-vector distance <= 0.50 SD; no replacement.
2. Moderate: same OVR or justified adjacent-boundary contrast; archetype controlled categorically; distance <= 0.75 SD; no replacement.
3. Broad robustness: OVR difference <= 1 with explicit OVR adjustment; archetype fixed effects; distance <= 1.00 SD; inverse-distance weighting.

The implementation may add specifications but must not silently drop these because they are inconvenient. Every spec records candidate count, accepted matches, balance before/after, effect estimate, uncertainty, and counterexample rate.

## Alternative hypotheses

Every component must compare at least:

- H_shared: one cross-position component relationship after OVR/archetype/vector controls.
- H_position: position-specific slope/intercept or position × component interaction.
- H_archetype: archetype-specific slope/intercept or archetype × component interaction.

Where sample size supports it, compare nested predictive models on grouped holdouts using MAE/RMSE and signed calibration error; report delta performance rather than relying on in-sample fit. A simpler shared model survives only if position/archetype alternatives do not materially improve held-out error and sensitivity runs agree.

## Confounding

The target component is excluded from the matching/control vector. Remaining numeric ratings are standardized within the eligible population. Report standardized mean differences and aggregate distance. Flag a match family as confounded when residual imbalance remains large enough that the target contrast cannot be isolated. Do not interpret matching success as causal proof.

## Holdouts

No in-sample result is called validated. Use grouped holdouts that prevent leakage of essentially repeated comparisons. Preferred order: leave-one-native-position-out, archetype holdout, then OVR-band holdout when the first two are not identifiable. Record explicitly when a requested holdout is impossible and why.

## Negative controls

Each component analysis must run the same candidate generation, matching, model comparison, sensitivity and holdout machinery on predeclared non-target rating/position combinations. Report the empirical false-positive strength distribution. A shared-component conclusion cannot be accepted when target evidence is not distinguishable from negative-control relationships under the same acceptance rule.

## Falsification and counterexamples

Search the complete eligible population, not only accepted matches, for observations/pairs with maximum contradiction to the leading hypothesis. Persist card identifiers, native positions, archetypes, OVR, target component values, remaining-vector distance, predicted contrast, observed contrast and residual. Inspect at least the strongest contradictions per independent replication family.

## Replication

Assign replication_group IDs before aggregation. Pairs sharing the same card, same position/archetype/OVR cell, or trivially reusing the same boundary are not independent replication. Report raw observations separately from independent replication-family count.

## Verdict rules

Allowed final labels: SHARED COMPONENT; POSITION-SCALED COMPONENT; ARCHETYPE-SCALED COMPONENT; POSITION-SPECIFIC; ARCHETYPE-SPECIFIC; CONFOUNDED; FALSIFIED; INSUFFICIENT EVIDENCE.

Any conclusion that materially changes sign, magnitude, ranking of hypotheses, or acceptance state under reasonable specifications is marked UNSTABLE and cannot be promoted as a stable shared/scaled verdict. Contradictory holdouts override attractive in-sample averages. Insufficient sample size is evidence uncertainty, not permission to extrapolate.

## Required artifact family

The E.14 runner must emit machine-readable and human-readable artifacts covering: population manifest/fingerprint; experiment inventory; BSH/PRC/SPD/PMV/FMV matrices; alternative-hypothesis comparisons; holdouts; sensitivity; negative controls; strongest counterexamples; replication groups; uncertainty; final verdict matrix; plus run metadata sufficient to reproduce the analysis from the canonical CFB27 population.

## Quality gate

Tests must verify deterministic population fingerprinting, exhaustive candidate accounting, target exclusion from confound vectors, grouped holdout isolation, sensitivity-spec execution, negative-control parity, counterexample extraction, replication de-duplication, unstable-verdict downgrade, and E.15 non-execution. Run Ruff and the complete relevant pytest suite, push the E.14 commit, and verify definitive GitHub Actions status before handoff.
