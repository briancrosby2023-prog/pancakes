import json
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


def test_current_mapped_statless_art_is_uniform_source_size():
    root = Path(__file__).parents[1]
    all_rows = _current_rows(root)
    rows = [row for row in all_rows if row.card_id]
    sizes = {Image.open(root / row.art_asset).size for row in rows if row.art_asset}
    assert len(all_rows) == 79
    assert rows
    assert sizes == {(440, 588)}


def test_current_resolved_rows_use_exact_statless_assets():
    root = Path(__file__).parents[1]
    all_rows = _current_rows(root)
    rows = [row for row in all_rows if row.card_id]
    assert len(all_rows) == 79
    assert rows
    assert all(
        row.art_asset == f"data/production/card_art/{row.card_id.replace(':', '-')}.png"
        for row in rows
    )


def test_current_mappings_never_borrow_different_ovr_instance():
    root = Path(__file__).parents[1]
    cards = json.loads((root / "data/production/cfb27_scored_population.json").read_text())
    by_id = {card["card_id"]: card for card in cards}
    rows = _current_rows(root)
    assert len(rows) == 79
    assert all(
        row.card_id is None or by_id[row.card_id].get("native_overall") == row.displayed_ovr
        for row in rows
    )
