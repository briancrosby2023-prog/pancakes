# OP-X-018 blind historical WR validation

`WR-M19-ARCH-001 v1.0` was frozen and committed before scoring. CFB26 was executed and persisted first; CFB25 then used the unchanged specification. Ranking accuracy excludes score ties, matching prior Operation Pancake gates.

| Season | Population | Eligible | Pairs | Correct | Inversions | Ties | Accuracy | Spearman | Gate |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| CFB26 | 1158 | 1157 | 646906 | 639363 | 7534 | 9 | 98.8354% | 0.996173 | PASS |
| CFB25 | 1305 | 1305 | 812874 | 808738 | 4118 | 18 | 99.4934% | 0.997233 | PASS |

Cross-season verdict: **DURABLE PASS**.

Program/card-type behavior is explicitly unavailable because those fields are not present in the historical record schema. Machine-readable results preserve OVR-band behavior, archetype behavior, residuals, worst inversions, and boundary transition clusters.
