"""Print the deterministic CFB27 database health report."""

import json
from pathlib import Path

from operation_pancake.research.cfb27_op_x_010 import build_op_x_010


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    print(json.dumps(build_op_x_010(root)["database_health"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
