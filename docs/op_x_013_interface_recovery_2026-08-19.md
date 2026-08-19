# OP-X-013 historical interface recovery — 2026-08-19

This is a measured recovery checkpoint, not a completeness claim.

## Recovered branch state

- Working branch exists: `agent/op-x-013-cfb25-cfb26-historical-db`.
- Historical listing runner exists: `scripts/acquire_cfb_historical.py`.
- Historical listing parser exists as `parse_historical_listing` in `src/operation_pancake/research/cfb27_op_x_005.py`.
- The runner is resumable by persisted page keys and card IDs, enforces a minimum 2-second delay, and targets `https://cfb.fan/{game}/players/?page={page}` for game 25/26.
- The parser recognizes CFB25/26 detail hrefs and retains card ID, source URL, OVR, visible listing text, and listing-summary scope.

## Public-interface verification performed in this slice

### CFB25

`https://cfb.fan/25/players/?page=1` is a live public pageable listing. The observed first page exposes 15 card items and pagination links extending through at least page 600. Listing rows expose OVR, player name, five displayed ratings, program, position, and archetype. Historical position terminology is Madden/NFL-style (for example LE/RE/LOLB/MLB/ROLB), so normalization must preserve source-native position values rather than rewriting them to CFB27-native terminology.

The prior independent TE evidence remains a cross-check only: pages 1-693, terminal page 694 HTTP 404, 543 unique TE URLs. It is not a whole-season population count.

### CFB26

The direct archive route `https://cfb.fan/26/players/?page=1` was not successfully validated by the available web retrieval path in this slice. CFB.FAN forum evidence from the CUT26 transition states that separate CUT25 and CUT26 databases were intended, but that is not sufficient to claim the current CFB26 population interface or boundary.

### CFB27 preservation

The current public route `https://cfb.fan/players/?page=1` serves CFB27. No CFB27 acquisition or mutation was performed in this slice. Existing 8,838/8,838 evidence is therefore untouched.

## Code audit finding

`acquire_cfb_historical.py` currently loops only through a caller-supplied `--max-pages` boundary and does not itself convert a terminal HTTP 404 into a normal end-of-population condition. It checkpoints every successful page and deduplicates by `card_id`, but it does not yet establish the population boundary automatically, acquire full detail vectors, calculate unique-player counts, or produce the required completeness manifest.

## Exact next incomplete operation

Establish and persist full-season discovery boundaries before full-record acquisition: resume/complete CFB25 all-position enumeration to terminal pagination using the existing checkpoint architecture, independently validate the correct CFB26 archived listing interface and terminal behavior, then reconcile unique discovered card IDs. Do not treat the prior 543 TE URLs as the CFB25 denominator.
