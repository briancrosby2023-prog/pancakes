"""Supported Team Setup runtime with executable-verified OCR readiness."""
from __future__ import annotations

import csv
import io
import subprocess
from pathlib import Path

from operation_pancake import team_app
from operation_pancake.ocr_runtime import discover_tesseract
from operation_pancake.team_import import OCRObservation

TEAM_SETUP_BUILD = "OCR-RUNTIME-PATCH-1"
_ORIGINAL_UPLOAD_SURFACE = team_app._upload_surface


def _ocr(path: Path) -> list[OCRObservation] | None:
    runtime = discover_tesseract()
    if not runtime.ready or not runtime.executable:
        return None
    try:
        p = subprocess.run([runtime.executable, str(path), "stdout", "--psm", "11", "tsv"], capture_output=True, text=True, timeout=45, check=False)
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
            words.append(OCRObservation(text, (x / page_w, y / page_h, (x + w) / page_w, (y + h) / page_h), None if conf < 0 else conf / 100))
        return words
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return None


def _upload_surface():
    runtime = discover_tesseract()
    original = _ORIGINAL_UPLOAD_SURFACE()
    marker = '<span id="team-drop-status"'
    readiness = f'<br><span id="team-ocr-status" role="status">{runtime.message}</span>\n'
    return original.replace(marker, readiness + marker, 1).replace("TEAM SETUP BUILD: DROP-ZONE-PATCH-3", f"TEAM SETUP BUILD: {TEAM_SETUP_BUILD}", 1)


def install_runtime():
    team_app.TEAM_SETUP_BUILD = TEAM_SETUP_BUILD
    team_app._ocr = _ocr
    team_app._upload_surface = _upload_surface


def main():
    install_runtime()
    runtime = discover_tesseract()
    print(runtime.message)
    team_app.main()
