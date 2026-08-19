# OP-X-012E.15 — Frozen TE model manifest

Purpose: preserve the pre-CFB25/26 validation state of the TE ranking models before population-scale historical scoring. Historical validation outcomes must not be used to alter these entries in place; any refit requires a new model/version.

Recovered from the canonical Operation Pancake File Library workbooks dated 2026-08-01.

| Model | Archetype | Frozen architecture | Established CFB27 ranking result | Historical validation status |
|---|---|---|---|---|
| TE-MODEL-006 v1.3 | Vertical Threat | Madden 19 Vertical Threat base, unavailable ELU omitted/renormalized, plus +2 LBK and +3 IBL | 138/140 cross-OVR = 98.5714%; prospective independent validation 17/17 | NOT YET SCORED on CFB25/26 |
| TE-MODEL-001 v1.1 | Gritty Possession | Madden 19 Possession weights | 97/98 cross-OVR = 98.9796%; blind result recorded as 82/83 = 98.8% | NOT YET SCORED on CFB25/26 |
| TE-MODEL-003 v1.1 | Physical Route Runner | 71% Vertical Threat candidate + 29% Possession candidate | 304/304 unique-profile blind = 100% | NOT YET SCORED on CFB25/26 |
| TE-MODEL-004 v1.1 | Pure Blocker | Madden 19 Blocking prior only | No pairwise validation; one structured CFB27 card in original phase | NOT VALIDATED; historical population is acquisition priority |

## Scientific controls

- These are ranking architectures, not proven exact displayed-OVR conversion formulas.
- Keep ranking accuracy distinct from exact OVR accuracy.
- Do not pool CFB25/26 records into fitting before first frozen-model scoring.
- Preserve season and archetype provenance.
- If the exact underlying Madden 19 attribute-weight table required to reproduce a score is unavailable in GitHub, recover it from the canonical File Library source before scoring; do not reconstruct coefficients from memory.
- CFB25/26 failures are validation evidence. Do not silently tune these frozen versions after observing failures.

## Source recovery notes

Canonical File Library evidence recovered the model identities and frozen status:

- `Operation_Pancake_Master_Database_v1.6_TE_Formula_Phase_Complete.xlsx` status board: TE-MODEL-006 v1.3, TE-MODEL-001 v1.1, TE-MODEL-003 v1.1, TE-MODEL-004 v1.1.
- `Operation_Pancake_Master_Database_v1.4_TE_VT_Model_v1.3.xlsx`: VT v1.3 is the frozen predictive candidate and identifies the +2 LBK/+3 IBL modification.
- Earlier model registry: Gritty uses Madden 19 Possession; PRR uses the frozen 71/29 VT/Possession blend; Pure Blocker retains Madden Blocking as an external prior only.

Freeze date: 2026-08-19.
