"""Bounded C-3PO -> Team Setup bridge for OFFENSE LT/RT only."""
from __future__ import annotations

from pathlib import Path

from operation_pancake.c3po_tackle_resolver import TackleResolution, resolve_tackles
from operation_pancake.team_import import Candidate

TACKLE_SLOTS = ("LT1", "RT1")


def _candidate(state, slot: str) -> Candidate:
    found = next((c for c in state.candidates if c.group == "OFFENSE" and c.slot == slot), None)
    if found is not None:
        return found
    found = Candidate(id=f"c3po-{slot.lower()}", group="OFFENSE", slot=slot)
    state.candidates.append(found)
    return found


def _backup(row: TackleResolution) -> dict:
    return {
        "observed_player_name": row.observed_player_name,
        "player_name": row.canonical_player_identity,
        "displayed_ovr": row.displayed_lineup_ovr,
        "native_card_ovr": row.native_card_ovr,
        "program": row.program,
        "canonical_card_id": row.canonical_card_id,
        "match_status": "MATCHED" if row.status == "MATCHED" else "UNMATCHED",
    }


def _apply(candidate: Candidate, rows: list[TackleResolution]) -> None:
    starter = rows[0]
    candidate.player_name = starter.canonical_player_identity
    candidate.displayed_ovr = starter.displayed_lineup_ovr
    candidate.position = starter.observed_position
    candidate.program = starter.program
    candidate.canonical_card_id = starter.canonical_card_id
    candidate.match_status = "MATCHED" if starter.status == "MATCHED" else "UNMATCHED"
    candidate.confidence = 1.0 if starter.status == "MATCHED" else None
    candidate.backups = [_backup(row) for row in rows[1:]]
    candidate.provenance = [p for p in candidate.provenance if not p.startswith("c3po:")] + ["c3po:google-gemini-screen-translation", "c3po:cfb27-position-isolated-resolution"]
    candidate.match_diagnostics = dict(candidate.match_diagnostics)
    candidate.match_diagnostics["c3po"] = {
        "observed_player_name": starter.observed_player_name,
        "displayed_lineup_ovr": starter.displayed_lineup_ovr,
        "native_card_ovr": starter.native_card_ovr,
        "canonical_player_identity": starter.canonical_player_identity,
        "program": starter.program,
        "canonical_card_id": starter.canonical_card_id,
        "status": starter.status,
    }


def integrate_offense_tackles(state_store, cards: list[dict], translator) -> object:
    """Translate the current OFFENSE image and replace only LT1/RT1 resolution."""
    state = state_store.load()
    offense = next((shot for shot in state.screenshots if shot.get("view") == "OFFENSE"), None)
    if offense is None:
        state.team_observations["c3po_tackles"] = {"status": "SKIPPED", "reason": "offense-screenshot-unavailable"}
        state_store.save(state)
        return state
    try:
        observation = translator.translate_offense_tackles(Path(offense["path"]))
        resolutions = resolve_tackles(observation, cards)
    except Exception as exc:
        # The translator is an external observation boundary. Fail closed without
        # mutating any previously extracted candidate identity or other position.
        state.team_observations["c3po_tackles"] = {"status": "ERROR", "error_type": type(exc).__name__}
        state_store.save(state)
        return state
    for slot in TACKLE_SLOTS:
        rows = [row for row in resolutions if row.slot == slot]
        if rows:
            _apply(_candidate(state, slot), rows)
    state.team_observations["c3po_tackles"] = {
        "status": "APPLIED",
        "provider": observation.provider,
        "model": observation.model,
        "source_screenshot": offense.get("id"),
        "slots": list(TACKLE_SLOTS),
    }
    state_store.save(state)
    return state
