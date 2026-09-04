"""Operation Pancake My Team presentation for the authoritative C-3PO roster."""
from __future__ import annotations

import html

from operation_pancake.c3po_roster import VIEWS, C3PORoster


def _enrichment_copy(enrichment) -> str:
    if enrichment is None:
        return ""
    if enrichment.state != "LINKED" or enrichment.card is None:
        return f'<span class="enrichment">{html.escape(enrichment.state)}</span>'
    card = enrichment.card
    facts = []
    if card.native_position:
        facts.append(str(card.native_position))
    if card.card_ovr is not None:
        facts.append(f"{card.card_ovr} OVR")
    if card.program:
        facts.append(str(card.program))
    detail = " · ".join(facts) or card.canonical_name
    return f'<span class="enrichment">CFB27: {html.escape(detail)}</span>'


def _player_card(player, enrichment=None) -> str:
    name = player.name if player.name and player.name.strip() else "NAME NOT READ"
    ovr = "—" if player.displayed_ovr is None else str(player.displayed_ovr)
    return (
        f'<article class="player" data-slot="{html.escape(player.slot)}">'
        f'<span class="slot">{html.escape(player.slot)}</span>'
        '<div class="player-copy">'
        f'<strong class="name">{html.escape(name)}</strong>'
        f'<span class="ovr">EA OVR {html.escape(ovr)}</span>'
        f"{_enrichment_copy(enrichment)}"
        "</div></article>"
    )


def render_c3po_roster(roster: C3PORoster, enrichment=None) -> str:
    """Render provider observations first; optional canonical data is secondary."""
    if roster.status == "PROVIDER FAILURE":
        return (
            '<section id="my-team" class="team-panel"><header class="team-header">'
            '<p class="eyebrow">OPERATION PANCAKE</p><h1>My Team</h1></header>'
            '<p class="provider-failure">C-3PO could not read the screenshots. '
            "Your previous roster was not replaced.</p></section>"
        )
    by_observation = {}
    if enrichment is not None:
        by_observation = {id(row.observation): row for row in enrichment.players}
    sections = []
    for view in VIEWS:
        cards = "".join(
            _player_card(player, by_observation.get(id(player)))
            for player in roster.players
            if player.view == view
        )
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
