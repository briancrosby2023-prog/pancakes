"""Generate repository completeness and recovery-priority artifacts."""

from pathlib import Path

from operation_pancake.research.repository_completeness_audit import write_repository_audit


def main() -> None:
    audit = write_repository_audit(Path(__file__).resolve().parents[1])
    print(
        f"Audited {audit['audit_summary']['positions']} positions and "
        f"{audit['audit_summary']['canonical_cards']} canonical cards."
    )


if __name__ == "__main__":
    main()
