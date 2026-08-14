"""Generate deterministic Phase-V research artifacts."""

from pathlib import Path

from operation_pancake.research.cfb27_phase5 import build_phase5, write_artifacts


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    analysis = build_phase5(root)
    output = root / "data/research/cfb27_inheritance_phase5"
    write_artifacts(output, analysis)
    print(
        f"Phase V preserved {len(analysis['thresholds'])} threshold-tier records and "
        f"{len(analysis['schema_graph']['edges'])} explicit schema edges."
    )


if __name__ == "__main__":
    main()
