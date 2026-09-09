import json
from pathlib import Path

from PIL import Image


def test_current_exact_page_art_has_one_normalized_card_size():
    root = Path(__file__).parents[1]
    state = json.loads((root / ".operation_pancake/c3po-programs.json").read_text())
    card_ids = {row["card_id"] for row in state["observations"] if row.get("card_id")}
    sizes = {
        Image.open(root / "data/production/card_art" / f"{card_id.replace(':', '-')}-page.png").size
        for card_id in card_ids
    }

    assert sizes == {(268, 382)}
