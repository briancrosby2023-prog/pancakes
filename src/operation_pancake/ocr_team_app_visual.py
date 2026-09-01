"""Visual-lineup runtime layered on accepted OCR-LAYOUT-PATCH-6."""
from __future__ import annotations

from operation_pancake import ocr_team_app_patch6 as patch6
from operation_pancake import product_app, team_app
from operation_pancake.cfb27_ocr_match import match_candidate_cfb27
from operation_pancake.production.gm import GMProduct
from operation_pancake.team_import import TeamImportStore
from operation_pancake.team_lineup_visual import render_lineup
from operation_pancake.team_slot_extraction import REAL_TEAM_MANAGER_SLOT_REGIONS

TEAM_SETUP_BUILD = "CFB27-REAL-IMAGE-MATCH-PATCH-1"


def _closure_value(fn, cls):
    for cell in fn.__closure__ or ():
        try:
            value = cell.cell_contents
        except ValueError:
            continue
        if isinstance(value, cls):
            return value
    raise RuntimeError(f"Team Setup renderer missing {cls.__name__} closure")


def install_runtime():
    patch6.install_runtime()
    patch6.patch5.REAL_TEAM_MANAGER_REGIONS = REAL_TEAM_MANAGER_SLOT_REGIONS
    team_app.DEFAULT_REGIONS = REAL_TEAM_MANAGER_SLOT_REGIONS
    # _extract_unique lives in patch5 and imported match_candidate into that
    # module at import time. Patch the binding it actually calls, not only the
    # similarly named team_app attribute. This is the production image -> OCR
    # -> structured slot -> CFB27 matching path used by operation-pancake-app.
    patch6.patch5.match_candidate = match_candidate_cfb27
    team_app.match_candidate = match_candidate_cfb27
    # Preserve PATCH-6's own module identity so its isolated regression tests
    # remain meaningful. Only the live lower-level/runtime surface receives the
    # visual layer's build marker.
    patch6.patch5.TEAM_SETUP_BUILD = TEAM_SETUP_BUILD
    team_app.TEAM_SETUP_BUILD = TEAM_SETUP_BUILD
    original_create_handler = team_app.create_handler

    def create_handler(root, **kwargs):
        Base = original_create_handler(root, **kwargs)
        imports = _closure_value(Base._team_page, TeamImportStore)
        gm = _closure_value(Base._team_page, GMProduct)

        class VisualHandler(Base):
            def _team_page(self):
                state = imports.load()
                current = state.screenshots[-4:]
                evidence = "".join(
                    f'<li>{team_app.html.escape(x["filename"])} — {team_app.html.escape(x["extraction_status"])}</li>'
                    for x in current
                ) or "<li>No current batch yet.</li>"
                body = (
                    '<div class="hero"><h1>Team Setup</h1><p>Scan the lineup first. Review unresolved matches only where needed.</p></div>'
                    + team_app._upload_surface()
                )
                if state.candidates:
                    body += '<form method="post" action="/team/confirm">' + render_lineup(state.candidates, gm.cards) + '</form>'
                body += f'<details class="card" id="current-batch-evidence"><summary>Current batch evidence ({len(current)}/4)</summary><ul>{evidence}</ul></details>'
                return product_app.page("Team Setup", body)

        return VisualHandler

    team_app.create_handler = create_handler


def main():
    install_runtime()
    print(patch6.patch5.discover_tesseract().message)
    team_app.main()
