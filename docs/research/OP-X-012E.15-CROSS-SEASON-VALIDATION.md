# OP-X-012E.15 — Cross-Season Blind Validation

Status: ACTIVE

## Discovery

CFB.FAN preserves separate historical player databases for College Football 25 and College Football 26. Historical player detail pages expose displayed OVR, position, archetype, program/team metadata, and detailed displayed ratings. This makes prior seasons useful as genuine out-of-season validation populations for E.15.

## Scientific purpose

Do not pool CFB25, CFB26, and CFB27 before validation. Candidate formulas/models must be frozen on their derivation season first, then evaluated blind on another season. This distinguishes a model that merely fits one year's card population from a model that captures reusable EA architecture.

Required sequence:

1. Preserve season provenance on every record.
2. Freeze the candidate model before examining target-season outcomes.
3. Score CFB25 and CFB26 separately from CFB27.
4. Compare exact OVR agreement, ranking/order agreement, MAE, residual structure, archetype behavior, and rounding behavior.
5. If performance shifts materially by season, treat that as evidence of formula/architecture revision rather than silently refitting a pooled model.
6. Special/out-of-position/upgrade/reset cards must remain identifiable and may be evaluated separately from ordinary native-position cards.

## Immediate value

Center is a priority because CFB26 pages expose all major blocking ratings and multiple Center archetypes. TE is a priority because existing CFB27-derived ranking models can be tested without refitting. CB/Safety and DT/EDGE/LB follow because prior-season populations expand same-OVR and adjacent-OVR natural experiments.

## Verified source examples

CFB25 historical database page: `https://cfb.fan/25/players/`

CFB25 Jace Amaro, 99 OVR Vertical Threat TE, exposes general, receiving, ball-carrier, and blocking ratings.

CFB26 historical detail pages are indexed under `/players/.../26-.../`. Verified examples include:

- Carter Miller, 80 OVR Pass Protector C: AWR 79, STR 79, RBK 72, RBF 70, RBP 68, PBK/PBF/PBP 80.
- Cam Nichols, 70 OVR Agile C: AWR/STR/RBK/RBF/RBP 70 with PBK 62, PBF 63, PBP 62.
- Chandler Strong, 86 OVR Agile C: AWR 86, STR 74, RBK/RBF 86, RBP 83, PBK/PBF 86, PBP 81.
- Gavin Gerhardt, 81 OVR Raw Strength C: AWR/RBK/RBF/RBP 81, STR 77, PBK 72, PBF 67, PBP 80.
- Jake Timm, 91 OVR Well Rounded C: STR/RBK 91, AWR 81, RBF/PBK/PBP 89, RBP 88, PBF 91.

These examples already show that CFB26 Center OVR cannot be interpreted as a trivial function of AWR alone or one universal blocking rating. Archetype-aware multi-attribute validation is required.

## Accuracy policy

Cross-season ranking accuracy and exact displayed-OVR accuracy are separate metrics. Neither may be substituted for the other. Existing >=95% ranking results may establish GM ranking usability without establishing >=95% exact OVR prediction.
