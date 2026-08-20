# OP-X-027 Current Market Source Audit

Audit date: 2026-08-20.

## Best source: CFB.FAN

CFB.FAN is the only discovered public source with current CUT 27 card-level price displays, platform selection, price history UI, live-auction/recent-sales UI, daily sales counts, and stable exact card URLs.

Its public application bundle identifies JSON routes including `/api/cutdb/prices/dashboard/{platform}/`, `/api/cutdb/prices/overall/playeritem/?external_ids=...`, and `/api/cutdb/prices/{unique_id}/{platform}/`. The normal public page successfully used the dashboard route and rendered current Xbox market data. Direct non-browser requests to the same route were blocked by Cloudflare. No attempt was made to bypass that control.

The player-list display provides exact card identity, OVR, program, position/archetype, and a platform-selected displayed price. It does not expose a source observation timestamp or enough semantics to distinguish lowest live listing, aggregate listing, or recent completed sale. Therefore the five captured displays are real public market evidence but are not admitted as fresh canonical production observations and cannot authorize BUY.

## Alternatives

- EA: no documented public CUT auction API was found. EA pages document the product, not a market-data interface.
- CollegeFootball.gg: publishes CUT quicksell/training reference values, not current card prices.
- MUT.GG: current price infrastructure applies to Madden Ultimate Team, not College Football Ultimate Team.
- College Football Data API: game/team/player/recruiting data, not CUT auction prices.
- Coin-selling sites, videos, forums, and social posts: rejected for card-level reproducibility, identity, semantics, or trust.

## Verdict

Automated production acquisition remains unavailable. CFB.FAN is the best manual verification source, and its public UI can generate exact identity-bound price requests. Success path B applies.
