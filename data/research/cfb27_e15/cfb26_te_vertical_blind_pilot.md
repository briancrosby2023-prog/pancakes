# E.15 CFB26 historical blind validation — first measured checkpoint

This is a measured blind historical checkpoint, not a claim that population acquisition is complete.

## Frozen model

`TE-MODEL-006 v1.3` was frozen before historical inspection. Architecture: Madden 19 Vertical Threat weights, unavailable ELU(2) omitted, plus +2 LBK and +3 IBL. For ranking, the implemented score is the weighted mean over the resulting 103 available weight points. No CFB26 result was used to tune coefficients.

## Source and compatibility

Source: CFB.FAN CFB26 historical player detail pages. Six Vertical Threat TE cards with all model-required fields exposed by the indexed detail pages were scored. Records retain source URLs, card/player identifiers where recoverable, version, OVR, archetype, OOP OVRs and extraction status in `cfb26_te_vertical_blind_pilot.csv`.

## Measured result

- Historical sample N: 6
- Model-compatible N: 6
- Distinct-OVR pair comparisons: 14
- Correct cross-OVR orderings: 14
- Inversions: 0
- Ties: 0
- Pairwise ranking accuracy: 100.0%
- Observed OVRs: 91, 92, 92, 96, 97, 98
- Narrowest correct score margin: 1.029126 score points (97 OVR O.J. Howard over 96 OVR Izayah Cummings)

Scores:

| Player | OVR | Frozen v1.3 score |
|---|---:|---:|
| Trey Leckner | 91 | 85.766990 |
| Luke Reynolds | 92 | 86.932039 |
| Shamar Easter | 92 | 87.291262 |
| Izayah Cummings | 96 | 90.271845 |
| O.J. Howard | 97 | 91.766990 |
| Eric Ebron | 98 | 92.796117 |

## Interpretation

This clears the first historical-score checkpoint and is encouraging cross-season evidence for the frozen VT ranking architecture, but N=6 is not population-scale and must not be reported as population validation. The next scientific requirement remains enumerating the historical index and selectively expanding TE detail pages until the CFB25/26 TE populations are exhausted or a documented completeness boundary is reached.

No exact-OVR accuracy or MAE is reported because this frozen model is a ranking model, not a calibrated displayed-OVR predictor.
