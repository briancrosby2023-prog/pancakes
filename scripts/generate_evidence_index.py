"""Generate durable source-index and reconciliation artifacts."""

from pathlib import Path

from operation_pancake.evidence.catalog import write_evidence_artifacts


def main() -> None:
    index = write_evidence_artifacts(Path(__file__).resolve().parents[1])
    print(f"Indexed {len(index.sources)} sources and {len(index.records)} records.")


if __name__ == "__main__":
    main()
