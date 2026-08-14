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
