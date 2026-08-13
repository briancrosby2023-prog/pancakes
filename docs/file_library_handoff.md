# File Library bulk-ingestion handoff

ChatGPT should return UTF-8 JSON conforming to
`schemas/historical_ingestion_manifest.schema.json`. Use stable, descriptive IDs; preserve literal
`"UNKNOWN"` values and list them in `unresolved_fields`. Every observed field needs a source ID and
page/image locator. A catalog source may be referenced with `"catalog_source": true`; otherwise it
must appear in the same manifest. Historical and external evidence must use `HISTORICAL_CARD`,
`REFERENCE_DATA`, `PROGRESSION_EVIDENCE`, or `RESEARCH_ONLY`, never `CANONICAL_CARD`.

Dry-run first:

```text
uv run operation-pancake ingest recovered.json --dry-run
uv run operation-pancake ingest recovered.json
uv run operation-pancake coverage
uv run operation-pancake conflicts
uv run operation-pancake incomplete
uv run operation-pancake reconcile
```

## A. One player card

```json
{"manifest_id":"FL-001","schema_version":"1.0","origin":"CHATGPT_FILE_LIBRARY","sources":[{"source_id":"SRC-IMG-001","source_name":"Card image","original_filename":"card.png","source_type":"SCREENSHOT","coverage":{"expected_items":["image-1"],"processed_items":["image-1"],"unresolved_items":[]}}],"records":[{"record_id":"HIST-CARD-001","record_type":"card","disposition":"HISTORICAL_CARD","validation_status":"VALIDATED","values":{"player":"Example Player","position":"C","overall":82,"program":"Core","attributes":{"STR":85}},"source_links":[{"source_id":"SRC-IMG-001","locator":"image-1"}],"provenance":[{"provenance_id":"PROV-HIST-CARD-001-STR","field_name":"STR","source_id":"SRC-IMG-001","locator":"image-1 rating panel","provenance_status":"DIRECTLY_OBSERVED"}]}]}
```

## B. Multiple cards from one PDF

Use one PDF source with page IDs in `expected_items`, multiple card records, and a page locator on
each source link. `processed_items` and `unresolved_items` may be updated by later manifests.

```json
{"sources":[{"source_id":"SRC-PDF-001","source_name":"Card PDF","original_filename":"cards.pdf","source_type":"PDF","coverage":{"expected_items":[1,2],"processed_items":[1],"unresolved_items":[2],"cards_identified":["CARD-1","CARD-2"],"cards_extracted":["CARD-1"]}}],"records":[{"record_id":"CARD-1","record_type":"card","disposition":"HISTORICAL_CARD","validation_status":"VALIDATED","values":{"player":"Player One","position":"C","overall":81},"source_links":[{"source_id":"SRC-PDF-001","locator":"page 1"}]}]}
```

## C. Progression chain

Use `record_type: "progression_observation"`, disposition `PROGRESSION_EVIDENCE`, and values such as
`lower_card_id`, `upper_card_id`, `relationship_status`, and `experiment_id`. Multiple screenshots
can link to the same observation.

```json
{"record_id":"PROG-001","record_type":"progression_observation","disposition":"PROGRESSION_EVIDENCE","validation_status":"HISTORICAL","values":{"lower_card_id":"CARD-1","upper_card_id":"CARD-2","relationship_status":"CANDIDATE"},"source_links":[{"source_id":"SRC-PDF-001","locator":"pages 1-2"}]}
```

## D. Historical research result

Use `record_type: "research_artifact"`, disposition `RESEARCH_ONLY`, and store exact reported
metrics in `values`, including a statement that they are historical and not a production formula.

```json
{"record_id":"RESEARCH-001","record_type":"research_artifact","disposition":"RESEARCH_ONLY","validation_status":"HISTORICALLY_RECOVERED","values":{"metric":"MAE","value":0.91,"production_formula":false},"source_links":[{"source_id":"SRC-HIST-WB-001","locator":"Results sheet","catalog_source":true}]}
```

## E. Unresolved visual field

```json
{"record_id":"HIST-CARD-002","record_type":"card","disposition":"HISTORICAL_CARD","validation_status":"NEEDS_REVIEW","values":{"player":"Example Player","position":"C","overall":82,"attributes":{"AWR":"UNKNOWN"}},"unresolved_fields":["AWR"],"source_links":[{"source_id":"SRC-C-RAW-003","locator":"page 7","catalog_source":true}],"provenance":[{"provenance_id":"PROV-HIST-CARD-002-AWR","field_name":"AWR","source_id":"SRC-C-RAW-003","locator":"page 7 rating panel","provenance_status":"UNKNOWN"}]}
```

## F. Conflicting evidence

Submit the observed incoming value unchanged with its independent provenance. The dry-run emits
`CONFLICT`, preserving the canonical value, incoming value, and both provenance chains. Do not add a
reconciliation resolution until a human-validated decision exists.

## Screenshot and history-PDF conventions

For the approximately 202-image archive, register each filename as a source or coverage item and
link any number of images to one card, progression, or experiment. For `history(4).pdf`, use page
locators and classify each record independently; a page may support Saturday Reset experiments,
formula history, or conclusions without representing a canonical card.

The same contract is used by future web/API adapters. All sources converge on staging, validation,
deduplication, explicit promotion, and research availability; origin does not bypass these gates.
