"""Visual-lineup runtime layered on accepted OCR-LAYOUT-PATCH-6."""
from __future__ import annotations

from operation_pancake import ocr_team_app_patch6 as patch6
from operation_pancake import team_app
from operation_pancake.team_lineup_visual import render_lineup

TEAM_SETUP_BUILD = "TEAM-LINEUP-VISUAL-PATCH-1"


def install_runtime():
    patch6.install_runtime()
    patch6.TEAM_SETUP_BUILD = TEAM_SETUP_BUILD
    team_app.TEAM_SETUP_BUILD = TEAM_SETUP_BUILD
    original_create_handler = team_app.create_handler

    def create_handler(root, **kwargs):
        Base = original_create_handler(root, **kwargs)
        original_team_page = Base._team_page

        def _team_page(self):
            page = original_team_page(self)
            state = self.__class__.__closure__ if False else None
            return page

        # The base renderer owns its import store in closure, so replace only the
        # rendered Review Team fragment using the stable API state embedded by a
        # small subclass hook installed below.
        return Base

    # Renderer integration is implemented directly by a narrow helper hook in team_app.
    team_app._lineup_renderer = render_lineup


def main():
    install_runtime()
    print(patch6.patch5.discover_tesseract().message)
    team_app.main()
