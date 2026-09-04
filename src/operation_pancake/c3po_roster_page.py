"""My Team HTML for the clean-room C-3PO roster."""
from __future__ import annotations

import html

from operation_pancake.c3po_roster import VIEWS, C3PORoster


def _player_card(player) -> str:
    name = player.name if player.name and player.name.strip() else "NAME NOT READ"
    ovr = "—" if player.displayed_ovr is None else str(player.displayed_ovr)
    backups = "".join(
        '<li class="backup">'
        + html.escape(str(row.get("player_name") or row.get("name") or "NAME NOT READ"))
        + "</li>"
        for row in player.backups
    )
    backup_html = f'<ul class="backups">{backups}</ul>' if backups else ""
    return (
        f'<article class="player" data-slot="{html.escape(player.slot)}">'
        f'<span class="slot">{html.escape(player.slot)}</span>'
        f'<strong class="name">{html.escape(name)}</strong>'
        f'<span class="ovr">EA OVR {html.escape(ovr)}</span>'
        f"{backup_html}</article>"
    )


def render_c3po_roster(roster: C3PORoster) -> str:
    if roster.status == "PROVIDER FAILURE":
        return (
            '<section id="my-team"><h1>My Team</h1>'
            '<p class="provider-failure">C-3PO could not read the screenshots. '
            "Your previous roster was not replaced.</p></section>"
        )
    sections = []
    for view in VIEWS:
        cards = "".join(_player_card(player) for player in roster.players if player.view == view)
        sections.append(
            f'<section class="roster-view" data-view="{html.escape(view)}">'
            f"<h2>{html.escape(view)}</h2>{cards}</section>"
        )
    return '<section id="my-team"><h1>My Team</h1>' + "".join(sections) + "</section>"
