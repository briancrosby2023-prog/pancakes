# Product Surface

Implemented command:

`operation-pancake-gm context <card-id> [--role ...] [--deployment ...] [--assignment ...] [--build ...]`

The output reports frozen numerical value separately from contextual role, scheme, behavior, risk, advantage, source-family, and UNKNOWN evidence. It exposes `score_modified: false`, `market_semantics_modified: false`, and `buy_gates_modified: false` invariants.

Context evidence is imported through the existing `operation-pancake-gm evidence-import` command and OP-X-043A registry.