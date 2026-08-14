"""Conservative resumable CFB.FAN historical listing acquisition."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
import urllib.request
from pathlib import Path

from operation_pancake.research.cfb27_op_x_005 import parse_historical_listing


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--game", choices=("25", "26"), required=True)
    parser.add_argument("--max-pages", type=int, default=1)
    parser.add_argument("--delay", type=float, default=2.0)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.delay < 2:
        raise ValueError("minimum delay is 2 seconds")
    output = (
        args.output
        or Path(__file__).resolve().parents[1]
        / f"data/external/cfb_fan_{args.game}_historical.json"
    )
    state = (
        json.loads(output.read_text())
        if output.exists()
        else {"game": f"CFB{args.game}", "pages": {}, "cards": {}}
    )
    for page in range(1, args.max_pages + 1):
        if str(page) in state["pages"]:
            continue
        url = f"https://cfb.fan/{args.game}/players/?page={page}"
        request = urllib.request.Request(url, headers={"User-Agent": "OperationPancake/1.0"})
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read()  # noqa: S310
        for card in parse_historical_listing(raw.decode("utf-8")):
            state["cards"][card["card_id"]] = card
        state["pages"][str(page)] = {"url": url, "sha256": hashlib.sha256(raw).hexdigest()}
        output.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        if page < args.max_pages:
            time.sleep(args.delay)


if __name__ == "__main__":
    main()
