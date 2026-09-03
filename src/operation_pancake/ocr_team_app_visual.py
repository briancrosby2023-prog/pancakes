"""Visual-lineup runtime layered on accepted OCR-LAYOUT-PATCH-6."""

from __future__ import annotations

from pathlib import Path

from operation_pancake import ocr_team_app_patch6 as patch6
from operation_pancake import product_app, team_app
from operation_pancake.c3po_team_setup import (
    apply_user_tackle_name,
    select_user_tackle_card,
)
from operation_pancake.cfb27_ocr_match import candidate_diagnostics, match_candidate_cfb27
from operation_pancake.production.gm import GMProduct
from operation_pancake.roster_state import RosterStore
from operation_pancake.tackle_screenshot_recognition import (
    TACKLE_SLOTS,
    recognize_tackle_candidate,
)
from operation_pancake.tackle_visual_pilot import load_index
from operation_pancake.team_import import TeamImportStore
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

    original_extract = patch6._extract_current_batch

    def extract_with_match_evidence(state_store, gm):
        state = original_extract(state_store, gm)
        by_shot = state.team_observations.get("screenshots", {})
        tackle_index_path = gm.root / "data/production/cfb27_tackle_visual_index.json.gz"
        tackle_index = load_index(tackle_index_path)
        offense_regions = {
            region.slot: region for region in REAL_TEAM_MANAGER_SLOT_REGIONS["OFFENSE"]
        }
        for candidate in state.candidates:
            shot_id, shot = next(
                (
                    (key, row)
                    for key, row in by_shot.items()
                    if row.get("view") == candidate.group
                ),
                (None, None),
            )
            if shot is None:
                continue
            slot = shot.get("slot_crop_ocr", {}).get(candidate.slot, {})
            slot["match"] = candidate_diagnostics(candidate, gm.population)
            if candidate.slot not in TACKLE_SLOTS:
                continue
            source = next(
                (row for row in state.screenshots if row.get("id") == shot_id), None
            )
            region = offense_regions.get(candidate.slot)
            if source is None or region is None:
                slot["visual_recognition"] = {
                    "decision": "UNRESOLVED",
                    "reason": "source-screenshot-or-region-missing",
                }
                candidate.player_name = None
                candidate.canonical_card_id = None
                candidate.confidence = None
                candidate.match_status = "UNRESOLVED"
                continue
            slot["visual_recognition"] = recognize_tackle_candidate(
                Path(source["path"]), candidate, region, slot, tackle_index
            )
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
        roster = _closure_value(Base.do_POST, RosterStore)

        class VisualHandler(Base):
            def _team_page(self):
                state = imports.load()
                current = state.screenshots[-4:]
                evidence = (
                    "".join(
                        "<li>"
                        + team_app.html.escape(x["filename"])
                        + " — "
                        + team_app.html.escape(x["extraction_status"])
                        + "</li>"
                        for x in current
                    )
                    or "<li>No current batch yet.</li>"
                )
                body = (
                    '<div class="hero"><h1>Team Setup</h1>'
                    "<p>Scan the lineup first. Review unresolved matches only where needed.</p>"
                    "</div>"
                    + team_app._upload_surface()
                )
                if state.candidates:
                    body += (
                        '<form method="post" action="/team/confirm">'
                        + render_lineup(state.candidates, gm.cards)
                        + "</form>"
                    )
                tackle_diagnostics = {
                    candidate.slot: candidate.match_diagnostics
                    for candidate in state.candidates
                    if candidate.slot in TACKLE_SLOTS
                }
                body += (
                    '<details class="card" id="tackle-visual-diagnostics">'
                    "<summary>CFB27 tackle visual diagnostics</summary>"
                    "<p>LT/RT only · real uploaded pixels · 638-card CFB27 index</p>"
                    "<pre style=\"white-space:pre-wrap;overflow-wrap:anywhere\">"
                    + team_app.html.escape(
                        team_app.json.dumps(tackle_diagnostics, indent=2, sort_keys=True)
                    )
                    + "</pre></details>"
                )
                body += (
                    '<details class="card" id="current-batch-evidence">'
                    f"<summary>Current batch evidence ({len(current)}/4)</summary>"
                    f"<ul>{evidence}</ul></details>"
                )
                return product_app.page("Team Setup", body)

            def do_POST(self):
                path = team_app.urlparse(self.path).path
                if path == "/team/tackle-search":
                    form = team_app.parse_qs(
                        self.rfile.read(int(self.headers.get("Content-Length", "0"))).decode()
                    )
                    state = imports.load()
                    changed = False
                    for candidate in state.candidates:
                        if candidate.slot not in TACKLE_SLOTS:
                            continue
                        query = form.get("player_name__" + candidate.id, [""])[0].strip()
                        if not query:
                            continue
                        apply_user_tackle_name(candidate, query, gm.population)
                        changed = True
                    if changed:
                        imports.save(state)
                    self.redir("/setup")
                    return
                if path == "/team/confirm":
                    form = team_app.parse_qs(
                        self.rfile.read(int(self.headers.get("Content-Length", "0"))).decode()
                    )
                    state = imports.load()
                    fallback_changed = False
                    for candidate in state.candidates:
                        selected = form.get("card__" + candidate.id, [""])[0]
                        if (
                            candidate.slot in TACKLE_SLOTS
                            and selected
                            and candidate.match_diagnostics.get("user_name_fallback")
                        ):
                            fallback_changed = (
                                select_user_tackle_card(candidate, selected, gm.population)
                                or fallback_changed
                            )
                    if fallback_changed:
                        imports.save(state)
                    byslot = {row.slot: row for row in roster.load()}
                    for candidate in state.candidates:
                        card_id = form.get("card__" + candidate.id, [""])[0]
                        slot = candidate.slot.upper().strip()
                        if not card_id or not slot:
                            continue
                        card = gm.cards.get(card_id)
                        if not card:
                            continue
                        base = "".join(ch for ch in slot if not ch.isdigit())
                        kind = (
                            "SPECIALIST"
                            if base in team_app.SPECIALIST_SLOTS
                            else "ROSTER"
                        )
                        byslot[slot] = team_app.RosterAssignment(
                            card_id,
                            card.get("position") or candidate.position or base,
                            slot,
                            True,
                            True,
                            observed_overall=candidate.displayed_ovr,
                            observed_ratings=candidate.observed_ratings,
                            evidence=candidate.provenance,
                            assignment_kind=kind,
                        )
                    roster.save(list(byslot.values()))
                    self.redir("/roster")
                    return
                super().do_POST()

        return VisualHandler

    team_app.create_handler = create_handler


def main():
    install_runtime()
    print(patch6.patch5.discover_tesseract().message)
    team_app.main()


if __name__ == "__main__":
    main()
