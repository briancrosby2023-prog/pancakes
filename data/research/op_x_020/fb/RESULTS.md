# OP-X-020-FB blind historical validation

`FB-M19-ARCH-001 v1.0` was frozen and committed before scoring. CFB26 was persisted before the unchanged CFB25 replication.

| Season | Population | Eligible | Pairs | Correct | Inversions | Ties | Accuracy | Spearman | Gate |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| CFB26 | 62 | 62 | 1823 | 1801 | 21 | 1 | 98.8474% | 0.994869 | PASS |
| CFB25 | 58 | 58 | 1605 | 1578 | 27 | 0 | 98.3178% | 0.993272 | PASS |

Cross-season verdict: **DURABLE PASS**.
