from __future__ import annotations

from pathlib import Path

from PIL import Image

from operation_pancake.tackle_visual_pilot import (
    IndexedTackle,
    TackleCard,
    fingerprint,
    index_from_payload,
    index_to_payload,
    load_cards,
    rank,
    resolve,
    visual_score,
)

ROOT = Path(__file__).resolve().parents[1]


def _card(external_id: str, name: str, position: str, overall: int) -> TackleCard:
    return TackleCard(
        external_id,
        f"card:{external_id}",
        name,
        position,
        overall,
        "Test Program",
        "CFB27",
        "https://example.invalid/card.png",
        None,
        None,
        None,
        None,
        (name.casefold().replace(" ", ""), name.split()[-1].casefold()),
    )


def test_all_cfb27_tackles_link_to_unique_production_metadata():
    cards = load_cards(
        ROOT / "data/external/raw/cfb_fan_player_items",
        ROOT / "data/production/cfb27_scored_population.json",
    )
    assert sum(card.position == "LT" for card in cards) >= 317
    assert sum(card.position == "RT" for card in cards) >= 321
    assert all(card.season == "CFB27" and card.canonical_card_id for card in cards)


def test_visual_signal_changes_ranking_independently_of_text_and_ovr():
    red = fingerprint(Image.new("RGB", (240, 321), "red"))
    blue = fingerprint(Image.new("RGB", (240, 321), "blue"))
    first = IndexedTackle(_card("1", "Alpha One", "LT", 80), red, "a", None)
    second = IndexedTackle(_card("2", "Beta Two", "LT", 80), blue, "b", None)
    ranking = rank([first, second], blue, None, None, "LT")
    assert ranking[0]["external_id"] == "2"
    assert ranking[0]["visual"] > ranking[1]["visual"]


def test_wrong_position_and_ambiguous_queries_fail_closed():
    red = fingerprint(Image.new("RGB", (240, 321), "red"))
    item = IndexedTackle(_card("1", "Alpha One", "LT", 80), red, "a", None)
    assert rank([item], red, "Alpha One", 80, "QB") == []
    assert resolve(rank([item], None, None, None, "LT")) is None


def test_perceptual_signal_tolerates_resize_and_jpeg_like_degradation():
    image = Image.new("RGB", (240, 321), (30, 80, 170))
    transformed = image.resize((80, 107), Image.Resampling.LANCZOS)
    assert visual_score(fingerprint(image), fingerprint(transformed)) > 0.9


def test_checked_in_index_covers_all_tackles_and_round_trips():
    from operation_pancake.tackle_visual_pilot import load_index

    index = load_index(ROOT / "data/production/cfb27_tackle_visual_index.json.gz")
    assert len(index) == 638
    assert sum(item.card.position == "LT" for item in index) == 317
    assert sum(item.card.position == "RT" for item in index) == 321
    rebuilt = index_from_payload(index_to_payload(index))
    assert [item.card.canonical_card_id for item in rebuilt] == [
        item.card.canonical_card_id for item in index
    ]
    assert visual_score(rebuilt[0].fingerprint, index[0].fingerprint) > 0.99999


def test_displayed_ovr_allows_bounded_positive_lineup_boost():
    red = fingerprint(Image.new("RGB", (240, 321), "red"))
    native_80 = IndexedTackle(_card("1", "Juan Gaston", "RT", 80), red, "a", None)
    result = rank([native_80], red, "Gaston", 81, "RT")[0]
    assert result["ovr"] == 0.8
