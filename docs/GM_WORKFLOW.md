# Operation Pancake GM workflow

The product-facing command is `operation-pancake-gm`. It composes the frozen production scoring, roster, and market engines; it does not route exploratory research models into production.

## Evaluate one player

Use `operation-pancake-gm player --card-id CARD_ID` when the card ID is known. Name searches may be narrowed with `--position`, `--overall`, and `--program`. If multiple versions remain, Pancake returns `AMBIGUOUS CARD VERSION` rather than silently choosing one.

## Compare two players

Use `operation-pancake-gm compare CURRENT_CARD_ID CANDIDATE_CARD_ID`. The football verdict is independent of market evidence. Without a price an upgrade can remain `UPGRADE` while the market verdict is `PRICE CHECK REQUIRED`. Add `--price` and optional `--resale` only when current evidence exists.

## Evaluate the roster

Use `operation-pancake-gm roster`. Resolved players continue through scoring, depth, positional-strength and upgrade analysis even when other roster identities remain unresolved. Pancake does not require 24/24 resolution.

## Enter today's prices

Prepare a JSON list containing a card identity and `observed_price`, then run `operation-pancake-gm price prices.json --observed-at 2026-08-20T08:00:00-07:00`. The timestamp must include a timezone. Malformed observations are rejected individually. Accepted observations use the canonical OP-X-023 market schema and are observations, not invented completed-sale evidence.

## See which prices Pancake needs

Use `operation-pancake-gm price-check`. The output identifies the candidate card and why current price evidence is needed. This prevents users from inspecting internal JSON to discover missing market inputs.

## Ask what to do with a budget

Use `operation-pancake-gm budget candidates.json 300000`. Candidate rows supply `net_cost` and `score_improvement`; the optimizer compares combinations and may keep coins unspent. Missing-price candidates are excluded rather than assigned invented prices.

## Confidence and incomplete data

Confidence is decomposed into identity, attribute completeness, model/ranking, market, and Moneyball dimensions. `LOW` or unavailable market confidence does not erase a defensible football verdict. Unsupported models, insufficient attributes, unresolved identities, stale prices, and missing prices are explicit states rather than silent fallbacks.

## Research/production boundary

OP-X-024 remains `IMPLEMENTED — EXECUTION PENDING`. Its TE research does not replace locked production TE ranking models. Diagnostic TE models do not become production routes; unsupported QB Pure Runner remains unsupported; Center limitations remain explicit.
