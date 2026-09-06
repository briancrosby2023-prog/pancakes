# Attribute intelligence

Use the GM CLI to explain model-based football value:

```text
operation-pancake-gm explain CARD_ID
operation-pancake-gm compare-explain CURRENT_CARD_ID CANDIDATE_CARD_ID
operation-pancake-gm alternatives CARD_ID --tolerance 0.5
operation-pancake-gm attribute-upgrades CARD_ID --attribute RBK --min-score-gain 1
```

Contributions, strength labels, scarcity, and marginal values describe the frozen Pancake
ranking model. They are not independent gameplay claims, EA OVR coefficients, or market
prices. Comparisons across unrelated positions are rejected. Missing and diagnostic model
evidence remains explicit.
