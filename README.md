# Prepare RAG knowledge-base data with Apify and n8n

A practical integration for AI agencies, support-chatbot builders and document ingestion pipelines. If you already collect help-center or documentation text, this recipe turns it into stable, source-linked chunks and a quality report before you embed or index it.

**[Try the RAG Knowledge Base Sync & QA Actor](https://apify.com/millgrah/rag-knowledge-base-sync-qa)** · [Help-center example](https://apify.com/millgrah/rag-knowledge-base-sync-qa/examples/prepare-help-center-text-for-rag) · [Data-quality example](https://apify.com/millgrah/rag-knowledge-base-sync-qa/examples/review-document-data-before-rag-indexing)

## What problem does this solve?

When crawler output contains repeated source rows, missing text or conflicting versions of the same source, sending everything straight into an embedding pipeline can create avoidable rework. This Actor prepares supplied text deterministically, preserves provenance and exposes a QA report and optional snapshot change operations. It does not scrape websites, generate embeddings or modify a vector database.

```
Existing crawler dataset or JSON records
       ↓
RAG Knowledge Base Sync & QA
       ↓
Successful run + COMPLETE status check
       ↓
QA report + stable UPSERT chunks + reviewable DELETE suggestions
       ↓
Your own indexing workflow
```

## n8n workflow (importable JSON)

[Download the workflow](n8n/rag-dataset-qa.json). Import the JSON into your n8n instance. This is an independently authored integration recipe, not an official n8n or Apify template.

1. Create an Apify account and an API token. In n8n create a **Header Auth** credential with header name `Authorization` and value `Bearer YOUR_APIFY_TOKEN`. Never paste your token into the workflow JSON.
2. Select the credential in all four HTTP Request nodes: Start Apify report, Read completion status, Read QA and Read chunk operations.
3. Execute the manual trigger with the default fictional demo. The expected output is two UPSERT chunks, no deletion suggestions, and a QA report with one duplicate row removed and zero rejected rows.
4. To use your own Apify dataset, replace the JSON returned in **Choose input** with the object below. The dataset must be accessible to your Apify account and contain a stable source key and text. Non-demo billing applies.
5. Review QA and deletion suggestions before connecting the result to your embedding/indexing tools. The workflow is inactive by default.

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

The API call waits up to 60 seconds. If a run is not confirmed successful, the workflow stops. Inspect that run in Apify Console before retrying; the run may still be active. Do not turn on automatic POST retries.

## Connect directly after Website Content Crawler

In the upstream Actor's Integrations tab, add RAG Knowledge Base Sync & QA as a target when the crawler succeeds. Grant the target read access to the source dataset. The target input can use:

```json
{
  "inputMode": "dataset",
  "datasetId": "{{resource.defaultDatasetId}}",
  "corpusId": "my-help-center",
  "completeSnapshot": false
}
```

This is the native Apify integration input, not an n8n expression. A partial or failed crawl must not be treated as a complete authoritative snapshot.

## Compare snapshots safely

For a complete authoritative first snapshot, set `completeSnapshot: true`. After the run succeeds, confirm `SYNC_STATUS.status` is `COMPLETE`, `baselineEligible` is true and `MANIFEST.complete` is true. Preserve that run's default key-value store ID. Supply it as `previousManifestStoreId` on the next run; keep the corpus ID, field mappings, and chunk settings the same.

Review `DELETE` suggestions before applying them. A report with rejected input rows or partial input cannot replace the previous eligible baseline. An unchanged snapshot can return zero chunk operations.

## Costs and limits

- Fictional demo: no product-event charge; platform usage may apply.
- Non-demo: US$0.50 per completed report plus Apify usage, subject to the Store's displayed pricing.
- The workflow specifies a US$0.75 maximum run charge, 256 MB memory, and a 90-second timeout. Check your account's own usage limits as well.
- Maximum 500 input rows per report, 120,000 characters per document, 6 MB of input text, and 8,000 chunks per snapshot. Character chunks are not model token counts.
- Use authorized data only. No external model credentials are needed.

## Validation and feedback

The underlying Actor's live demo, paid-report, and dataset-comparison paths have been tested. The n8n recipe is new; its full execution in an n8n instance has not yet been verified. Start with the fictional demo and report reproducible issues using the [Actor's Issues tab](https://apify.com/millgrah/rag-knowledge-base-sync-qa/issues). Do not include customer data or credentials.

Questions about reducing re-embedding work or maintaining multiple client knowledge bases are welcome. Try the demo first, then use a real dataset when ready.
