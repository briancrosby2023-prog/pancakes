"""OCR exact Team Manager slot subregions instead of filtering a global OCR pass."""

from __future__ import annotations

import csv
import io
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageEnhance, ImageFilter, ImageOps

from operation_pancake.team_import import OCRObservation, SlotRegion, normalize_name


def _pixels(box, width, height):
    left = max(0, min(width, round(box[0] * width)))
    top = max(0, min(height, round(box[1] * height)))
    right = max(left + 1, min(width, round(box[2] * width)))
    bottom = max(top + 1, min(height, round(box[3] * height)))
    return left, top, right, bottom


def _variants(crop):
    scale = max(3, min(6, round(900 / max(crop.width, 1))))
    gray = ImageOps.grayscale(crop).resize(
        (crop.width * scale, crop.height * scale), Image.Resampling.LANCZOS
    )
    gray = ImageEnhance.Contrast(gray).enhance(2.0).filter(ImageFilter.SHARPEN)
    threshold = gray.point(lambda value: 255 if value >= 155 else 0)
    return (("contrast", gray), ("threshold", threshold))


def _run(executable, image, psm, temp_dir):
    target = Path(temp_dir) / f"crop-{id(image)}-{psm}.png"
    image.save(target)
    process = subprocess.run(
        [executable, str(target), "stdout", "--psm", str(psm), "tsv"],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    if process.returncode:
        return [], process.stdout.strip(), process.stderr.strip()
    rows = list(csv.DictReader(io.StringIO(process.stdout), delimiter="\t"))
    words = []
    for row in rows:
        text = (row.get("text") or "").strip()
        if not text:
            continue
        try:
            confidence = float(row.get("conf") or -1)
        except ValueError:
            confidence = -1
        words.append((text, None if confidence < 0 else confidence / 100))
    return words, " ".join(word[0] for word in words), process.stderr.strip()


def _read_box(image, normalized_box, executable, temp_dir, kind):
    pixel_box = _pixels(normalized_box, image.width, image.height)
    crop = image.crop(pixel_box)
    attempts = []
    best = []
    for variant_name, variant in _variants(crop):
        for psm in (7, 13, 11) if kind == "name" else (7, 13):
            words, raw, error = _run(executable, variant, psm, temp_dir)
            attempts.append({"variant": variant_name, "psm": psm, "raw_text": raw, "error": error})
            quality = sum(max(0.0, confidence or 0.0) for _, confidence in words)
            best_quality = sum(max(0.0, confidence or 0.0) for _, confidence in best)
            if words and (quality, len(words)) > (best_quality, len(best)):
                best = words
    return best, {
        "normalized_box": list(normalized_box),
        "pixel_box": list(pixel_box),
        "raw_text": " ".join(word[0] for word in best),
        "normalized_tokens": [normalize_name(word[0]) for word in best if normalize_name(word[0])],
        "attempts": attempts,
    }


def ocr_slot_crops(path, regions: list[SlotRegion], executable: str):
    """Return global-coordinate observations and auditable evidence for every exact crop."""
    observations = []
    diagnostics = {}
    with (
        Image.open(path) as opened,
        tempfile.TemporaryDirectory(prefix="pancake-slot-ocr-") as temp_dir,
    ):
        image = ImageOps.exif_transpose(opened).convert("RGB")
        for region in regions:
            slot_diagnostic = {"image_size": [image.width, image.height], "crops": {}}
            boxes = [
                ("starter_name", region.starter_name_box, "name"),
                ("starter_ovr", region.starter_ovr_box, "ovr"),
            ]
            boxes.extend(
                (f"backup_{index + 1}", box, "name")
                for index, box in enumerate(region.backup_boxes)
            )
            for label, box, kind in boxes:
                if box is None:
                    continue
                words, diagnostic = _read_box(image, box, executable, temp_dir, kind)
                slot_diagnostic["crops"][label] = diagnostic
                left, top, right, bottom = box
                count = max(len(words), 1)
                for index, (text, confidence) in enumerate(words):
                    word_left = left + (right - left) * index / count
                    word_right = left + (right - left) * (index + 1) / count
                    observations.append(
                        OCRObservation(text, (word_left, top, word_right, bottom), confidence)
                    )
            diagnostics[region.slot] = slot_diagnostic
    return observations, diagnostics
