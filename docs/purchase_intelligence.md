# Unified GM purchase intelligence

Generate one concise report from canonical card IDs:

```text
operation-pancake-gm purchase-report CURRENT_CARD_ID CANDIDATE_CARD_ID
```

Generate the roster-wide board:

```text
operation-pancake-gm shopping-board
```

The report keeps football score, attribute explanation, intrinsic value, market evidence,
cost, and final action in separate named sections. Context-only prices cannot authorize
BUY. Missing resale or alternative prices remain null and become explicit next-evidence
requests. After `market-observe` or `market-snapshot`, rerun either command; it reads the
append-only OP-X-029 history automatically.
