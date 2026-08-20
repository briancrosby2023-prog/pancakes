# OP-X-016 Historical TE Validation

Frozen coefficients only; no refit. Ranking accuracy is the primary decision measure. Raw-score/OVR residuals and MAE are diagnostic because these ranking models are not asserted to reproduce displayed OVR exactly. TE-MODEL-004 is a non-production prior.

## CFB25

Population: 542 TE; scored: 542; excluded: 0.

| Model | N | Pairs | Correct | Inversions | Ties | Accuracy | Spearman | MAE | Gate |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| TE-MODEL-001 v1.1 (Gritty Possession) | 201 | 19426 | 19413 | 13 | 0 | 99.9331% | 0.999069 | 5.9253 | PASS |
| TE-MODEL-003 v1.1 (Physical Route Runner) | 0 | 0 | 0 | 0 | 0 | n/a | n/a | n/a | INSUFFICIENT EVIDENCE |
| TE-MODEL-004 v1.1 (Pure Blocker) | 162 | 12218 | 11873 | 338 | 7 | 97.2320% | 0.981811 | 7.8130 | PASS |
| TE-MODEL-006 v1.3 (Vertical Threat) | 179 | 15464 | 15391 | 73 | 0 | 99.5279% | 0.998318 | 6.6722 | PASS |

## CFB26

Population: 657 TE; scored: 657; excluded: 0.

| Model | N | Pairs | Correct | Inversions | Ties | Accuracy | Spearman | MAE | Gate |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| TE-MODEL-001 v1.1 (Gritty Possession) | 67 | 2137 | 2116 | 21 | 0 | 99.0173% | 0.995605 | 4.6672 | PASS |
| TE-MODEL-003 v1.1 (Physical Route Runner) | 403 | 78439 | 78295 | 144 | 0 | 99.8164% | 0.998992 | 4.3415 | PASS |
| TE-MODEL-004 v1.1 (Pure Blocker) | 63 | 1798 | 1794 | 4 | 0 | 99.7775% | 0.994030 | 2.9352 | PASS |
| TE-MODEL-006 v1.3 (Vertical Threat) | 124 | 7342 | 7328 | 13 | 1 | 99.8229% | 0.998115 | 4.6331 | PASS |

## Cross-season decision

- TE-MODEL-001 v1.1 (Gritty Possession): **DURABLE PASS**
- TE-MODEL-003 v1.1 (Physical Route Runner): **INSUFFICIENT CROSS-SEASON EVIDENCE**
- TE-MODEL-004 v1.1 (Pure Blocker): **DURABLE PASS**
- TE-MODEL-006 v1.3 (Vertical Threat): **DURABLE PASS**

## Residual and failure interpretation

The machine-readable results include five-point OVR bands, missing-attribute patterns, the ten worst inversions, and the ten OVR-transition clusters with the most inversions for every season/model. Cross-season pooled comparisons are reported separately from within-season aggregate counts because season-to-season score calibration shifts can create inversions that do not affect either season's validation gate.
