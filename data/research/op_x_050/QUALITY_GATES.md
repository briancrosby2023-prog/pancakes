# OP-X-050 Quality Gates

1. Frozen production evaluation remains untouched.
2. OP-X-028 methodology remains untouched.
3. Purchase BUY gates remain untouched.
4. Context is structured, provenance-bearing, and non-numeric.
5. UNKNOWN is neutral.
6. Canonical/deployment identity is separated.
7. Build theoretical/observed status is explicit.
8. Ability available/equipped/competitive semantics are separated.
9. Adoption/recommendation/rejection/limitation semantics are separated.
10. Residual classification never automatically declares model error.

Execution gates requested by the work order: focused tests; OP-X-025..050 regressions; full pytest; Ruff; git diff --check. These must be reported as NOT EXECUTED unless an execution environment actually runs them.
