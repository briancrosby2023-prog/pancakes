# Operation Pancake Operational Memory

This directory is the durable decision-memory layer for Operation Pancake.

## Purpose

Before designing a new approach to a problem, inspect `pancake_memory.jsonl` for prior work on the same or an analogous problem. Prefer a `PROVEN_PATH` with `VERIFIED` or strong project evidence unless new evidence justifies deviation.

The memory is intentionally evidence-oriented. It records successful paths, failed paths, partial paths, open checkpoints, and established workflow protocols so repeated chats do not rediscover lessons already paid for.

## Classifications

- `PROVEN_PATH`: demonstrated successful technical route; prefer reuse.
- `FAILED_PATH`: attempted route that produced poor or failed results; do not repeat without a material change.
- `PARTIAL_PATH`: valid result with limited scope; useful as evidence/cross-check, not a complete solution.
- `OPEN_CHECKPOINT`: incomplete work with durable state worth resuming.
- `PROVEN_PROTOCOL`: established Operation Pancake workflow behavior.

## Decision rule

For every substantial Operation Pancake task:

1. Identify the problem class.
2. Search operational memory for matching or analogous records.
3. Prefer the highest-confidence proven path.
4. Reuse its runner/checkpoint/evidence architecture where applicable.
5. If deviating, record why the prior path does not apply.
6. After execution, append the measured outcome and evidence so future work learns from the result.

## Evidence rule

Do not promote hypotheses into proven paths. A memory should distinguish measured evidence from assumptions and should point to durable commits/artifacts when available.

## Current high-value rule

For CFB25/CFB26 complete population acquisition, the default prior is the successful CFB27 resumable pageable acquisition pipeline that produced 8,838/8,838 unique card records. Historical TE-only discovery is a cross-check, not the primary database-building architecture.
