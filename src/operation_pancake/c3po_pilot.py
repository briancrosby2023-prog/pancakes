"""Run the bounded real-image C-3PO LT/RT pilot from the repository root."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from operation_pancake.c3po_tackle_resolver import TackleResolutionStore, resolve_tackles
from operation_pancake.c3po_vision import GeminiScreenshotTranslator
from operation_pancake.production.gm import GMProduct


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("screenshot", type=Path)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, default=Path(".operation_pancake/c3po-tackle-pilot.json"))
    args = parser.parse_args()
    root = args.root.resolve()
    screenshot = args.screenshot.resolve()
    output = args.output if args.output.is_absolute() else root / args.output

    translated = GeminiScreenshotTranslator().translate_offense_tackles(screenshot)
    gm = GMProduct(root)
    resolved = resolve_tackles(translated, gm.population)
    TackleResolutionStore(output).save(translated, resolved)
    print(json.dumps({"translator_observation": translated.to_dict(), "resolutions": [row.__dict__ for row in resolved]}, indent=2))


if __name__ == "__main__":
    main()
