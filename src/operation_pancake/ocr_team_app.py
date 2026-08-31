"""Supported Team Setup runtime with executable-verified OCR and real Team Manager layouts."""
from __future__ import annotations

import csv
import io
import subprocess
from pathlib import Path

from operation_pancake import team_app
from operation_pancake.ocr_runtime import discover_tesseract
from operation_pancake.team_import import OCRObservation, SlotRegion

TEAM_SETUP_BUILD = "OCR-LAYOUT-PATCH-2"
_ORIGINAL_UPLOAD_SURFACE = team_app._upload_surface


def _r(slot: str, cx: float, y1: float, y2: float, width: float = 0.095) -> SlotRegion:
    """Starter nameplate region measured from the four real 2048x1536 Team Manager photos."""
    return SlotRegion(slot, (cx - width / 2, y1, cx + width / 2, y2))


# Each region is an independent EA Team Manager starter container.  Text outside
# these rectangles can never become part of that slot's player record.
REAL_TEAM_MANAGER_REGIONS = {
    "OFFENSE": [
        _r("LT1", .320, .405, .449), _r("LG1", .431, .405, .449),
        _r("C1", .544, .405, .449), _r("RG1", .656, .405, .449),
        _r("RT1", .768, .405, .449), _r("TE1", .880, .405, .449),
        _r("WR1", .320, .704, .752), _r("WR3", .431, .704, .752),
        _r("HB1", .544, .704, .752), _r("QB1", .656, .704, .752),
        _r("FB1", .768, .704, .752), _r("WR2", .880, .704, .752),
    ],
    "DEFENSE": [
        _r("FS1", .315, .426, .466), _r("WILL1", .418, .426, .466),
        _r("MIKE1", .522, .426, .466), _r("MIKE2", .625, .426, .466),
        _r("SAM1", .728, .426, .466), _r("SS1", .832, .426, .466),
        _r("CB1", .270, .690, .735), _r("CB3", .371, .690, .735),
        _r("REDG1", .472, .690, .735), _r("DT1", .573, .690, .735),
        _r("DT2", .674, .690, .735), _r("LEDG1", .775, .690, .735),
        _r("CB2", .876, .690, .735),
    ],
    "SPECIAL TEAMS": [
        _r("P1", .378, .435, .476), _r("K1", .468, .435, .476),
        _r("KR1", .700, .435, .476), _r("PR1", .802, .435, .476),
        _r("LS1", .378, .675, .716), _r("KOS1", .468, .675, .716),
    ],
    "SPECIALISTS": [
        _r("3DRB1", .365, .455, .505), _r("PWHB1", .468, .455, .505),
        _r("SLWR1", .570, .455, .505), _r("GAD1", .673, .455, .505),
        _r("NT1", .776, .455, .505),
        _r("SUBLB1", .365, .704, .755), _r("RRE1", .468, .704, .755),
        _r("RDT1", .570, .704, .755), _r("RLE1", .673, .704, .755),
        _r("SLCB1", .776, .704, .755),
    ],
}


def _ocr(path: Path) -> list[OCRObservation] | None:
    runtime = discover_tesseract()
    if not runtime.ready or not runtime.executable:
        return None
    try:
        p = subprocess.run(
            [runtime.executable, str(path), "stdout", "--psm", "11", "tsv"],
            capture_output=True, text=True, timeout=45, check=False,
        )
        if p.returncode != 0:
            return None
        rows = list(csv.DictReader(io.StringIO(p.stdout), delimiter="\t"))
        page_w = max([int(r.get("width") or 0) for r in rows if r.get("level") == "1"] or [1])
        page_h = max([int(r.get("height") or 0) for r in rows if r.get("level") == "1"] or [1])
        words = []
        for row in rows:
            text = (row.get("text") or "").strip()
            if not text:
                continue
            x, y, w, h = (int(row.get(k) or 0) for k in ("left", "top", "width", "height"))
            conf = float(row.get("conf") or -1)
            words.append(OCRObservation(
                text,
                (x / page_w, y / page_h, (x + w) / page_w, (y + h) / page_h),
                None if conf < 0 else conf / 100,
            ))
        return words
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return None


_VISUAL_LINEUP = r'''
<style>
.pancake-lineup{display:grid;gap:22px;margin:18px 0}.lineup-view{border:1px solid #334155;border-radius:18px;padding:16px}.lineup-view h3{margin:0 0 12px}.lineup-grid{display:grid;grid-template-columns:repeat(6,minmax(135px,1fr));gap:10px}.lineup-slot{border:1px solid #475569;border-radius:14px;padding:11px;min-height:150px;background:rgba(15,23,42,.28)}.lineup-slot strong{font-size:18px}.lineup-player{font-weight:800;margin-top:10px}.lineup-ovr,.lineup-match,.lineup-backups{font-size:13px;margin-top:6px}.lineup-unresolved{opacity:.72}.lineup-slot select{max-width:100%;margin-top:8px}@media(max-width:900px){.lineup-grid{grid-template-columns:repeat(2,minmax(135px,1fr))}}
</style>
<script>
(()=>{function buildVisualLineup(){
 const heading=Array.from(document.querySelectorAll('h2')).find(x=>x.textContent.trim()==='Review Team'); if(!heading)return;
 const table=heading.parentElement.querySelector('table'); if(!table||table.dataset.visualized==='1')return; table.dataset.visualized='1';
 const rows=Array.from(table.querySelectorAll('tr')).slice(1), order=['OFFENSE','DEFENSE','SPECIAL TEAMS','SPECIALISTS']; const groups=new Map(order.map(x=>[x,[]]));
 rows.forEach(row=>{const td=Array.from(row.querySelectorAll('td'));if(td.length<6)return;const view=td[0].textContent.trim(),slot=td[1].textContent.trim(),raw=td[2].textContent.trim(),ovr=td[3].textContent.trim(),status=td[5].textContent.trim();const select=td[4].querySelector('select');
  const card=document.createElement('div');card.className='lineup-slot';const unresolved=!raw||raw==='UNKNOWN';card.innerHTML=`<strong>${slot}</strong><div class="lineup-player ${unresolved?'lineup-unresolved':''}">${unresolved?'[UNRESOLVED PLAYER]':raw}</div><div class="lineup-ovr">OVR: ${!ovr||ovr==='UNKNOWN'?'?':ovr}</div><div class="lineup-match">CANONICAL PANCAKE MATCH: ${status||'UNRESOLVED'}</div><div class="lineup-backups">BACKUPS: none observed</div>`;if(select)card.append(select);(groups.get(view)||groups.get('SPECIALISTS')).push(card);
 });
 const shell=document.createElement('div');shell.className='pancake-lineup';order.forEach(view=>{const section=document.createElement('section');section.className='lineup-view';const h=document.createElement('h3');h.textContent=view;const grid=document.createElement('div');grid.className='lineup-grid';(groups.get(view)||[]).forEach(x=>grid.append(x));section.append(h,grid);shell.append(section)});heading.textContent='Visual Lineup';table.replaceWith(shell);
 }
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',buildVisualLineup,{once:true});else buildVisualLineup();})();
</script>
'''


def _upload_surface():
    runtime = discover_tesseract()
    original = _ORIGINAL_UPLOAD_SURFACE()
    marker = '<span id="team-drop-status"'
    readiness = f'<br><span id="team-ocr-status" role="status">{runtime.message}</span>\n'
    return original.replace(marker, readiness + marker, 1).replace(
        "TEAM SETUP BUILD: DROP-ZONE-PATCH-3", f"TEAM SETUP BUILD: {TEAM_SETUP_BUILD}", 1
    ) + _VISUAL_LINEUP


def install_runtime():
    team_app.TEAM_SETUP_BUILD = TEAM_SETUP_BUILD
    team_app.DEFAULT_REGIONS = REAL_TEAM_MANAGER_REGIONS
    team_app._ocr = _ocr
    team_app._upload_surface = _upload_surface


def main():
    install_runtime()
    runtime = discover_tesseract()
    print(runtime.message)
    team_app.main()
