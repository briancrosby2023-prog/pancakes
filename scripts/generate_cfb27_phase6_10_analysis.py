"""Generate deterministic Phase VI-X research artifacts."""

from pathlib import Path

from operation_pancake.research.cfb27_phase6_10 import build_phase6_10, write_artifacts


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    analysis = build_phase6_10(root)
    write_artifacts(root / "data/research/cfb27_ability_phase6_10", analysis)
    catalog = analysis["ability_catalog"]
    print(
        f"Preserved {catalog['tier_requirement_groups']} grouped thresholds and "
        f"{catalog['attribute_constraints']} attribute constraints."
    )


if __name__ == "__main__":
    main()
