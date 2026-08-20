# Operation Pancake 95% Coverage Matrix

| Position | Model | Archetype | Production | CFB25 N | CFB25 | CFB26 N | CFB26 | Verdict | Locked |
|---|---|---|---|---:|---:|---:|---:|---|---|
| TE | TE-MODEL-001 v1.1 | Gritty Possession | production | 201 | 99.9331% | 67 | 99.0173% | DURABLE PASS | YES |
| TE | TE-MODEL-003 v1.1 | Physical Route Runner | production | 0 | n/a | 403 | 99.8164% | INSUFFICIENT CROSS-SEASON EVIDENCE | NO |
| TE | TE-MODEL-004 v1.1 | Pure Blocker | diagnostic/non-production | 162 | 97.2320% | 63 | 99.7775% | DURABLE PASS | NO |
| TE | TE-MODEL-006 v1.3 | Vertical Threat | production | 179 | 99.5279% | 124 | 99.8229% | DURABLE PASS | YES |
| C | Historical Madden 19 Center frozen historical hypothesis | all | diagnostic/non-production | 356 | 97.6602% | 372 | 98.6992% | DURABLE RANKING PASS; ABSOLUTE CALIBRATION REJECTED | YES |
| QB | QB-SHARED-001 v1.0 | shared; Pure Runner excluded | production | 621 | 98.3737% | 494 | 99.2240% | DURABLE PASS | YES |
| QB | Madden 19 Field General prior historical reference | Field General | diagnostic/non-production | 351 | 99.9778% | 305 | 99.9494% | DURABLE DIAGNOSTIC PASS | NO |
| QB | Madden 19 Scrambler prior historical reference | Scrambler | diagnostic/non-production | 100 | 100.0000% | 129 | 99.9617% | DURABLE DIAGNOSTIC PASS | NO |
| QB | Madden 19 Strong Arm prior historical reference | Strong Arm | diagnostic/non-production | 19 | 100.0000% | 0 | n/a | SINGLE-SEASON DIAGNOSTIC PASS | NO |
| QB | Madden 19 West Coast prior historical reference | West Coast | diagnostic/non-production | 0 | n/a | 60 | 96.0445% | SINGLE-SEASON DIAGNOSTIC PASS | NO |
| WR | WR-M19-ARCH-001 v1.0 | generation-mapped archetype vectors | production | 1305 | 99.4934% | 1157 | 98.8354% | DURABLE PASS | YES |
| CB | CB-M19-ARCH-001 v1.0 | generation-mapped archetype vectors | production | 1079 | 98.3188% | 953 | 99.8088% | DURABLE PASS | YES |
| S | S-M19-ARCH-001 v1.0 | generation-mapped archetype vectors | production | 955 | 99.7610% | 949 | 99.4680% | DURABLE PASS | YES |
| EDGE | EDGE-M19-ARCH-001 v1.0 | generation-mapped archetype vectors | production | 831 | 99.7634% | 898 | 98.9275% | DURABLE PASS | YES |
| MIKE | MIKE-M19-ARCH-001 v1.0 | generation-mapped archetype vectors | production | 708 | 99.5998% | 614 | 99.7689% | DURABLE PASS | YES |
| DT | DT-M19-ARCH-001 v1.0 | generation-mapped archetype vectors | production | 609 | 99.7887% | 633 | 98.9334% | DURABLE PASS | YES |
| SAM | SAM-M19-ROLE-001 v1.0 | generation-mapped archetype vectors | production | 733 | 99.7429% | 778 | 99.1545% | DURABLE PASS | YES |

## Non-executable families

- HB/RB: CFB25 N=783; CFB26 N=747; Exact position/archetype coefficients frozen independently of CFB25/26.
- FB: CFB25 N=58; CFB26 N=62; Exact position/archetype coefficients frozen independently of CFB25/26.
- LT/RT: CFB25 N=743; CFB26 N=719; Exact position/archetype coefficients frozen independently of CFB25/26.
- LG/RG: CFB25 N=702; CFB26 N=713; Exact position/archetype coefficients frozen independently of CFB25/26.
- K/P: CFB25 N=336; CFB26 N=323; Exact position/archetype coefficients frozen independently of CFB25/26.

## Next highest-value model

HB/RB. It is the largest remaining unmodeled two-season family (783 CFB25; 747 CFB26). Authoritative HB vectors are present in SRC-M19-001, but its generation terminology must be frozen before blind validation.
