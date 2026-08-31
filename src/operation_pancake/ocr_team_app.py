"""Supported Team Setup runtime with executable-verified OCR and real Team Manager layouts."""
from __future__ import annotations

import csv
import io
import subprocess
from pathlib import Path

from operation_pancake import team_app
from operation_pancake.ocr_runtime import discover_tesseract
from operation_pancake.team_import import OCRObservation, SlotRegion

TEAM_SETUP_BUILD = "OCR-LAYOUT-PATCH-1"
_ORIGINAL_UPLOAD_SURFACE = team_app._upload_surface


def _r(slot: str, cx: float, y1: float, y2: float, width: float = 0.095) -> SlotRegion:
    """Starter nameplate region measured from the four real 2048x1536 Team Manager photos."""
    return SlotRegion(slot, (cx - width / 2, y1, cx + width / 2, y2))


# These regions intentionally cover only the starter name/OVR nameplate, not the
# player-card artwork or backup rows.  The previous generic five-column grid
# included the left navigation and card art, which is why menu text became QB1
# and other slots in the real Opera run.
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


def _upload_surface():
    runtime = discover_tesseract()
    original = _ORIGINAL_UPLOAD_SURFACE()
    marker = '<span id="team-drop-status"'
    readiness = f'<br><span id="team-ocr-status" role="status">{runtime.message}</span>\n'
    return original.replace(marker, readiness + marker, 1).replace(
        "TEAM SETUP BUILD: DROP-ZONE-PATCH-3", f"TEAM SETUP BUILD: {TEAM_SETUP_BUILD}", 1
    )


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
