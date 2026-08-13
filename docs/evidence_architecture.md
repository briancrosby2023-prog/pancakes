# Evidence architecture

Operation Pancake keeps source discovery, extraction, validation, and canonical promotion as
separate lifecycle steps. `SourceRecord` catalogs evidence independently of cards; `EvidenceLink`
provides many-to-many source relationships; and `FieldProvenance` records where individual values
came from without overwriting competing observations.

New external observations enter `StagedRecord` storage through an `ExternalSourceAdapter`. Staging
is deliberately noncanonical. Conflicts are reported explicitly and promotion remains a separate,
reviewed operation. The reconciliation queue records incomplete extraction, duplicates, conflicts,
and missing validation as durable work rather than informal notes.

ChatGPT File Library is responsible for historical source discovery and recovery. The repository is
responsible for indexing, structured extraction, provenance, validation, reconciliation, and
canonical promotion after recovered evidence is supplied. Existing `PlayerCard`, canonical
repository, and research-artifact structures remain authoritative; the evidence index links to them
instead of replacing them. This is the migration path for the earlier Sources, CardSources,
FieldProvenance, ImportLog, and ProcessingQueue concepts.

**Not found in the local repository does not mean the historical evidence does not exist.
Historical Operation Pancake evidence must be checked against the File Library/source-reconciliation
process before being declared unavailable.**

Run `uv run operation-pancake sources --status partial`, `search`, `unresolved`, `source SOURCE_ID`, or
`card CARD_ID` for read-only discovery and reverse lookup. Regenerate committed artifacts with
`uv run python scripts/generate_evidence_index.py`.

In a no-sync development shell, the equivalent entry point is
`uv run --no-sync python -m operation_pancake.cli`.

Recovered evidence can be supplied in bulk through the versioned JSON contract documented in
`file_library_handoff.md`. Ingestion writes a separate deterministic state overlay and report; it
does not edit the canonical workbook. `--dry-run` classifies every item before persistence, while
`--promote` only accepts complete, explicitly validated `CANONICAL_CARD` records.

`SRC-C-RAW-003` is the known 14-page partial `raw str centers2(2).pdf` Center CUT source. It is not
the EA base-roster reference source and is not treated as complete or canonically ingested.
