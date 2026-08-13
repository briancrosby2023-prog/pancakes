"""Generate the reproducible QB Formula Phase research artifact."""

from operation_pancake.importers.position_database_importer import import_registered_position
from operation_pancake.importers.position_registry import create_default_registry
from operation_pancake.repository.canonical_repository import CanonicalRepository
from operation_pancake.research.qb_formula_phase import write_qb_formula_research


def main() -> None:
    """Load canonical QB data and write the derived research artifact."""
    repository = CanonicalRepository()
    result = import_registered_position("QB", create_default_registry(), repository)
    if not result.is_valid:
        raise RuntimeError(f"Canonical QB import failed: {result.failures}")

    write_qb_formula_research(
        "data/research/qb_formula_phase_population_boundary.json",
        repository,
    )


if __name__ == "__main__":
    main()
