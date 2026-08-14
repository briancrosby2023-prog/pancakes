"""Generate OP-X-005 Dynamic Upgrade intelligence."""

from pathlib import Path

from operation_pancake.research.cfb27_op_x_005 import build_op_x_005, write_artifacts


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    analysis = build_op_x_005(root)
    write_artifacts(root / "data/research/cfb27_op_x_005", analysis)
    print(f"Preserved {len(analysis['dynamic_upgrade_event_master_v1'])} event-attribute rows.")


if __name__ == "__main__":
    main()
