from pathlib import Path

from PIL import Image

from operation_pancake.c3po_card_version import C3POCardObservationStore
from operation_pancake.c3po_roster import (
    C3PORosterStore,
    observation_fingerprint,
    roster_observations,
)


def _current_rows(root: Path):
    roster = C3PORosterStore(root / ".operation_pancake/c3po-roster.json").load()
    programs = C3POCardObservationStore(root / ".operation_pancake/c3po-programs.json").load()
    return [
        programs[observation_fingerprint(player, occurrence)]
        for occurrence, player in roster_observations(roster)
    ]


def test_current_exact_page_art_is_dom_card_element_size():
    root = Path(__file__).parents[1]
    rows = [row for row in _current_rows(root) if row.card_id]
    sizes = {
        Image.open(
            root / "data/production/card_art" / f"{row.card_id.replace(':', '-')}-page.png"
        ).size
        for row in rows
    }
    assert len(rows) == 79
    assert sizes == {(280, 374)}


def test_current_resolved_rows_use_exact_card_page_assets():
    root = Path(__file__).parents[1]
    rows = [row for row in _current_rows(root) if row.card_id]
    assert len(rows) == 79
    assert all(
        row.art_asset == f"data/production/card_art/{row.card_id.replace(':', '-')}-page.png"
        for row in rows
    )
