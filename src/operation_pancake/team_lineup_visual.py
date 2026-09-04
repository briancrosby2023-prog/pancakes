"""Compact observation-first visual lineup renderer for My Team."""
from __future__ import annotations

import html

from operation_pancake.team_import import VIEW_SLOTS

VIEW_ORDER = ("OFFENSE", "DEFENSE", "SPECIAL TEAMS", "SPECIALISTS")


def _card_label(candidate, cards):
    if not candidate.canonical_card_id:
        return None
    card = cards.get(candidate.canonical_card_id) or {}
    name = card.get("player_name") or candidate.canonical_card_id
    position = card.get("position")
    ovr = card.get("native_overall")
    program = card.get("program")
    bits = [str(name)]
    if position:
        bits.append(str(position))
    if ovr is not None:
        bits.append(f"CARD OVR {ovr}")
    if program:
        bits.append(str(program))
    return " · ".join(bits)


def _enrichment_status(candidate):
    if not candidate.player_name:
        return "PLAYER UNRESOLVED"
    if candidate.canonical_card_id:
        return ""
    if candidate.match_status == "AMBIGUOUS_CARD":
        return "CFB27 CARD: SELECT CARD"
    return "CFB27 DATA NOT LINKED"


def _backup(row):
    name = html.escape(row.get("player_name") or "UNRESOLVED")
    ovr = str(row.get("displayed_ovr")) if row.get("displayed_ovr") is not None else "—"
    status = row.get("enrichment_status")
    if row.get("player_name") and status == "not-linked":
        detail = '<small>CFB27 DATA NOT LINKED</small>'
    elif row.get("player_name") and status == "ambiguous-card":
        detail = '<small>CFB27 CARD: SELECT CARD</small>'
    else:
        detail = ""
    return (
        '<div class="lineup-backup"><span>↳ '
        + name
        + detail
        + '</span><b>'
        + ovr
        + "</b></div>"
    )


def _slot(candidate, cards):
    name = html.escape(candidate.player_name or "UNRESOLVED")
    ovr = str(candidate.displayed_ovr) if candidate.displayed_ovr is not None else "—"
    match = _card_label(candidate, cards)
    match_html = f'<div class="lineup-match">{html.escape(match)}</div>' if match else ""
    status = _enrichment_status(candidate)
    status_html = f'<div class="lineup-status">{html.escape(status)}</div>' if status else ""
    backups = "".join(_backup(row) for row in candidate.backups)
    return (
        f'<div class="lineup-slot" data-slot="{html.escape(candidate.slot)}">'
        f'<div class="lineup-position">{html.escape(candidate.slot)}</div>'
        f'<div class="lineup-starter"><strong>{name}</strong>'
        f'<span class="lineup-ovr" title="EA displayed OVR">{ovr}</span></div>'
        f'{match_html}{status_html}{backups}</div>'
    )


def render_lineup(candidates, cards):
    by_view = {
        view: {candidate.slot: candidate for candidate in candidates if candidate.group == view}
        for view in VIEW_ORDER
    }
    tabs = "".join(
        f'<button type="button" class="lineup-tab" data-lineup-tab="{i}" '
        f'aria-selected="{str(i == 0).lower()}">{html.escape(view)}</button>'
        for i, view in enumerate(VIEW_ORDER)
    )
    panels = []
    for i, view in enumerate(VIEW_ORDER):
        slots = []
        for slot in VIEW_SLOTS[view]:
            candidate = by_view[view].get(slot)
            if candidate:
                slots.append(_slot(candidate, cards))
            else:
                slots.append(
                    f'<div class="lineup-slot lineup-empty" data-slot="{html.escape(slot)}">'
                    f'<div class="lineup-position">{html.escape(slot)}</div>'
                    '<div class="lineup-starter"><strong>UNRESOLVED</strong>'
                    '<span class="lineup-ovr">—</span></div></div>'
                )
        panels.append(
            f'<section class="lineup-panel" data-lineup-panel="{i}" '
            f'{"" if i == 0 else "hidden"}><div class="lineup-grid '
            f'lineup-{view.lower().replace(" ", "-")}">{"".join(slots)}</div></section>'
        )
    return f'''<style>
.lineup-shell{{padding:14px}}.lineup-tabs{{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:12px}}.lineup-tab{{padding:8px 14px;font-weight:800}}.lineup-tab[aria-selected="true"]{{outline:2px solid currentColor}}.lineup-grid{{display:grid;grid-template-columns:repeat(6,minmax(120px,1fr));gap:8px;align-items:start}}.lineup-defense{{grid-template-columns:repeat(7,minmax(110px,1fr))}}.lineup-special-teams,.lineup-specialists{{grid-template-columns:repeat(5,minmax(130px,1fr))}}.lineup-slot{{border:1px solid rgba(127,127,127,.35);border-radius:10px;padding:8px;min-height:72px}}.lineup-position{{font-size:12px;font-weight:900;opacity:.72;letter-spacing:.08em}}.lineup-starter{{display:flex;justify-content:space-between;gap:6px;align-items:baseline;margin-top:4px}}.lineup-starter strong{{font-size:15px;line-height:1.15}}.lineup-ovr{{font-size:20px;font-weight:900}}.lineup-match,.lineup-status{{font-size:11px;opacity:.72;margin-top:3px}}.lineup-backup{{display:flex;justify-content:space-between;gap:5px;border-top:1px solid rgba(127,127,127,.25);margin-top:5px;padding-top:4px;font-size:12px}}.lineup-backup small{{display:block;font-size:9px;opacity:.68}}@media(max-width:900px){{.lineup-grid,.lineup-defense,.lineup-special-teams,.lineup-specialists{{grid-template-columns:repeat(2,minmax(140px,1fr))}}}}
</style><div class="card lineup-shell"><h2>Your Lineup</h2><div class="lineup-tabs" role="tablist">{tabs}</div>{''.join(panels)}<button>IMPORT TEAM</button></div><script>(()=>{{const tabs=[...document.querySelectorAll('[data-lineup-tab]')],panels=[...document.querySelectorAll('[data-lineup-panel]')];tabs.forEach((tab,i)=>tab.addEventListener('click',()=>{{tabs.forEach((x,j)=>x.setAttribute('aria-selected',String(i===j)));panels.forEach((x,j)=>x.hidden=i!==j);}}));}})();</script>'''
