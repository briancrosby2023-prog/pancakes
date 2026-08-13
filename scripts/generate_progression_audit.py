"""Generate database-wide progression mining artifacts."""

from pathlib import Path

from operation_pancake.research.progression_mining import (
    build_progression_audit,
    write_progression_artifacts,
)


def main() -> None:
    """Mine all repository-accessible canonical and progression evidence."""
    output = Path("data/research/progression_audit")
    research_files = [
        str(path)
        for path in Path("data/research").rglob("*")
        if path.is_file() and output not in path.parents
    ]
    audit = build_progression_audit("data/canonical/canonical_v1.9.xlsx", research_files)
    write_progression_artifacts(output, audit)


if __name__ == "__main__":
    main()
