"""PATCH-6 runtime: analyze only the current four-file Team Setup batch."""
from __future__ import annotations

import os

from operation_pancake import ocr_team_app as patch5
from operation_pancake import team_app
from operation_pancake.c3po_team_setup import integrate_offense_tackles
from operation_pancake.c3po_vision import GeminiScreenshotTranslator

TEAM_SETUP_BUILD = "OCR-LAYOUT-PATCH-6"
C3PO_TRANSLATOR_FACTORY = GeminiScreenshotTranslator


def _extract_current_batch(state_store, gm):
    """Discard history, run accepted OCR, then overlay bounded C-3PO LT/RT."""
    state = state_store.load()
    if len(state.screenshots) > 4:
        state.screenshots = state.screenshots[-4:]
        state.candidates = []
        state.team_observations = {}
        state_store.save(state)
    state = patch5._extract_unique(state_store, gm)
    if os.getenv("GEMINI_API_KEY"):
        return integrate_offense_tackles(state_store, gm.population, C3PO_TRANSLATOR_FACTORY())
    return state


def install_runtime():
    patch5.TEAM_SETUP_BUILD = TEAM_SETUP_BUILD
    patch5.install_runtime()
    team_app.TEAM_SETUP_BUILD = TEAM_SETUP_BUILD
    team_app._extract = _extract_current_batch


def main():
    install_runtime()
    print(patch5.discover_tesseract().message)
    team_app.main()
