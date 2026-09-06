#!/usr/bin/env python3
"""Build and benchmark the bounded CFB27 tackle visual recognition pilot."""

from __future__ import annotations

import argparse
import gzip
import io
import json
import random
from collections import Counter
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

from operation_pancake.tackle_visual_pilot import (
    _download,
    build_index,
    compose_card,
    fingerprint,
    index_to_payload,
    load_cards,
    rank,
    resolve,
)


def degraded(image: Image.Image, seed: int) -> Image.Image:
    rng = random.Random(seed)
    width, height = image.size
    inset_x = rng.randint(3, 12)
    inset_y = rng.randint(2, 10)
    crop = image.crop((inset_x, inset_y, width - inset_x, height - inset_y))
    crop = crop.resize((96, 128), Image.Resampling.LANCZOS).filter(ImageFilter.GaussianBlur(0.55))
    overlay_color = (rng.randint(8, 30), rng.randint(8, 30), rng.randint(8, 30))
    overlay = Image.new("RGB", crop.size, overlay_color)
    crop = Image.blend(crop.convert("RGB"), overlay, 0.10)
    draw = ImageDraw.Draw(crop)
    draw.rectangle((0, 104, 96, 128), fill=(18, 24, 31))  # UI/nameplate occlusion
    buffer = io.BytesIO()
    crop.save(buffer, format="JPEG", quality=48)
    return Image.open(io.BytesIO(buffer.getvalue())).convert("RGB")


def noisy_name(name: str, seed: int) -> str:
    rng = random.Random(seed)
    last = name.split()[-1]
    if len(last) <= 4:
        return last[:-1] or last
    start = rng.randint(0, 1)
    end = rng.randint(max(start + 3, len(last) - 3), len(last))
    value = last[start:end]
    if len(value) > 3 and seed % 3 == 0:
        value = value[:2] + value[3:]
    return value


def metric(results: list[dict]) -> dict:
    total = len(results)
    resolved = [row for row in results if row["resolved"]]
    correct = [row for row in results if row["resolved"] == row["expected"]]
    false = [row for row in resolved if row["resolved"] != row["expected"]]
    return {
        "cases": total,
        "top_1_accuracy": round(sum(row["top1"] for row in results) / total, 6),
        "top_3_accuracy": round(sum(row["top3"] for row in results) / total, 6),
        "identification_accuracy": round(len(correct) / total, 6),
        "unresolved_rate": round((total - len(resolved)) / total, 6),
        "false_positive_rate": round(len(false) / total, 6),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--cache", type=Path, default=Path("/tmp/pancake-tackle-images"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    cards = load_cards(
        root / "data/external/raw/cfb_fan_player_items",
        root / "data/production/cfb27_scored_population.json",
    )
    index = build_index(cards, args.cache)
    production_index = root / "data/production/cfb27_tackle_visual_index.json.gz"
    production_payload = (
        json.dumps(index_to_payload(index), separators=(",", ":")) + "\n"
    )
    production_index.write_bytes(gzip.compress(production_payload.encode(), mtime=0))
    duplicate_players = Counter((item.card.player_name, item.card.position) for item in index)
    same_ovr = Counter((item.card.position, item.card.overall) for item in index)
    clean_results, degraded_results, text_only_results = [], [], []
    examples = []
    for number, item in enumerate(index):
        card_bytes, _ = _download(item.card.card_image_url, args.cache)
        portrait_bytes = None
        if item.card.portrait_url:
            try:
                portrait_bytes, _ = _download(item.card.portrait_url, args.cache)
            except Exception:
                pass
        layers = []
        for url in (
            item.card.border_url,
            item.card.program_image_url,
            item.card.team_image_url,
        ):
            try:
                layers.append(_download(url, args.cache)[0] if url else None)
            except Exception:
                layers.append(None)
        clean_image = compose_card(card_bytes, portrait_bytes, *layers)
        cases = [
            (clean_results, fingerprint(clean_image), item.card.player_name, item.card.overall),
            (
                degraded_results,
                fingerprint(degraded(clean_image, number)),
                noisy_name(item.card.player_name, number),
                item.card.overall if number % 3 else None,
            ),
            (
                text_only_results,
                None,
                noisy_name(item.card.player_name, number),
                item.card.overall if number % 3 else None,
            ),
        ]
        for result_rows, query, name, ovr in cases:
            ranking = rank(index, query, name, ovr, item.card.position)
            selected = resolve(ranking)
            result_rows.append(
                {
                    "expected": item.card.external_id,
                    "resolved": selected["external_id"] if selected else None,
                    "top1": ranking[0]["external_id"] == item.card.external_id,
                    "top3": item.card.external_id in {row["external_id"] for row in ranking[:3]},
                    "multiple_card_player": duplicate_players[
                        (item.card.player_name, item.card.position)
                    ]
                    > 1,
                    "same_ovr_competitors": same_ovr[(item.card.position, item.card.overall)] - 1,
                }
            )
        if number in {0, 17, 101, 317, 421, 637}:
            query = fingerprint(degraded(clean_image, number))
            examples.append(
                {
                    "expected": {
                        "external_id": item.card.external_id,
                        "name": item.card.player_name,
                        "position": item.card.position,
                        "overall": item.card.overall,
                        "program": item.card.program,
                    },
                    "observations": {
                        "name": noisy_name(item.card.player_name, number),
                        "ovr": item.card.overall if number % 3 else None,
                    },
                    "top_candidates": rank(
                        index,
                        query,
                        noisy_name(item.card.player_name, number),
                        item.card.overall if number % 3 else None,
                        item.card.position,
                    )[:3],
                }
            )

    # Explicit ambiguity control: no pixels, no text, no OVR must fail closed.
    ambiguous = resolve(rank(index, None, None, None, "LT")) is None
    non_tackles = load_cards(
        root / "data/external/raw/cfb_fan_player_items",
        root / "data/production/cfb27_scored_population.json",
        {"QB", "WR", "CB", "DT"},
    )[:: max(1, len(cards) // 32)][:32]
    negative_index = build_index(non_tackles, args.cache)
    negative_results = []
    for number, item in enumerate(negative_index):
        # Query genuine non-tackle pixels against an intentionally asserted tackle slot.
        ranking = rank(index, item.fingerprint, None, None, "LT" if number % 2 == 0 else "RT")
        selected = resolve(ranking)
        negative_results.append(selected is not None)
    wrong_position_unresolved = all(
        resolve(rank(index, item.fingerprint, item.card.player_name, item.card.overall, "QB"))
        is None
        for item in index[:64]
    )
    report = {
        "scope": "CFB27 LT/RT only",
        "index": {
            "lt_cards": sum(item.card.position == "LT" for item in index),
            "rt_cards": sum(item.card.position == "RT" for item in index),
            "total_tackle_images": len(index),
            "metadata_linked": sum(item.card.canonical_card_id is not None for item in index),
            "portraits_available": sum(item.portrait_sha256 is not None for item in index),
            "multiple_card_players": sum(count > 1 for count in duplicate_players.values()),
        },
        "clean": metric(clean_results),
        "degraded_screenshot_like": metric(degraded_results),
        "degraded_same_ovr_cases": metric(
            [row for row in degraded_results if row["same_ovr_competitors"] > 0]
        ),
        "degraded_multiple_card_player_cases": metric(
            [row for row in degraded_results if row["multiple_card_player"]]
        ),
        "ocr_only_control_on_same_degraded_observations": metric(text_only_results),
        "visual_top1_lift": round(
            metric(degraded_results)["top_1_accuracy"]
            - metric(text_only_results)["top_1_accuracy"],
            6,
        ),
        "ambiguous_no_evidence_fails_closed": ambiguous,
        "wrong_position_fails_closed": wrong_position_unresolved,
        "non_tackle_negatives": {
            "cases": len(negative_results),
            "unresolved_rate": round(
                sum(not value for value in negative_results) / len(negative_results), 6
            ),
            "false_positive_rate": round(
                sum(negative_results) / len(negative_results), 6
            ),
        },
        "examples": examples,
    }
    output = args.output or root / "data/research/cfb27_tackle_visual_pilot/report.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
