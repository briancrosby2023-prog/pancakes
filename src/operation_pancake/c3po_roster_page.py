"""Operation Pancake My Team presentation for the authoritative C-3PO roster."""
from __future__ import annotations

import html
import re

from operation_pancake.c3po_roster import (
    VIEWS,
    C3PORoster,
    observation_fingerprint,
    roster_observations,
)


def _program_copy(card_observation) -> str:
    if (
        card_observation is not None
        and getattr(card_observation, "state", None) == "IDENTIFIED"
        and getattr(card_observation, "program", None)
    ):
        return '<span class="program">' + html.escape(card_observation.program) + "</span>"
    return '<span class="program program-missing">CARD NOT READ</span>'


def _player_card(player, card_observation=None, *, starter: bool) -> str:
    name = player.name if player.name and player.name.strip() else "NAME NOT READ"
    ovr = "—" if player.displayed_ovr is None else str(player.displayed_ovr)
    return (
        f'<article class="player {"starter" if starter else "backup"}" data-slot="{html.escape(player.slot)}">'
        f'<span class="slot">{html.escape(player.slot)}</span>'
        '<div class="player-copy">'
        f'<strong class="name">{html.escape(name)}</strong>'
        f'<span class="ovr">EA OVR {html.escape(ovr)}</span>'
        f"{_program_copy(card_observation)}"
        "</div></article>"
    )


def _position_group(slot: str) -> tuple[str, int]:
    match = re.match(r"^(.*?)(?:\s*(\d+))?$", slot.strip())
    if match is None:
        return slot, 1
    return (match.group(1) or slot), int(match.group(2) or 1)


def render_c3po_roster(roster: C3PORoster, programs=None) -> str:
    """Render the saved C-3PO roster and independently persisted programs."""
    if roster.status == "PROVIDER FAILURE":
        return (
            '<section id="my-team" class="team-panel"><header class="team-header">'
            '<p class="eyebrow">OPERATION PANCAKE</p><h1>My Team</h1></header>'
            '<p class="provider-failure">C-3PO could not read the screenshots. '
            "Your previous roster was not replaced.</p></section>"
        )
    programs = programs if hasattr(programs, "get") else {}
    sections = []
    for view in VIEWS:
        groups: dict[str, list[tuple[int, object, object]]] = {}
        for occurrence, player in roster_observations(roster):
            if player.view != view:
                continue
            position, depth = _position_group(player.slot)
            fingerprint = observation_fingerprint(player, occurrence)
            program = programs.get(fingerprint)
            if program is not None and (
                getattr(program, "player_name", None) != (player.name or "")
                or getattr(program, "displayed_ovr", None) != player.displayed_ovr
            ):
                program = None
            groups.setdefault(position, []).append((depth, player, program))
        cards = "".join(
            '<section class="position-group"><h3>' + html.escape(position) + "</h3>"
            + '<div class="depth-stack">'
            + "".join(
                _player_card(player, program, starter=depth == 1)
                for depth, player, program in sorted(rows, key=lambda row: row[0])
            )
            + "</div></section>"
            for position, rows in groups.items()
        )
        empty = '<p class="empty-view">No observations reported.</p>' if not cards else ""
        sections.append(
            f'<section class="roster-view" data-view="{html.escape(view)}">'
            f'<div class="section-heading"><h2>{html.escape(view)}</h2></div>'
            f'<div class="position-grid">{cards}{empty}</div></section>'
        )
    return (
        '<section id="my-team" class="team-panel"><header class="team-header">'
        '<p class="eyebrow">OPERATION PANCAKE</p><h1>My Team</h1>'
        '<p class="team-subtitle">Your lineup, read directly from EA Team Manager.</p>'
        '<a class="update-team" href="/setup">UPDATE TEAM</a></header>'
        + "".join(sections)
        + "</section>"
    )
