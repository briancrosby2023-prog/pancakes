# External card acquisition

External data follows the same evidence lifecycle as File Library recovery:

```text
adapter -> raw snapshot -> parse -> normalize -> ingestion manifest -> staging
        -> validation -> deduplication -> conflict review -> explicit promotion
```

Adapters implement `discover_cards`, `fetch_card`, `parse_card`, `normalize_card`, and `stage_card`.
They cannot mutate canonical records. Raw responses are content-addressed by SHA-256 and retain the
source, external identifiers, retrieval timestamp, snapshot location, and parser version so they can
be reparsed later.

The card model preserves source/card/player IDs, identity fields, all displayed ratings, provenance,
and nullable unknowns. Market observations are separate timestamped records and do not participate
in identity matching. Matching requires an external ID or the complete player/position/OVR/
archetype/program/card-type tuple. A same-player/same-OVR candidate with different program or card
type is an ambiguity, not an automatic match.

The `cfb_fan` namespace only imports historical saved-page discovery IDs. It deliberately has no
live endpoint implementation. A live adapter must first validate a normal public interface and obey
throttling, retry/backoff, caching, resume, and access restrictions. Authentication, anti-bot, and
CAPTCHA bypasses are prohibited; inaccessible sources are logged as blocked.

Commands:

```text
operation-pancake acquire plan
operation-pancake acquire import local-fixture-or-export.json --dry-run
operation-pancake acquire import local-fixture-or-export.json
operation-pancake acquire status
operation-pancake acquire conflicts
```

There is intentionally no live scrape command. The reusable state exposes last retrieval history,
raw snapshots, new cards, conflicts, failure status, resume cursor, and market history for a future
PC application.

## Controlled CFB.FAN pilot

On 2026-08-13, normal public access returned HTTP 200 for `robots.txt`, `/players/`, and the six
fixed Center player pages used by the pilot. Robots rules disallow `/accounts/*` and `/api/*`, but
not public player pages. The pilot made no API calls and fetched the six pages sequentially at no
more than 12 requests per minute. The adapter has no broad crawl discovery method.

The listing provides population discovery and key ratings. Player pages provide the 15 displayed
Center ratings (`SPD ACC AGI COD AWR STR TGH RBK RBF RBP PBK PBF PBP LBK IBL`), program,
archetype, team, quick-sell information, and sometimes date added. Release and market coverage are
therefore partial rather than guaranteed. All six responses are retained as content-addressed raw
snapshots and all normalized cards remain external staging evidence.
