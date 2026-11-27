# Check recurring documentation updates with existing Apify datasets

[Open the Actor](https://apify.com/millgrah/rag-knowledge-base-sync-qa) · [Back to the recipes](../README.md)

Use this guide when your team already receives help-center or documentation text as Apify datasets and maintains a support chatbot or another retrieval system. Run one report when a new snapshot needs checking, inspect its readiness decision, and pass approved operations to your existing destination workflow.

**Price: US$0.50 per completed non-demo report, plus Apify platform usage**, subject to the current Store price. An unchanged snapshot or a completed report that flags rejected rows still counts as a report. Fictional demo mode has no product-event charge; platform usage may apply.

The report needs no external model, new collection service or hosted n8n instance. Your existing process remains responsible for collecting the authoritative source, applying destination changes and remembering which full snapshot was successfully applied.

## 1. Define one client collection

Choose a stable `corpusId`, such as `client-acme-help`. Use one configuration for that collection across runs:

| Input field | What to keep stable |
| --- | --- |
| `corpusId` | The namespace for this collection |
| `sourceField` | The top-level key identifying each document, usually `url` |
| `textField` | `auto`, or the exact top-level key containing text |
| `chunkChars` | Maximum characters per chunk |
| `overlapChars` | Overlap between chunks |

With `textField: "auto"`, non-empty `markdown` takes precedence over `text`. Dotted field names are literal top-level keys, not nested paths. Keep source identifiers consistent across exports; the Actor does not canonicalize URLs for you.

One report accepts at most **500 input rows**, including duplicate or invalid rows. For larger collections, define stable partitions, each with its own corpus ID and accepted baseline. Each claimed full snapshot must cover its entire defined partition. An arbitrary 500-row slice is not a complete snapshot of a larger corpus.

## 2. Inspect an existing dataset

In Apify Console, open the Actor, select **Existing Apify dataset**, choose a dataset your account can access, and grant read access. Retain supported source HTTP status and error metadata alongside the text so explicit failures can be checked.

This input is suitable for an initial inspection of partial data:

```json
{
  "inputMode": "dataset",
  "datasetId": "YOUR_DATASET_ID",
  "corpusId": "client-acme-help",
  "sourceField": "url",
  "textField": "auto",
  "chunkChars": 1800,
  "overlapChars": 150,
  "completeSnapshot": false
}
```

Replace `YOUR_DATASET_ID` with the actual source dataset ID. This is a paid non-demo input. If you have already verified that the dataset is the entire authoritative collection, you can use the full-snapshot process below for your first report.

The Actor reads the supplied records without visiting their source URLs. Inspect the report for rejected rows, duplicates, source identifiers and chunk text before choosing how to proceed.

## 3. Establish the first accepted full snapshot

Set `completeSnapshot: true` only when the dataset represents the entire authoritative collection. A successful upstream job alone does not prove that every expected document was collected. Missing pages that leave no record cannot be detected from the supplied rows.

For this first full report, omit `previousManifestStoreId`. Wait for the Actor run to succeed, then inspect the output links:

| Output | Required check before handoff |
| --- | --- |
| `SYNC_STATUS` | `status` is `COMPLETE`; `downstreamReady` is `true`; `baselineEligible` is `true` |
| `QA` | `downstreamReady` is `true`; there are no rejected rows or issues |
| `QA` and `SYNC_STATUS` | Matching `approvalStatus: "READY"`, empty `approvalReasons`, and `approvalScope: "SUPPLIED_RECORDS_ONLY"` |
| `MANIFEST` | `complete` is `true` and its configuration matches the collection |
| Chunk operations | Source-linked changes are appropriate for your destination; review any DELETE suggestions |

`COMPLETE` describes report delivery. It does not mean the input was approved or that your destination was updated. The readiness decision covers preparation of the supplied records; it does not certify source coverage, semantic accuracy or retrieval quality.

Apply the approved operations through your existing embedding/indexing workflow. **After the destination confirms that the full update succeeded**, record that report's default key-value store ID as the accepted baseline. Preserve access to it under your account's storage-retention settings. A generated manifest alone is not a committed baseline.

## 4. Pass the next fresh dataset and the accepted baseline

When the next complete snapshot is available, replace both placeholder IDs below with real, authorized IDs. Keep all corpus and chunk settings unchanged.

```json
{
  "inputMode": "dataset",
  "datasetId": "NEW_SNAPSHOT_DATASET_ID",
  "previousManifestStoreId": "LAST_ACCEPTED_MANIFEST_STORE_ID",
  "corpusId": "client-acme-help",
  "sourceField": "url",
  "textField": "auto",
  "chunkChars": 1800,
  "overlapChars": 150,
  "completeSnapshot": true
}
```

The new source dataset and previous manifest store must both be readable by the Actor. The previous manifest must belong to the same collection and configuration. Use only an eligible full baseline that your destination actually accepted.

An unchanged full snapshot can produce zero operations and still deliver a new report. A changed document can re-emit an existing chunk ID to update its metadata. Review DELETE suggestions against the new authoritative snapshot before applying them.

Process accepted updates for a given corpus in sequence. Keep the baseline fixed while an update is in progress, and advance it only after the destination acknowledges success. Overlapping updates must not independently replace the same baseline.

## 5. Trigger reports from your existing collection workflow

If an upstream Actor such as Website Content Crawler already produces your datasets, use its **Integrations** tab to run RAG Knowledge Base Sync & QA after a successful upstream run. Grant the target Actor read access to the produced dataset.

The native Apify integration input can contain:

```json
{
  "inputMode": "dataset",
  "datasetId": "{{resource.defaultDatasetId}}",
  "corpusId": "client-acme-help",
  "sourceField": "url",
  "textField": "auto",
  "chunkChars": 1800,
  "overlapChars": 150,
  "completeSnapshot": false
}
```

`{{resource.defaultDatasetId}}` is the native Apify integration value for the new upstream dataset. This example produces a review report. It does not declare the source complete, select the accepted baseline or update a destination.

For full comparisons, your existing orchestration must supply the last accepted `previousManifestStoreId`, establish that the new dataset is complete, and perform the readiness and destination-acknowledgement steps above. Do not store a candidate baseline before those steps succeed.

If you use a schedule or another API caller, supply the new snapshot's actual dataset ID on each run. Repeating a saved input with an old dataset ID checks the old snapshot again. Run when there is a fresh snapshot to check or corrected input to review; each completed non-demo report has the advertised charge.

Keep the run ID returned by the start request. Poll that same run if it is still queued or running. If the start response is lost, or a wait expires, inspect the existing run before starting another paid report. Do not enable automatic retries of the paid start request.

## 6. Handle each result explicitly

| Result | Action |
| --- | --- |
| Clean, explicitly complete snapshot with matching readiness fields | Review the operations and apply approved changes through your existing destination workflow |
| Rejected records, including a recorded HTTP failure | Inspect the QA findings; keep the existing destination and accepted baseline while correcting the source |
| Partial input | Use the prepared output for review; do not automatically apply it to the persistent index |
| Fictional demo | Inspect the sample; do not use it as a real baseline or destination update |
| Missing approval fields from an older Actor output | Keep it review-only; it does not establish the current handoff contract |
| Report is not COMPLETE, including `BUDGET_LIMIT` or `BILLING_UNKNOWN` | Inspect that run's log and completion state; do not apply its output or accept its baseline |
| Destination write fails or is uncertain | Keep the previous accepted baseline and reconcile the destination state |
| Destination confirms all approved UPSERTs and reviewed DELETEs were accepted | Save the candidate manifest-store ID as the next accepted baseline |

Rejected rows block automatic handoff even when valid chunks remain in the report. Partial or rejected-row reports must not replace the last accepted full baseline. Do not apply partial-batch operations between full snapshots while retaining an older baseline: new chunk IDs from those partial writes can become untracked and survive later cleanup. Empty input is rejected; it never means “delete everything.”

## Optional n8n handoff

Teams already using n8n can import the [workflow JSON](../n8n/rag-dataset-qa.json) and follow the [handoff and validation contract](n8n-validation.md). The workflow is inactive by default and exposes reviewed operations only after the documented checks. A destination integration must check `downstreamReady === true` and consume the top-level operation arrays; `review` is for inspection.

The recipe leaves `baseline.commitAllowed` and `baseline.updated` false. It has no destination write, acknowledgement or baseline-persistence step. Full import and execution in a live n8n instance have not been verified; the exported JavaScript has offline graph tests with mocked HTTP responses.

## Costs, limits and scope

| Item | Current behavior |
| --- | --- |
| Completed non-demo report | US$0.50 plus Apify platform usage; confirm the Store's displayed price |
| Unchanged snapshot or completed report that flags rejected rows | Still counts as one report |
| Empty or entirely rejected input | Fails before the product event; platform usage may still accrue |
| Fictional demo | No product-event charge; platform usage may apply |
| Input rows per report | At most 500 |
| Characters per document | At most 120,000 |
| Combined input text | At most 6,000,000 UTF-8 bytes |
| Chunks per snapshot | At most 8,000 |
| Chunk size | 250–5,000 characters |
| Overlap | 0–800 characters and strictly less than half the chunk size |

Character limits are not model-specific token counts. Oversized batches fail rather than silently becoming truncated snapshots. The optional n8n recipe sets a US$0.75 maximum run charge, 256 MB memory and a 90-second timeout; other runs use their selected options. Check your account's own usage limits as well.

Use only authorized records. Keep tokens out of public inputs and examples. For reproducible problems, use the [Actor's Issues tab](https://apify.com/millgrah/rag-knowledge-base-sync-qa/issues) with a small fictional example and the relevant error.
