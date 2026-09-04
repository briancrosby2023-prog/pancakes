"""Operation Pancake My Team presentation for the authoritative C-3PO roster."""
from __future__ import annotations

import html

from operation_pancake.c3po_roster import VIEWS, C3PORoster


def _player_card(player) -> str:
    name = player.name if player.name and player.name.strip() else "NAME NOT READ"
    ovr = "—" if player.displayed_ovr is None else str(player.displayed_ovr)
    return (
        f'<article class="player" data-slot="{html.escape(player.slot)}">'
        f'<span class="slot">{html.escape(player.slot)}</span>'
        '<div class="player-copy">'
        f'<strong class="name">{html.escape(name)}</strong>'
        f'<span class="ovr">EA OVR {html.escape(ovr)}</span>'
        "</div></article>"
    )


def render_c3po_roster(roster: C3PORoster) -> str:
    """Render persisted provider observations without identity reinterpretation."""
    if roster.status == "PROVIDER FAILURE":
        return (
            '<section id="my-team" class="team-panel"><header class="team-header">'
            '<p class="eyebrow">OPERATION PANCAKE</p><h1>My Team</h1></header>'
            '<p class="provider-failure">C-3PO could not read the screenshots. '
            "Your previous roster was not replaced.</p></section>"
        )
    sections = []
    for view in VIEWS:
        cards = "".join(_player_card(player) for player in roster.players if player.view == view)
        empty = '<p class="empty-view">No observations reported.</p>' if not cards else ""
        sections.append(
            f'<section class="roster-view" data-view="{html.escape(view)}">'
            f'<div class="section-heading"><h2>{html.escape(view)}</h2></div>'
            f'<div class="player-grid">{cards}{empty}</div></section>'
        )
    return (
        '<section id="my-team" class="team-panel"><header class="team-header">'
        '<p class="eyebrow">OPERATION PANCAKE</p><h1>My Team</h1>'
        '<p class="team-subtitle">Your lineup, read directly from EA Team Manager.</p>'
        "</header>" + "".join(sections) + "</section>"
    )
