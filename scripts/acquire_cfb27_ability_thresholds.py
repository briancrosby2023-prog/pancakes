"""Acquire the public CFB Labs CFB27 ability-requirement snapshot."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import urllib.request
from datetime import date
from pathlib import Path

SOURCE_URL = "https://www.cfblabs.com/ability-requirements"


def extract_next_data(html: str) -> dict:
    match = re.search(
        r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
        html,
        flags=re.DOTALL,
    )
    if not match:
        raise ValueError("CFB Labs page did not contain __NEXT_DATA__")
    return json.loads(match.group(1))


def extract_requirements(payload: dict) -> list[dict]:
    props = payload["props"]["pageProps"]
    candidates = [value for value in props.values() if isinstance(value, list)]
    for rows in candidates:
        if rows and {"Position_Short", "Archetype", "Ability", "Bronze"} <= set(rows[0]):
            return rows
    raise ValueError("structured ability requirement rows were not found")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-html", type=Path)
    args = parser.parse_args()
    if args.input_html:
        raw = args.input_html.read_bytes()
    else:
        request = urllib.request.Request(SOURCE_URL, headers={"User-Agent": "OperationPancake/1.0"})
        with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310
            raw = response.read()
    payload = extract_next_data(raw.decode("utf-8"))
    rows = extract_requirements(payload)
    output = Path(__file__).resolve().parents[1] / "data/external/cfb27_ability_thresholds.json"
    snapshot = {
        "source": SOURCE_URL,
        "source_id": "SRC-CFB27-ABILITY-001",
        "source_class": "STRUCTURED_SECONDARY",
        "retrieval_date": date.today().isoformat(),
        "raw_html_sha256": hashlib.sha256(raw).hexdigest(),
        "site_build_id": payload.get("buildId"),
        "records": rows,
    }
    output.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Preserved {len(rows)} ability requirement rows from {SOURCE_URL}.")


if __name__ == "__main__":
    main()
