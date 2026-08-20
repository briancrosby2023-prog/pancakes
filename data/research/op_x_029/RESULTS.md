# OP-X-029 Results

## Capability

`operation-pancake-gm market-observe` records one exact current observation.
`market-snapshot` records a JSON mapping of canonical card IDs to prices in one command.
Known player, position, OVR, program, and archetype data are enriched automatically.
User observation time and ingestion time are recorded separately; source-published time
remains null unless the source actually supplies it.

Real observations append to `data/production/market/user_observation_history.json`.
Stable evidence IDs deduplicate exact repeats without overwriting distinct observations.
Fixture evidence is rejected from that history.

## Evidence and decisions

Per-card history reports count, distinct times, first/latest observation, min/median/max,
range, dispersion, span, semantics, supported changes, and volatility. Evidence progresses
through INSUFFICIENT, EARLY, USABLE, and STRONG based on independent time breadth,
freshness, semantics, exact identity, and stability.

BUY requires STRONG market evidence, favorable frozen OP-X-028 intrinsic value, stable
dispersion, meaningful roster improvement, and affordability. USABLE evidence can support
WAIT and WATCH/re-evaluation boundaries, but not BUY. The OP-X-028 index and hash remain
unchanged.

## Collection burden

The first request is limited to Brendan Black and E'Marion Harris because their contextual
classes are STRONG VALUE and VALUE. Anthony Donkoh and Samson Okunlola resale listings are
optional but materially improve net-cost decisions. Kip Lewis, Bray Hubbard, and Kobe Black
are lower-priority checks because their contextual classes are FAIR, PREMIUM, and OVERPAY.

The five OP-X-027 displays are retained as context-only evidence with capture-time quality
explicitly separated from absent source-published timestamps. They do not enter qualified
OP-X-029 history.

## Verification

Fourteen OP-X-029 tests and 66 targeted regression tests pass. Ruff passes. Broader pytest
was attempted but cannot collect because the existing E.15 acquisition test imports the
absent optional `requests` dependency.
