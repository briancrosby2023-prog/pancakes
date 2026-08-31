"""PATCH-6 runtime: analyze only the current four-file Team Setup batch."""
from __future__ import annotations

from operation_pancake import ocr_team_app as patch5
from operation_pancake import team_app

TEAM_SETUP_BUILD = "OCR-LAYOUT-PATCH-6"


def _extract_current_batch(state_store, gm):
    """Discard historical screenshot attempts before classifying the current upload batch."""
    state = state_store.load()
    if len(state.screenshots) > 4:
        state.screenshots = state.screenshots[-4:]
        state.candidates = []
        state.team_observations = {}
        state_store.save(state)
    return patch5._extract_unique(state_store, gm)


def install_runtime():
    patch5.TEAM_SETUP_BUILD = TEAM_SETUP_BUILD
    patch5.install_runtime()
    team_app.TEAM_SETUP_BUILD = TEAM_SETUP_BUILD
    team_app._extract = _extract_current_batch


def main():
    install_runtime()
    print(patch5.discover_tesseract().message)
    team_app.main()
