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


LINEUP_STYLE = """
<style>
.team-panel{background:transparent;border:0;box-shadow:none;padding:0;margin-top:24px}
.team-header{display:grid;grid-template-columns:1fr auto;align-items:end;gap:16px;padding:18px 0 20px;border-bottom:1px solid #26303b}
.team-header .eyebrow{grid-column:1}.team-header h1{grid-column:1;font-size:30px}.team-subtitle{grid-column:1;margin-top:2px}
.team-header .update-team{grid-column:2;grid-row:1/4;position:static;align-self:center}
.lineup-tabs{display:flex;gap:34px;overflow-x:auto;border-bottom:1px solid #26303b;margin:0 0 26px;padding:0 2px}
.lineup-tabs a{position:relative;padding:18px 0 14px;color:#91a0b0;text-decoration:none;font-size:13px;font-weight:900;letter-spacing:.05em;white-space:nowrap}
.lineup-tabs a:first-child{color:#f5f7fa}.lineup-tabs a:first-child:after{content:"";position:absolute;left:0;right:0;bottom:-1px;height:2px;background:#f5b642}
.roster-view{margin:0 0 46px;scroll-margin-top:20px}.section-heading{margin:0 0 16px;border:0}.section-heading h2{font-size:13px;margin:0;color:#f5b642;letter-spacing:.12em}
.position-grid{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:24px 16px;align-items:start}
.position-group{min-width:0;background:transparent;border:0;border-radius:0;padding:0}.position-group h3{height:28px;margin:0 0 8px;color:#91a0b0;font-size:12px;font-weight:700;letter-spacing:0;text-transform:none}
.depth-stack{display:grid;gap:6px}.player{position:relative;display:block;min-width:0;padding:12px 11px;background:#171f2a;border:1px solid #303b48;border-radius:4px}
.player.starter{aspect-ratio:3/4;min-height:190px;padding:14px 12px;background:linear-gradient(155deg,#1d2937 0%,#111820 58%,#0d131a 100%);border-color:#3a4654;box-shadow:0 8px 24px #0003}
.player.starter .slot{display:block;margin-bottom:18px;font-size:11px;color:#9ba8b6}.player.starter .player-copy{position:absolute;left:12px;right:12px;bottom:13px;display:grid;gap:4px}
.player.starter .name{font-size:16px;line-height:1.05;text-transform:uppercase;overflow-wrap:anywhere}.player.starter .ovr{font-size:20px;line-height:1;color:#f5b642}
.player.starter .program{font-size:10px;line-height:1.2}.player.backup{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:4px 8px;margin:0;padding:9px 10px;background:#333b45;border:0;border-radius:2px}
.player.backup .slot{display:none}.player.backup .player-copy{display:contents}.player.backup .name{grid-column:1;font-size:12px;line-height:1.1;text-transform:uppercase;overflow-wrap:anywhere}.player.backup .ovr{grid-column:2;grid-row:1;font-size:14px;line-height:1;color:#fff;white-space:nowrap}.player.backup .program{grid-column:1/3;font-size:9px;color:#b5bec8}.program-missing{color:#768493!important}.empty-view{grid-column:1/-1;color:#697888}
@media(max-width:1100px){.position-grid{grid-template-columns:repeat(3,minmax(0,1fr))}.player.starter{min-height:210px}}
@media(max-width:720px){.position-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.lineup-tabs{gap:20px}.team-header{grid-template-columns:1fr}.team-header .update-team{grid-column:1;grid-row:auto;justify-self:start}.player.starter{min-height:190px}}
@media(max-width:460px){.position-grid{grid-template-columns:1fr}.player.starter{aspect-ratio:auto;min-height:180px}.lineup-tabs{gap:16px}}
</style>
"""


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


def _view_anchor(view: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", view.lower()).strip("-")


def render_c3po_roster(roster: C3PORoster, programs=None) -> str:
    """Render the saved C-3PO roster and independently persisted programs."""
    if roster.status == "PROVIDER FAILURE":
        return (
            LINEUP_STYLE
            + '<section id="my-team" class="team-panel"><header class="team-header">'
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
            '<section class="position-group"><h3>' + html.escape(position.title()) + "</h3>"
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
            f'<section id="{_view_anchor(view)}" class="roster-view" data-view="{html.escape(view)}">'
            f'<div class="section-heading"><h2>{html.escape(view)}</h2></div>'
            f'<div class="position-grid">{cards}{empty}</div></section>'
        )
    tabs = '<nav class="lineup-tabs" aria-label="Lineup sections">' + "".join(
        f'<a href="#{_view_anchor(view)}">{html.escape(view)}</a>' for view in VIEWS
    ) + "</nav>"
    return (
        LINEUP_STYLE
        + '<section id="my-team" class="team-panel"><header class="team-header">'
        '<p class="eyebrow">OPERATION PANCAKE</p><h1>My Team</h1>'
        '<p class="team-subtitle">Your lineup, read directly from EA Team Manager.</p>'
        '<a class="update-team" href="/setup">UPDATE TEAM</a></header>'
        + tabs
        + "".join(sections)
        + "</section>"
    )
