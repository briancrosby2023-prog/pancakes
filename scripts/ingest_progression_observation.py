"""Validate a future progression observation without overwriting history."""

import argparse
import json
from pathlib import Path

from operation_pancake.research.cfb27_op_x_011 import validate_progression_observation


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("--existing", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    validated = validate_progression_observation(
        json.loads(args.input.read_text(encoding="utf-8")),
        json.loads(args.existing.read_text(encoding="utf-8")),
    )
    text = json.dumps(validated, indent=2) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")


if __name__ == "__main__":
    main()
