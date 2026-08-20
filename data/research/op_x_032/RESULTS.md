# OP-X-032 Production Hardening Results

## Coverage

The canonical denominator is 8,838 cards. Identity and market-workflow coverage are 8,838 (100%). Production scoring, ranking, explanation, comparison, intrinsic-value, and alternative-search coverage are 8,184 (92.600136%). Of these, 396 cards are fully scoreable and 7,788 are partially scoreable.

The remaining 654 cards are exhaustively recorded in `unsupported_population_audit.json`: 558 have incomplete strict attribute vectors, 85 are Pure Runner QBs without an independently validated frozen production route, and 11 are Pure Blocker TEs whose model remains diagnostic-only. No routing mismatch, malformed source row, or other model-free correction was found. Consequently, zero cards were defensibly fixed by inventing or changing coefficients.

## Scientific gaps

The 85 Pure Runner QBs remain scientifically unsupported under QB-SHARED-001. Repository evidence does not provide the exact independent validation needed to freeze a route. The 11 Pure Blocker TEs retain useful identity, native attributes, comparison context, and market-observation support, but no production ranking score; OP-X-024 is not treated as coefficient proof.

The 7,788 partial scores are disclosed evidence, not complete-vector equivalents. Attribute coverage assigns 7,714 LOW and 74 MEDIUM confidence labels. A causal missingness correction, counterfactual rank displacement, and boundary-inversion rate are not identifiable from the available native vectors, so those measures are explicitly unavailable rather than fabricated.

## Decision quality

Near-score alternatives exist for 8,112 cards within 0.25, 8,148 within 0.50, and 8,171 within 1.00. Results now disclose different archetype, materially different attribute coverage, and different score confidence. The football-value index contains 1,000 lower-OVR/higher-score cases and 250 same-OVR major-separation cases; it makes no market-value claim without observations.

The current roster has 24 entries: all 24 support starter/depth evaluation, 18 have resolved identity and market-request coverage, and 17 support score, rank, explanation, alternatives, replacement search, intrinsic valuation, and purchase reports. Six identities remain explicitly unresolved. Dante Moore's card is resolved, but its seven-field strict QB vector remains incomplete; other Dante Moore versions cannot supply card-native evidence.

## Acceptance

All 14 installed CLI commands passed with isolated market history. Safety fuzzing passed, including invalid fractional prices and protected-asset/no-purchase/tie cases. The 50-candidate optimizer was deterministic, stayed within budget, and matched brute force on its tractable subset.

The OP-X-025 through OP-X-032 regression gate passed 77 tests, and the focused hardening/dependency gate passed 12 tests. The broad repository run produced 612 passes and 15 pre-existing historical/artifact expectation failures with a workspace-local pytest temp directory. Changed files pass Ruff; the remaining repository inventory is 168 findings (8 production, 157 research scripts, 3 tests).
