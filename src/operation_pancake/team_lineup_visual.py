"""Compact visual lineup renderer for Team Setup."""
from __future__ import annotations

import html

from operation_pancake.team_import import VIEW_SLOTS

VIEW_ORDER = ("OFFENSE", "DEFENSE", "SPECIAL TEAMS", "SPECIALISTS")
TACKLE_SLOTS = {"LT1", "RT1"}


def _card_label(candidate, cards):
    if not candidate.canonical_card_id:
        return None
    card = cards.get(candidate.canonical_card_id) or {}
    name = card.get("player_name") or candidate.player_name or candidate.canonical_card_id
    ovr = card.get("native_overall")
    program = card.get("program")
    bits = [str(name)]
    if ovr is not None:
        bits.append(str(ovr))
    if program:
        bits.append(str(program))
    return " · ".join(bits)


def _fallback_options(candidate, cards):
    fallback = candidate.match_diagnostics.get("user_name_fallback", {})
    out = []
    for card_id in fallback.get("result_card_ids") or []:
        card = cards.get(card_id) or {}
        name = card.get("player_name") or card_id
        position = card.get("position") or candidate.position or ""
        ovr = card.get("native_overall")
        program = card.get("program") or ""
        label = " · ".join(
            bit
            for bit in (
                str(name),
                str(position),
                str(ovr) if ovr is not None else "",
                str(program),
            )
            if bit
        )
        out.append((card_id, label))
    return out


def _slot(candidate, cards):
    name = html.escape(candidate.player_name or "UNRESOLVED")
    ovr = str(candidate.displayed_ovr) if candidate.displayed_ovr is not None else "—"
    match = _card_label(candidate, cards)
    match_html = f'<div class="lineup-match">{html.escape(match)}</div>' if match else ""
    status = ""
    if candidate.match_status not in {"MATCHED", "UNRESOLVED", "UNMATCHED"}:
        status = f'<div class="lineup-status">{html.escape(candidate.match_status)}</div>'
    backups = "".join(
        '<div class="lineup-backup"><span>↳ '
        + html.escape(x.get("player_name") or "UNRESOLVED")
        + '</span><b>'
        + (str(x.get("displayed_ovr")) if x.get("displayed_ovr") is not None else "—")
        + "</b></div>"
        for x in candidate.backups
    )

    controls = ""
    if candidate.slot in TACKLE_SLOTS and not candidate.canonical_card_id:
        query = candidate.match_diagnostics.get("user_name_fallback", {}).get("query", "")
        controls = (
            '<div class="lineup-fallback-wrap">'
            '<label class="lineup-fallback">WHO IS THIS PLAYER?'
            f'<input name="player_name__{html.escape(candidate.id)}" '
            f'value="{html.escape(query)}" autocomplete="off" '
            'placeholder="Type player name"></label>'
            '<button class="lineup-search" type="submit" formaction="/team/tackle-search" '
            'formmethod="post">SEARCH CFB27</button>'
        )
        option_rows = _fallback_options(candidate, cards)
        if option_rows:
            controls += (
                f'<select class="lineup-select" name="card__{html.escape(candidate.id)}" '
                f'aria-label="Canonical match for {html.escape(candidate.slot)}">'
                '<option value="">SELECT CFB27 CARD</option>'
                + "".join(
                    f'<option value="{html.escape(card_id)}">{html.escape(label)}</option>'
                    for card_id, label in option_rows
                )
                + "</select>"
            )
        controls += "</div>"

    return (
        f'<div class="lineup-slot" data-slot="{html.escape(candidate.slot)}">'
        f'<div class="lineup-position">{html.escape(candidate.slot)}</div>'
        f'<div class="lineup-starter"><strong>{name}</strong><span class="lineup-ovr">{ovr}</span></div>'
        f'{match_html}{status}{backups}{controls}</div>'
    )


def render_lineup(candidates, cards):
    by_view = {
        view: {c.slot: c for c in candidates if c.group == view} for view in VIEW_ORDER
    }
    tabs = "".join(
        f'<button type="button" class="lineup-tab" data-lineup-tab="{i}" aria-selected="{str(i == 0).lower()}">{html.escape(view)}</button>'
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
                    f'<div class="lineup-slot lineup-empty" data-slot="{html.escape(slot)}"><div class="lineup-position">{html.escape(slot)}</div><div class="lineup-starter"><strong>UNRESOLVED</strong><span class="lineup-ovr">—</span></div></div>'
                )
        panels.append(
            f'<section class="lineup-panel" data-lineup-panel="{i}" {"" if i == 0 else "hidden"}><div class="lineup-grid lineup-{view.lower().replace(" ", "-")}">{"".join(slots)}</div></section>'
        )
    return f'''<style>
.lineup-shell{{padding:14px}}.lineup-tabs{{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:12px}}.lineup-tab{{padding:8px 14px;font-weight:800}}.lineup-tab[aria-selected="true"]{{outline:2px solid currentColor}}.lineup-grid{{display:grid;grid-template-columns:repeat(6,minmax(120px,1fr));gap:8px;align-items:start}}.lineup-defense{{grid-template-columns:repeat(7,minmax(110px,1fr))}}.lineup-special-teams,.lineup-specialists{{grid-template-columns:repeat(5,minmax(130px,1fr))}}.lineup-slot{{border:1px solid rgba(127,127,127,.35);border-radius:10px;padding:8px;min-height:72px}}.lineup-position{{font-size:12px;font-weight:900;opacity:.72;letter-spacing:.08em}}.lineup-starter{{display:flex;justify-content:space-between;gap:6px;align-items:baseline;margin-top:4px}}.lineup-starter strong{{font-size:15px;line-height:1.15}}.lineup-ovr{{font-size:20px;font-weight:900}}.lineup-match,.lineup-status{{font-size:11px;opacity:.72;margin-top:3px}}.lineup-backup{{display:flex;justify-content:space-between;gap:5px;border-top:1px solid rgba(127,127,127,.25);margin-top:5px;padding-top:4px;font-size:12px}}.lineup-fallback-wrap{{margin-top:7px;padding-top:7px;border-top:1px solid rgba(127,127,127,.25)}}.lineup-fallback{{display:block;font-size:10px;font-weight:800}}.lineup-fallback input{{width:100%;box-sizing:border-box;margin-top:3px}}.lineup-search{{width:100%;font-size:10px;margin-top:4px}}.lineup-select{{width:100%;font-size:11px;margin-top:6px}}@media(max-width:900px){{.lineup-grid,.lineup-defense,.lineup-special-teams,.lineup-specialists{{grid-template-columns:repeat(2,minmax(140px,1fr))}}}}
</style><div class="card lineup-shell"><h2>Your Lineup</h2><div class="lineup-tabs" role="tablist">{tabs}</div>{''.join(panels)}<button>IMPORT TEAM</button></div><script>(()=>{{const tabs=[...document.querySelectorAll('[data-lineup-tab]')],panels=[...document.querySelectorAll('[data-lineup-panel]')];tabs.forEach((tab,i)=>tab.addEventListener('click',()=>{{tabs.forEach((x,j)=>x.setAttribute('aria-selected',String(i===j)));panels.forEach((x,j)=>x.hidden=i!==j);}}));}})();</script>'''