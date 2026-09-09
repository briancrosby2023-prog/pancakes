import json
from pathlib import Path

from PIL import Image


def test_current_exact_page_art_uses_visible_card_bounds():
    root = Path(__file__).parents[1]
    state = json.loads((root / ".operation_pancake/c3po-programs.json").read_text())
    page_ids = {
        row["card_id"]
        for row in state["observations"]
        if row.get("card_id") and str(row.get("art_asset", "")).endswith("-page.png")
    }
    sizes = {
        Image.open(root / "data/production/card_art" / f"{card_id.replace(':', '-')}-page.png").size
        for card_id in page_ids
    }

    assert sizes == {(254, 356)}
