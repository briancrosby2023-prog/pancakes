# OP-X-019-SAFETY blind historical validation

`S-M19-ARCH-001 v1.0` was frozen and committed before scoring. CFB26 was persisted before the unchanged CFB25 replication.

| Season | Population | Eligible | Pairs | Correct | Inversions | Ties | Accuracy | Spearman | Gate |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| CFB26 | 949 | 949 | 436135 | 433798 | 2320 | 17 | 99.4680% | 0.998431 | PASS |
| CFB25 | 955 | 955 | 436828 | 435768 | 1044 | 16 | 99.7610% | 0.998002 | PASS |

Cross-season verdict: **DURABLE PASS**.
