"""Extract durable card art from the original Team Manager screenshots."""
from __future__ import annotations

from io import BytesIO
from pathlib import Path

from PIL import Image

BASE_SIZE = (2048, 1536)
VIEW_SOURCE = {"DEFENSE": 0, "OFFENSE": 1, "SPECIAL TEAMS": 2, "SPECIALISTS": 3}
CARD_BOXES = {
    "OFFENSE": {
        "LT 1": (574,389,747,635), "LG 1": (808,388,981,635), "C 1": (1042,389,1214,635),
        "RG 1": (1275,389,1448,635), "RT 1": (1508,389,1680,635), "TE 1": (1740,389,1914,635),
        "WR 1": (574,844,747,1084), "WR 3": (808,844,981,1084), "HB 1": (1042,844,1214,1084),
        "QB 1": (1275,844,1448,1084), "FB 1": (1508,844,1680,1084), "WR 2": (1740,844,1914,1084),
    },
    "DEFENSE": {
        "FS 1": (595,430,750,650), "WILL 1": (808,430,963,650), "MIKE 1": (1020,430,1175,650),
        "MIKE 2": (1240,430,1395,650), "SAM 1": (1470,430,1625,650), "SS 1": (1690,430,1845,650),
        "CB 1": (485,850,640,1080), "CB 3": (705,850,860,1080), "REDG 1": (925,850,1080,1080),
        "DT 1": (1120,850,1280,1080), "DT 2": (1325,850,1485,1080), "LEDG 1": (1535,850,1695,1080),
        "CB 2": (1745,850,1905,1080),
    },
    "SPECIAL TEAMS": {
        "P 1": (730,465,865,650), "K 1": (920,465,1055,650), "KR 1": (1350,465,1490,650),
        "PR 1": (1595,465,1735,650), "LS 1": (730,840,865,1025), "KOS 1": (920,840,1055,1025),
    },
    "SPECIALISTS": {
        "3DRB 1": (690,510,835,705), "PWHB 1": (920,510,1065,705), "SLWR 1": (1070,520,1215,705),
        "GAD 1": (1260,520,1405,705), "NT 1": (1460,520,1605,705),
        "SUBLB 1": (690,880,835,1065), "RRE 1": (875,880,1020,1065), "RDT 1": (1060,880,1205,1065),
        "RLE 1": (1245,880,1390,1065), "SLCB 1": (1430,880,1575,1065),
    },
}


def _scaled_box(box, size):
    sx, sy = size[0] / BASE_SIZE[0], size[1] / BASE_SIZE[1]
    left, top, right, bottom = box
    return (
        max(0, round(left * sx)),
        max(0, round(top * sy)),
        min(size[0], round(right * sx)),
        min(size[1], round(bottom * sy)),
    )


def crop_card(evidence, view: str | None, slot: str | None) -> Image.Image | None:
    """Return the visible card face for a known Team Manager view/slot."""
    if view not in VIEW_SOURCE or slot not in CARD_BOXES.get(view, {}):
        return None
    try:
        image = Image.open(BytesIO(evidence.images[VIEW_SOURCE[view]].payload)).convert("RGB")
    except OSError:
        return None
    return image.crop(_scaled_box(CARD_BOXES[view][slot], image.size))


def save_card_crop(evidence, player, card_id: str, card_art_root: Path) -> str | None:
    """Persist screenshot pixels under the exact stable card ID."""
    crop = crop_card(evidence, player.view, player.slot)
    if crop is None:
        return None
    filename = f"{card_id.replace(':', '-')}.png"
    target = card_art_root / filename
    target.parent.mkdir(parents=True, exist_ok=True)
    crop.save(target, format="PNG", optimize=True)
    return target.relative_to(card_art_root.parents[2]).as_posix()


def save_observation_crop(evidence, player, fingerprint: str, card_art_root: Path) -> str | None:
    """Persist proven screenshot art even when database card identity remains held."""
    import hashlib

    crop = crop_card(evidence, player.view, player.slot)
    if crop is None:
        return None
    digest = hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()[:20]
    target = card_art_root / f"observation-{digest}.png"
    target.parent.mkdir(parents=True, exist_ok=True)
    crop.save(target, format="PNG", optimize=True)
    return target.relative_to(card_art_root.parents[2]).as_posix()
