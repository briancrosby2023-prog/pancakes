"""Materialize refreshed CFB.FAN cards for the production scorer."""

import json
from pathlib import Path

from operation_pancake.research.cfb27_canonical_population import (
    materialize_canonical_population,
)

if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    print(json.dumps(materialize_canonical_population(root), sort_keys=True))
