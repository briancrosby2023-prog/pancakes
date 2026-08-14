"""Print the deterministic CFB27 database health report."""

import json
from pathlib import Path

from operation_pancake.research.cfb27_op_x_012 import build_op_x_012


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    print(json.dumps(build_op_x_012(root)["database_health_v3"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
