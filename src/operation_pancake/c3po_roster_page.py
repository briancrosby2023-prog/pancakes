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
.team-header .eyebrow{grid-column:1}.team-header h1{grid-column:1;font-size:26px}.team-subtitle{grid-column:1;margin-top:0}.team-header .update-team{grid-column:2;grid-row:1/4;position:static;align-self:center}
.lineup-tabs{display:flex;gap:32px;border-bottom:1px solid #26303b;margin:0 0 12px;padding:0 2px}.lineup-tabs button{appearance:none;background:none;border:0;position:relative;padding:11px 0 9px;color:#91a0b0;font:inherit;font-size:12px;font-weight:900;letter-spacing:.05em;white-space:nowrap;cursor:pointer}.lineup-tabs button.active{color:#f5f7fa}.lineup-tabs button.active:after{content:"";position:absolute;left:0;right:0;bottom:-1px;height:2px;background:#f5b642}
.roster-view{display:none;margin:0 0 18px}.roster-view.active{display:block}.section-heading{margin:0 0 8px;border:0}.section-heading h2{font-size:12px;margin:0;color:#f5b642;letter-spacing:.12em}
.position-grid{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:26px 12px;align-items:start}.position-group{min-width:0}.position-group h3{height:18px;margin:0 0 5px;color:#91a0b0;font-size:11px;font-weight:500;line-height:18px;text-align:center}
.feature-card{height:158px;position:relative;overflow:hidden;padding:9px;background:linear-gradient(145deg,#243246 0%,#15202d 48%,#0d141d 100%);border:1px solid #3b495a;border-radius:3px;box-shadow:0 5px 14px #0004}.feature-card:before{content:"";position:absolute;inset:0;background:linear-gradient(135deg,transparent 48%,#f5b64212 49%,transparent 52%);pointer-events:none}.feature-slot{position:relative;z-index:1;font-size:9px;line-height:12px;color:#a9b7c7}.feature-copy{position:absolute;z-index:1;left:9px;right:9px;bottom:10px;display:grid;gap:3px}.feature-ovr{font-size:27px;line-height:27px;font-weight:900;color:#fff}.feature-program{font-size:8px;line-height:10px;color:#9eabb9;text-transform:uppercase}.feature-program.program-missing{color:#718091}
.player-list{display:grid;gap:5px;margin-top:7px}.player-choice{appearance:none;width:100%;border:1px solid transparent;border-radius:2px;background:#3a4149;color:#fff;padding:7px 8px;display:grid;grid-template-columns:minmax(0,1fr) auto;gap:3px 7px;text-align:left;cursor:pointer;font:inherit}.player-choice:hover{background:#444d57}.player-choice.selected{border-color:#f5b642;background:#454b52}.choice-name{grid-column:1;grid-row:1;font-size:10px;line-height:12px;font-weight:900;text-transform:uppercase;overflow-wrap:normal}.choice-ovr{grid-column:2;grid-row:1;font-size:13px;line-height:13px;font-weight:900;text-align:right;white-space:nowrap}.choice-program{grid-column:1/3;grid-row:2;font-size:7px;line-height:8px;color:#b1bbc6;text-transform:uppercase}.choice-program.program-missing{color:#778593}.empty-view{grid-column:1/-1;color:#697888}
@media(max-width:820px){.position-grid{grid-template-columns:repeat(3,minmax(0,1fr))}.feature-card{height:165px}}@media(max-width:620px){.position-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.lineup-tabs{gap:18px;overflow-x:auto}.team-header{grid-template-columns:1fr}.team-header .update-team{grid-column:1;grid-row:auto;justify-self:start}.feature-card{height:155px}}@media(max-width:420px){.position-grid{grid-template-columns:1fr}.feature-card{height:145px}.lineup-tabs{gap:14px}}
</style>
<script>
document.addEventListener("DOMContentLoaded",()=>{
 const root=document.getElementById("my-team");if(!root)return;
 const tabs=[...root.querySelectorAll(".lineup-tabs button")],views=[...root.querySelectorAll(".roster-view")];
 const show=id=>{tabs.forEach(t=>{const on=t.dataset.target===id;t.classList.toggle("active",on);t.setAttribute("aria-selected",on?"true":"false")});views.forEach(v=>v.classList.toggle("active",v.id===id))};
 tabs.forEach(t=>t.addEventListener("click",()=>show(t.dataset.target)));if(tabs.length)show(tabs[0].dataset.target);
 root.querySelectorAll(".position-group").forEach(group=>{const card=group.querySelector(".feature-card"),choices=[...group.querySelectorAll(".player-choice")];if(!card||!choices.length)return;const select=choice=>{choices.forEach(c=>c.classList.toggle("selected",c===choice));card.querySelector(".feature-slot").textContent=choice.dataset.slot;card.querySelector(".feature-ovr").textContent=choice.dataset.ovr+" OVR";const program=card.querySelector(".feature-program");program.textContent=choice.dataset.program;program.classList.toggle("program-missing",choice.dataset.missing==="1")};choices.forEach(choice=>choice.addEventListener("click",()=>select(choice)));select(choices[0])});
});
</script>
"""

OFFENSE_POSITION_ORDER = ("LT", "LG", "C", "RG", "RT", "TE", "WR1", "WR3", "HB", "QB", "FB", "WR2")


def _program_value(card_observation) -> tuple[str, bool]:
    if card_observation is not None and getattr(card_observation, "state", None) == "IDENTIFIED" and getattr(card_observation, "program", None):
        return card_observation.program, False
    return "CARD NOT READ", True


def _player_choice(player, card_observation=None, *, selected: bool) -> str:
    name = player.name if player.name and player.name.strip() else "NAME NOT READ"
    ovr = "—" if player.displayed_ovr is None else str(player.displayed_ovr)
    program, missing = _program_value(card_observation)
    selected_class = " selected" if selected else ""
    return (
        f'<button type="button" class="player-choice{selected_class}" data-slot="{html.escape(player.slot)}" data-ovr="{html.escape(ovr)}" '
        f'data-program="{html.escape(program)}" data-missing="{1 if missing else 0}">'
        f'<strong class="choice-name">{html.escape(name)}</strong><span class="choice-ovr">{html.escape(ovr)}</span>'
        f'<span class="choice-program{" program-missing" if missing else ""}">{html.escape(program)}</span></button>'
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
        return LINEUP_STYLE + '<section id="my-team" class="team-panel"><header class="team-header"><p class="eyebrow">OPERATION PANCAKE</p><h1>My Team</h1></header><p class="provider-failure">C-3PO could not read the screenshots. Your previous roster was not replaced.</p></section>'
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
            if program is not None and (getattr(program, "player_name", None) != (player.name or "") or getattr(program, "displayed_ovr", None) != player.displayed_ovr):
                program = None
            groups.setdefault(position, []).append((depth, player, program))
        cards = []
        for position, rows in _ordered_groups(view, groups):
            ordered = sorted(rows, key=lambda row: row[0])
            first_player, first_program = ordered[0][1], ordered[0][2]
            first_ovr = "—" if first_player.displayed_ovr is None else str(first_player.displayed_ovr)
            first_program_text, first_missing = _program_value(first_program)
            choices = "".join(_player_choice(player, program, selected=index == 0) for index, (_depth, player, program) in enumerate(ordered))
            cards.append(
                f'<section class="position-group"><h3>{html.escape(position)}</h3>'
                f'<div class="feature-card"><span class="feature-slot">{html.escape(first_player.slot)}</span>'
                f'<div class="feature-copy"><strong class="feature-ovr">{html.escape(first_ovr)} OVR</strong>'
                f'<span class="feature-program{" program-missing" if first_missing else ""}">{html.escape(first_program_text)}</span></div></div>'
                f'<div class="player-list">{choices}</div></section>'
            )
        empty = '<p class="empty-view">No observations reported.</p>' if not cards else ""
        active = " active" if view_index == 0 else ""
        sections.append(f'<section id="{_view_anchor(view)}" class="roster-view{active}" data-view="{html.escape(view)}"><div class="section-heading"><h2>{html.escape(view)}</h2></div><div class="position-grid">{"".join(cards)}{empty}</div></section>')
    tabs = '<nav class="lineup-tabs" role="tablist" aria-label="Lineup sections">' + "".join(f'<button type="button" role="tab" data-target="{_view_anchor(view)}">{html.escape(view)}</button>' for view in VIEWS) + "</nav>"
    return LINEUP_STYLE + '<section id="my-team" class="team-panel"><header class="team-header"><p class="eyebrow">OPERATION PANCAKE</p><h1>My Team</h1><p class="team-subtitle">Your lineup, read directly from EA Team Manager.</p><a class="update-team" href="/setup">UPDATE TEAM</a></header>' + tabs + "".join(sections) + "</section>"
