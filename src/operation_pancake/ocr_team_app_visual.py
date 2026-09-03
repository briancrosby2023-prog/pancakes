"""Production Team Setup: four screenshots -> C-3PO -> canonical CFB27 -> My Team."""
from __future__ import annotations

from operation_pancake import ocr_team_app_patch6 as patch6
from operation_pancake import product_app, team_app
from operation_pancake.c3po_team import GeminiTeamTranslator, candidates_from_observation
from operation_pancake.c3po_team_setup import apply_user_tackle_name
from operation_pancake.cfb27_ocr_match import match_candidate_cfb27
from operation_pancake.production.gm import GMProduct
from operation_pancake.team_import import TeamImportStore, VIEW_SLOTS
from operation_pancake.team_lineup_visual import render_lineup
from operation_pancake.team_slot_extraction import REAL_TEAM_MANAGER_SLOT_REGIONS

TEAM_SETUP_BUILD = "CFB27-TACKLE-VISUAL-PATH-1"


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
    patch6.patch5.match_candidate = match_candidate_cfb27
    team_app.match_candidate = match_candidate_cfb27
    fallback_extract = patch6._extract_current_batch

    def extract_with_match_evidence(state_store, gm):
        """C-3PO is the normal data-entry path; legacy OCR is only an availability fallback."""
        state = state_store.load()
        current = state.screenshots[-4:]
        if len(current) != 4:
            return fallback_extract(state_store, gm)
        try:
            translator = GeminiTeamTranslator()
            observations = [translator.translate(team_app.Path(row["path"])) for row in current]
        except (RuntimeError, OSError, ValueError, KeyError, team_app.json.JSONDecodeError):
            return fallback_extract(state_store, gm)
        views = [observation.view for observation in observations]
        if len(set(views)) != 4 or set(views) != set(VIEW_SLOTS):
            for row in current:
                row["extraction_status"] = "C-3PO READ — FOUR VIEWS NOT UNIQUE"
            state_store.save(state)
            return state
        candidates = []
        evidence = {}
        for shot, observation in zip(current, observations, strict=True):
            shot["view"] = observation.view
            shot["extraction_status"] = f"C-3PO READ — {observation.view}"
            rows = candidates_from_observation(
                observation, gm.population, shot["id"], start=len(candidates)
            )
            candidates.extend(rows)
            evidence[shot["id"]] = {
                "view": observation.view,
                "provider": observation.provider,
                "model": observation.model,
                "players_read": len(observation.players),
            }
        state.version = 3
        state.candidates = candidates
        state.team_observations = {
            "screenshots": evidence,
            "four_view_set_complete": True,
            "transcriber": "C-3PO",
        }
        state_store.save(state)
        return state

    team_app._extract = extract_with_match_evidence
    patch6.patch5.TEAM_SETUP_BUILD = TEAM_SETUP_BUILD
    team_app.TEAM_SETUP_BUILD = TEAM_SETUP_BUILD
    original_create_handler = team_app.create_handler

    def create_handler(root, **kwargs):
        Base = original_create_handler(root, **kwargs)
        imports = _closure_value(Base._team_page, TeamImportStore)
        gm = _closure_value(Base._team_page, GMProduct)

        class MyTeamHandler(Base):
            def _team_page(self):
                state = imports.load()
                current = state.screenshots[-4:]
                body = (
                    '<div class="hero"><h1>My Team</h1>'
                    '<p>Drop your four CFB27 Team Manager screenshots. '
                    'C-3PO reads the lineup; Pancake attaches the CFB27 cards.</p></div>'
                    + team_app._upload_surface()
                )
                if state.candidates:
                    body += (
                        '<form method="post" action="/team/confirm">'
                        '<div class="card"><h2>Roster</h2>'
                        '<p class="muted">EA OVR is what your lineup displayed. '
                        'Card OVR and ratings come from the canonical CFB27 card.</p>'
                        + render_lineup(state.candidates, gm.cards)
                        + "</div></form>"
                    )
                evidence = (
                    "".join(
                        "<li>" + team_app.html.escape(row["filename"]) + " — "
                        + team_app.html.escape(row["extraction_status"]) + "</li>"
                        for row in current
                    )
                    or "<li>No current batch yet.</li>"
                )
                body += (
                    '<details class="card" id="current-batch-evidence">'
                    f"<summary>Current batch evidence ({len(current)}/4)</summary>"
                    f"<ul>{evidence}</ul></details>"
                    '<details class="card" id="tackle-visual-diagnostics">'
                    '<summary>CFB27 tackle visual diagnostics</summary>'
                    '<p>Legacy diagnostics retained for developer compatibility; '
                    'the normal My Team path uses C-3PO transcription.</p></details>'
                )
                return product_app.page("My Team", body)

            def do_POST(self):
                path = team_app.urlparse(self.path).path
                if path == "/team/tackle-search":
                    form = team_app.parse_qs(
                        self.rfile.read(int(self.headers.get("Content-Length", "0"))).decode()
                    )
                    state = imports.load()
                    changed = False
                    for candidate in state.candidates:
                        query = form.get("player_name__" + candidate.id, [""])[0].strip()
                        if not query:
                            continue
                        apply_user_tackle_name(candidate, query, gm.population)
                        changed = True
                    if changed:
                        imports.save(state)
                    self.redir("/setup")
                    return
                super().do_POST()

        return MyTeamHandler

    team_app.create_handler = create_handler


def main():
    install_runtime()
    team_app.main()


if __name__ == "__main__":
    main()
