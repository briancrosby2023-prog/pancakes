# Market observation campaign

Record one exact card without retyping known identity fields:

```text
operation-pancake-gm market-observe CARD_ID PRICE DISPLAYED_MARKET_PRICE
```

Record a rapid snapshot by placing canonical card IDs and integer coin prices in a JSON
object, then running:

```text
operation-pancake-gm market-snapshot snapshot.json --type DISPLAYED_MARKET_PRICE
```

Use `LOWEST_VISIBLE_LISTING`, `VISIBLE_LISTING`, `DISPLAYED_MARKET_PRICE`, `RECENT_SALE`,
`COMPLETED_SALE`, or `USER_REPORTED_OTHER` exactly as observed. A user observation records
when the user saw the price; it never claims that CFB.FAN published a timestamp.

Real observations append to `data/production/market/user_observation_history.json` and
deduplicate only exact repeated evidence IDs. Fixture observations are rejected from this
history. WATCH boundaries request re-evaluation and never authorize an automatic purchase.
