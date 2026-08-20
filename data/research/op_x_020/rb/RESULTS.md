# OP-X-020-RB blind historical validation

`RB-M19-ARCH-001 v1.0` was frozen and committed before scoring. CFB26 was persisted before the unchanged CFB25 replication.

| Season | Population | Eligible | Pairs | Correct | Inversions | Ties | Accuracy | Spearman | Gate |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| CFB26 | 747 | 747 | 262525 | 253439 | 3382 | 5704 | 98.6831% | 0.987408 | PASS |
| CFB25 | 783 | 783 | 292889 | 287109 | 5630 | 150 | 98.0768% | 0.990652 | PASS |

Cross-season verdict: **DURABLE PASS**.
