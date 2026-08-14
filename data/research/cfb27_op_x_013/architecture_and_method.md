# OP-X-013 full-vector extraction discovery

## Existing 432-vector path

The 432 pre-packet complete records came from individual public player detail pages. The
`CfbFanPublicAdapter` requested one HTML page per card at at most 12 requests/minute. Raw HTML was
saved under `data/external/raw/cfb_fan/`; `parse_player_page` isolated the rating rows between the
General and Team sections and extracted the 15 position-relevant `rating__label` / `rating__value`
pairs. The pages are server-rendered: the tested HTML had no JSON-LD, Next/Nuxt hydration state, or
inline API payload.

## Public structured architecture

The ordinary unauthenticated frontend bundle at
`https://assets.cfb.fan/frontend/assets/apps-BPNhmoF-.js` calls these public interfaces:

- `/api/27/core-data/`
- `/api/27/player-items/?ids=<comma-separated external IDs>`
- `/api/27/player-items/` with ordinary listing filters
- `/api/cutdb/player-items/<gameSlug>-<externalId>/`

The selected method is `GET https://cfb.fan/api/27/player-items/?ids=...`. It accepts the numeric
portion of the canonical `27-*` source ID and returned all 50 requested cards in one response. Each
record includes stable identity metadata and 54 explicit integer rating fields. A field absent from
JSON remains unknown; integer zero is retained as an observed rating. The API was not discovered by
probing private infrastructure: its exact route and parameters are present in the public site's own
JavaScript and it answered an ordinary unauthenticated GET. No authentication, CAPTCHA, access
control, or rate-limit bypass was used.

## Validation and pilot

Twenty existing complete records covered 17 positions, seven programs, 15 archetypes, and multiple
OVRs. All identity fields and every one of their legacy position-relevant ratings exactly matched the
structured records: 20 exact, zero conflicts, zero missing responses. The 30-card partial pilot also
returned 30/30. Every card matched identity, OVR, program, archetype, and its five listing ratings;
all exposed all 54 fields and were promoted. Raw JSON is content-addressed by SHA-256 and the
checkpoint records requested IDs, returned IDs, URL, retrieval time, digest, and snapshot.

## Options and cost

At the established conservative ceiling of 12 requests/minute:

| Method | Cards/request | Requests for 8,406 | Request time | Resume/evidence |
|---|---:|---:|---:|---|
| Detail HTML | 1 | 8,406 | 700.5 min (11.7 h) | Existing per-card hashes |
| Structured detail | 1 | 8,406 | 700.5 min (11.7 h) | Possible, but no benefit |
| Bulk `ids` endpoint | 50 validated | 169 before pilot; 168 remaining | 14.1 min remaining | Batch checkpoint + hashed raw JSON |

The bulk endpoint reduces requests by about 98%. Failures are retried at most three times with bounded
backoff and logged; completed batches replay from raw snapshots. Missing returned IDs remain partial.
Conflicts preserve the existing record and are logged. Complete records are never downgraded.

## Priority and resume point

Ordering is deterministic and inclusive: current/recent high OVR, upgradeable, OL, MIKE/LB, EDGE,
DT, TE, secondary, QB, WR/HB, then all remaining cards. The next run recomputes that order over only
the remaining partial records, so it resumes after the 30 validated promotions without re-acquiring
them. The exact next command is:

`uv run --no-sync --no-cache python scripts/run_cfb27_full_vector_pilot.py --pilot-size 8376`

That command is intentionally not run in OP-X-013; this packet stops at the validated pilot gate.
