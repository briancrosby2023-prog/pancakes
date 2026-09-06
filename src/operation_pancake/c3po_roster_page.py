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
.team-panel{background:transparent;border:0;box-shadow:none;padding:0;margin-top:12px}
.team-header{display:grid;grid-template-columns:1fr auto;align-items:end;gap:10px;padding:8px 0 10px;border-bottom:1px solid #26303b}
.team-header .eyebrow{grid-column:1}.team-header h1{grid-column:1;font-size:26px}.team-subtitle{grid-column:1;margin-top:0}
.team-header .update-team{grid-column:2;grid-row:1/4;position:static;align-self:center}
.lineup-tabs{display:flex;gap:32px;border-bottom:1px solid #26303b;margin:0 0 12px;padding:0 2px}
.lineup-tabs button{appearance:none;background:none;border:0;position:relative;padding:11px 0 9px;color:#91a0b0;font:inherit;font-size:12px;font-weight:900;letter-spacing:.05em;white-space:nowrap;cursor:pointer}
.lineup-tabs button.active{color:#f5f7fa}.lineup-tabs button.active:after{content:"";position:absolute;left:0;right:0;bottom:-1px;height:2px;background:#f5b642}
.roster-view{display:none;margin:0 0 18px}.roster-view.active{display:block}.section-heading{margin:0 0 8px;border:0}.section-heading h2{font-size:12px;margin:0;color:#f5b642;letter-spacing:.12em}
.position-grid{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:14px 12px;align-items:start}
.position-group{min-width:0;background:transparent;border:0;border-radius:0;padding:0}.position-group h3{height:18px;margin:0 0 4px;color:#91a0b0;font-size:11px;font-weight:700;line-height:18px;letter-spacing:0;text-align:left;text-transform:none}
.depth-stack{display:grid;gap:4px}.player{position:relative;display:block;min-width:0;padding:8px;background:#171f2a;border:1px solid #303b48;border-radius:3px;text-align:left}
.player.starter{height:158px;min-height:0;padding:9px;background:linear-gradient(155deg,#1d2937 0%,#111820 58%,#0d131a 100%);border-color:#3a4654;box-shadow:0 5px 14px #0003}
.player.starter .slot{display:block;margin:0;font-size:9px;line-height:12px;color:#9ba8b6;text-align:left}.player.starter .player-copy{position:absolute;left:9px;right:9px;bottom:9px;display:grid;grid-template-columns:1fr;gap:3px;align-items:end;text-align:left}
.player.starter .name{display:block;font-size:12px;line-height:14px;text-transform:uppercase;overflow-wrap:anywhere}.player.starter .ovr{display:block;font-size:18px;line-height:20px;color:#f5b642}.player.starter .program{display:block;min-height:9px;font-size:8px;line-height:9px}
.player.backup{display:block;margin:0;padding:7px 8px;background:#333b45;border:0;border-radius:2px;text-align:left}.player.backup .slot{display:none}.player.backup .player-copy{display:grid;grid-template-columns:1fr;gap:2px;text-align:left}.player.backup .name{display:block;width:100%;font-size:10px;line-height:12px;text-transform:uppercase;overflow-wrap:normal;word-break:normal}.player.backup .ovr{display:block;font-size:12px;line-height:13px;color:#fff;white-space:nowrap;text-align:left}.player.backup .program{display:block;min-height:8px;font-size:7px;line-height:8px;color:#b5bec8}.program-missing{color:#768493!important}.empty-view{grid-column:1/-1;color:#697888}
@media(max-width:820px){.position-grid{grid-template-columns:repeat(3,minmax(0,1fr))}.player.starter{height:165px}}
@media(max-width:620px){.position-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.lineup-tabs{gap:18px;overflow-x:auto}.team-header{grid-template-columns:1fr}.team-header .update-team{grid-column:1;grid-row:auto;justify-self:start}.player.starter{height:155px}}
@media(max-width:420px){.position-grid{grid-template-columns:1fr}.player.starter{height:145px}.lineup-tabs{gap:14px}}
</style>
<script>
document.addEventListener("DOMContentLoaded",()=>{
 const root=document.getElementById("my-team");if(!root)return;
 const tabs=[...root.querySelectorAll(".lineup-tabs button")];
 const views=[...root.querySelectorAll(".roster-view")];
 const show=id=>{tabs.forEach(t=>{const on=t.dataset.target===id;t.classList.toggle("active",on);t.setAttribute("aria-selected",on?"true":"false")});views.forEach(v=>v.classList.toggle("active",v.id===id))};
 tabs.forEach(t=>t.addEventListener("click",()=>show(t.dataset.target)));
 if(tabs.length)show(tabs[0].dataset.target);
});
</script>
"""

OFFENSE_POSITION_ORDER = ("LT", "LG", "C", "RG", "RT", "TE", "WR1", "WR3", "HB", "QB", "FB", "WR2")


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
        f'<span class="ovr">{html.escape(ovr)} OVR</span>'
        f"{_program_copy(card_observation)}"
        "</div></article>"
    )


def _position_group(slot: str) -> tuple[str, int]:
    clean_slot = slot.strip().upper()
    wr_match = re.fullmatch(r"WR\s*(\d+)", clean_slot)
    if wr_match:
        wr_depth = int(wr_match.group(1))
        if wr_depth <= 3:
            return f"WR{wr_depth}", 1
        return "WR3", wr_depth - 2
    match = re.match(r"^(.*?)(?:\s*(\d+))?$", clean_slot)
    if match is None:
        return clean_slot, 1
    return (match.group(1) or clean_slot), int(match.group(2) or 1)


def _ordered_groups(view: str, groups: dict[str, list[tuple[int, object, object]]]):
    if view != "OFFENSE":
        return groups.items()
    rank = {position: index for index, position in enumerate(OFFENSE_POSITION_ORDER)}
    return sorted(groups.items(), key=lambda item: (rank.get(item[0], len(rank)), item[0]))


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
    for view_index, view in enumerate(VIEWS):
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
                _player_card(player, program, starter=index == 0)
                for index, (_depth, player, program) in enumerate(
                    sorted(rows, key=lambda row: row[0])
                )
            )
            + "</div></section>"
            for position, rows in _ordered_groups(view, groups)
        )
        empty = '<p class="empty-view">No observations reported.</p>' if not cards else ""
        active = " active" if view_index == 0 else ""
        sections.append(
            f'<section id="{_view_anchor(view)}" class="roster-view{active}" data-view="{html.escape(view)}">'
            f'<div class="section-heading"><h2>{html.escape(view)}</h2></div>'
            f'<div class="position-grid">{cards}{empty}</div></section>'
        )
    tabs = '<nav class="lineup-tabs" role="tablist" aria-label="Lineup sections">' + "".join(
        f'<button type="button" role="tab" data-target="{_view_anchor(view)}">{html.escape(view)}</button>'
        for view in VIEWS
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
