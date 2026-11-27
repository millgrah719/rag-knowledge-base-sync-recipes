# Check recurring help-center imports before indexing

For AI agency developers who already use Apify datasets to maintain client support chatbots. Check each new documentation snapshot for missing text, conflicting source records, repeated rows and supported source-error metadata before handing it to your existing indexing workflow.

**US$0.50 per completed non-demo report, plus Apify platform usage. Up to 500 input rows per report.** No external AI model is required.

**[Try RAG Knowledge Base Sync & QA](https://apify.com/millgrah/rag-knowledge-base-sync-qa)** · **[Set up recurring dataset checks](docs/recurring-documentation-checks.md)**

| You already have | You receive | Your workflow controls |
| --- | --- | --- |
| Documentation text in an authorized Apify dataset | A QA report with row-level findings and a readiness decision | Whether the supplied dataset represents the whole source |
| Stable source identifiers and `markdown` or `text` | Source-linked chunks with stable IDs | Embedding and indexing at your destination |
| A new full snapshot and the last accepted manifest | `UPSERT` operations and guarded `DELETE` suggestions | Applying reviewed changes and advancing the accepted baseline |

The Actor processes supplied records. It does not crawl websites, create embeddings or write to a vector database. A report can finish successfully while blocking an indexing update.

## 1. Try the fictional demo

An Apify account is required. Open the Actor in Apify Console and choose **Fictional demo**. No Python installation, n8n instance or API token is needed for this Console trial.

Start the demo and open **Quality report**, **Chunk operations**, **Sync manifest** and **Completion status**. The verified sample produces two UPSERT chunks, removes one duplicate source row and has no rejected rows or deletion suggestions. Its readiness decision stays `REVIEW_REQUIRED` because fictional data is preview-only.

**Demo mode has no product-event charge; platform usage may apply.** Dataset and inline modes are paid, including the configured examples below. The Store's displayed price is authoritative.

## 2. Check an existing dataset

Choose **Existing Apify dataset**, select a source dataset your account can access, and grant read access. Use a stable source key such as `url`; `textField: "auto"` prefers non-empty `markdown` and falls back to `text`.

For an initial inspection of partial data, use:

```json
{
  "inputMode": "dataset",
  "datasetId": "YOUR_DATASET_ID",
  "corpusId": "client-help-center",
  "sourceField": "url",
  "textField": "auto",
  "chunkChars": 1800,
  "overlapChars": 150,
  "completeSnapshot": false
}
```

Replace the dataset ID with the real ID. Preserve supported HTTP status and error metadata from the source records. A non-empty HTTP error page can still be rejected when its failure is recorded in that metadata.

Wait for a successful run and a `COMPLETE` report, then inspect QA and the prepared operations. `COMPLETE` means report delivery finished. The separate `downstreamReady` decision determines whether the supplied records are eligible for handoff. Partial reports remain review-only. If you have already verified that the dataset is the entire authoritative corpus, follow the full-snapshot steps in the recurring guide.

| Inspect a worked example | What it demonstrates |
| --- | --- |
| [Help-center example](https://apify.com/millgrah/rag-knowledge-base-sync-qa/examples/prepare-help-center-text-for-rag) | Source-linked chunks and removal of an exact repeated row |
| [Data-quality example](https://apify.com/millgrah/rag-knowledge-base-sync-qa/examples/review-document-data-before-rag-indexing) | Rejected records, conflicting source identifiers and the QA summary |

## 3. Run another check when documentation changes

Keep one stable corpus configuration for each client collection. On the next refresh, pass the **new snapshot's dataset ID** and, when comparing changes, the **last successfully applied full report's manifest-store ID**.

The [recurring documentation guide](docs/recurring-documentation-checks.md) covers the first accepted baseline, native Apify integration with an existing collection workflow, readiness decisions, failed updates and when to advance the baseline. It uses your existing datasets and destination workflow; no additional hosted service is required for the report.

Run when there is a new snapshot to check or corrected input to review. Repeatedly scheduling an unchanged historical dataset still creates billable completed reports, even when there are zero change operations.

## Compare snapshots safely

For a complete authoritative first snapshot, set `completeSnapshot: true` only after verifying source completeness. After the run succeeds, confirm `SYNC_STATUS.status` is `COMPLETE`, inspect QA, and require `downstreamReady: true` in both QA and SYNC_STATUS for an automatic handoff. The manifest must be complete and baseline-eligible. Older reports without the approval contract require manual review.

Review `DELETE` suggestions before applying them. Preserve the candidate run's default key-value store ID as the next `previousManifestStoreId` **only after the destination confirms all UPSERTs and reviewed DELETEs were accepted**. Until then, keep the previous baseline. Keep the corpus ID, field mappings and chunk settings the same between comparisons. The n8n workflow exposes a candidate store ID but leaves `baseline.commitAllowed` and `baseline.updated` false because it has no destination acknowledgement or persistence step.

A report with rejected input rows or partial input cannot replace the previous accepted full baseline. Do not apply partial-batch operations between full snapshots while retaining an older baseline: changed chunk IDs from the partial update can become untracked and survive later cleanup. This recipe keeps partial batches review-only. An unchanged full snapshot can return zero chunk operations.

## Optional workflow for teams already using n8n

[Download the workflow JSON](https://raw.githubusercontent.com/millgrah719/rag-knowledge-base-sync-recipes/main/n8n/rag-dataset-qa.json) · [View source](n8n/rag-dataset-qa.json). Import the JSON into your n8n instance. This is an independently authored integration recipe, not an official n8n or Apify template.

1. Create an Apify account and an API token. In n8n create a **Header Auth** credential with header name `Authorization` and value `Bearer YOUR_APIFY_TOKEN`. Never paste your token into the workflow JSON.
2. Select the credential in all six HTTP Request nodes: Start Apify report, Wait for same run, Read completion status, Read QA, Read manifest and Read chunk operations.
3. Execute the manual trigger with the default fictional demo. Inspect two sample chunks under `review.upserts`, no deletion suggestions, and a QA report with one duplicate row removed and zero rejected rows. The top-level operation arrays stay empty because demo data is preview-only.
4. To use your own Apify dataset, replace the JSON returned in **Choose input** with the object below. The dataset must be accessible to your Apify account and contain a stable source key and text. Non-demo billing applies.
5. Review QA and deletion suggestions before connecting the result to your embedding/indexing tools. A destination integration must check `downstreamReady === true` and consume only the top-level operation arrays. The workflow is inactive by default and does not write to an index or save a new baseline.

```javascript
return [{json: {
  inputMode: "dataset",
  datasetId: "YOUR_DATASET_ID",
  corpusId: "my-help-center",
  sourceField: "url",
  textField: "auto",
  chunkChars: 1800,
  overlapChars: 150,
  completeSnapshot: false
}}];
```

The initial request waits up to 60 seconds. The workflow then reads that same run with an additional wait of up to 60 seconds, without starting another report. It reads outputs only when the run succeeds and the report is COMPLETE, then validates QA, the manifest and operation counts. Queueing can exceed this bounded wait. If the workflow stops, inspect the exact run ID before deciding whether another paid report is needed. Do not turn on automatic POST retries.

**Automatic handoff requires a clean, explicitly complete snapshot and matching approval fields in both QA and SYNC_STATUS.** Rejected rows block the handoff. Partial input and fictional demos remain review-only. Actor build 0.1.1, released on November 26, 2026, includes this approval contract. Older Actor outputs, including build 0.0.3, do not have the new approval contract and therefore remain review-only with `ACTOR_APPROVAL_UNAVAILABLE`.

Read the [handoff and validation contract](docs/n8n-validation.md) before attaching a destination. The contract approves preparation of supplied records only; it cannot establish whether an upstream crawl captured the whole source.

## Free offline data-quality check

Before paying for a full sync report, check a local JSON export for missing fields, duplicate rows, conflicting source identifiers and common input-limit problems.

[Download the Python preflight script](https://raw.githubusercontent.com/millgrah719/rag-knowledge-base-sync-recipes/main/tools/rag_preflight.py) · [View source](tools/rag_preflight.py). Requires Python 3; no dependencies, API key, signup, network requests or uploaded data.

```bash
python3 tools/rag_preflight.py --demo
python3 tools/rag_preflight.py documents.json
```

For custom fields, use `--source-field source_id --text-field content`. This diagnostic is deliberately limited: it does not generate chunks, apply changes, compare snapshots or reproduce the Actor's full validation. Use the [Apify Actor](https://apify.com/millgrah/rag-knowledge-base-sync-qa) for production reports, stable chunks and repeatable synchronization.

## Costs and processing limits

- Fictional demo: no product-event charge; Apify platform usage may apply.
- Completed non-demo report: **US$0.50 plus Apify platform usage**, subject to the current Store price. One report is one batch, not one document or chunk.
- An unchanged snapshot or a completed report with rejected rows still counts as a report. Empty or entirely rejected input fails before the product event; platform usage may still accrue.
- The optional n8n recipe specifies a US$0.75 maximum run charge, 256 MB memory and a 90-second timeout. Check your account's own usage limits and the options of any other run you start.

| Limit | Maximum or permitted range |
| --- | ---: |
| Input rows per report | 500 |
| Characters per document | 120,000 |
| Combined input text | 6,000,000 UTF-8 bytes |
| Chunks per snapshot | 8,000 |
| Characters per chunk | 250–5,000 |
| Overlap characters | 0–800; strictly less than half the chunk size |

Character chunks are not model-specific token counts. Use authorized data only and grant access only to the selected source dataset and previous manifest store. No external model credentials are required.

## Validation and feedback

Live Actor checks of build 0.1.1 on November 26, 2026 verified the fictional demo and a mixed inline report containing a recorded HTTP 503 failure. Earlier releases have had live demo, paid-report and dataset-comparison checks.

The optional n8n workflow's exported JavaScript is tested along its connection graph with mocked HTTP responses, including rejected records, partial input, older Actor output, manifest disagreement and demo isolation. Full import and execution in a live n8n instance have not been verified. A destination integration must be checked separately before it applies changes or advances a baseline.

For reproducible problems, use the [Actor's Issues tab](https://apify.com/millgrah/rag-knowledge-base-sync-qa/issues). Include a small fictional example and the relevant error; keep customer records and credentials private.

## Optional product-catalog integration

Working with existing product exports instead of documentation? The separate [product-catalog guide](docs/product-catalog-knowledge-base.md) covers the local commerce adapter, fictional fixtures, Variant Ledger integration and catalog QA skill. The documentation workflow above does not require that second marketplace service.
