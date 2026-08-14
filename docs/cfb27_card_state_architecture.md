# CFB27 card and state architecture

Operation Pancake treats a player, card, and card state as different entities.

`PLAYER_ENTITY` stores the person and source-native player identifiers. `CARD_ENTITY` stores one
specific source card/version and its immutable program, position, and archetype identity.
`CARD_NATIVE_STATE` stores the source-native OVR and complete available ratings. Upgrades never
overwrite it.

`CARD_UPGRADE_STATE` and `PROGRESSION_EVENT` represent observed transitions. An event links explicit
from/to states, deltas, system, provenance, and confidence. Missing ratings remain null. A displayed
OVR is never converted into ratings.

`CARD_ACTIVE_STATE` exists only when the active card identity and ratings are directly observed or a
complete deterministic progression is validated. `ROSTER_INSTANCE` separately stores lineup display
OVR. `SPECIALIST_VIEW` stores role-specific OVRs without creating fake cards. `CHEMISTRY_CONTEXT`
stores validated boosts without mutating native ratings.

Stable IDs use reliable source-native IDs where available and deterministic hashes otherwise. Player
names alone are never card IDs. Same-player cards with different programs, source card IDs, or states
remain distinct.

Run `uv run python scripts/cfb27_database_health.py` before downstream research. A model may proceed
only when its readiness artifact lists the required fields as available for the requested scope.

## Progression evidence

OP-X-011 normalizes each observed upgrade as an append-only event. A valid event needs an
identified card/family, ordered before and after states, exact observed deltas, system, source,
and confidence. Historical claims without original vectors remain recovery targets instead of
synthetic transitions. Generate analytics with `scripts/generate_cfb27_op_x_011.py`; validate a
future observation with `scripts/ingest_progression_observation.py`.

## Public population acquisition

OP-X-012R uses the ordinary CFB.FAN global listing as a restartable discovery layer. Listing-derived
records are explicitly partial: their five displayed summary ratings never masquerade as a full
native vector. Detail-page records take precedence while conflicts are retained. The initial run
checkpoints all 590 populated pages; later bounded refreshes use
`scripts/run_cfb27_population_v3.py --refresh-pages N` to scan only the newest pages.
