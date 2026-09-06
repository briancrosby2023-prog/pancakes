# OP-X-012E.14 Quality Gate Checkpoint

Recovered 2026-08-18 from durable GitHub Actions evidence.

- Run #84 / 32196974230 attempt 2 completed with Ruff PASS and Alpha PASS.
- Canonical E.14 executed against 8,838 / 8,838 eligible records.
- `data/research/cfb27_e14/evidence_matrix.json` is present and canonical.
- Attempt 2 reached pytest and reported 11 failures / 434 passes.
- The failures were deterministic-artifact/integration drift plus legacy release-date parsing on the older run SHA; the live branch contains the subsequent repair/refresh path.
- CLI was not reached in run #84 attempt 2 because pytest failed.
- E.14 remains incomplete until a definitive run on the repaired branch passes pytest and CLI and publishes required artifacts.
- E.15 has not started.

This checkpoint intentionally triggers a fresh branch pipeline so the repaired live branch, rather than the older run #84 SHA, receives the definitive quality-gate execution.
