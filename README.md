# Check and prepare RAG datasets before indexing

For developers and AI agencies who already have documentation text or an Apify crawler dataset. Review missing text, duplicate rows and conflicting sources, then export stable, source-linked chunks for your own indexing workflow.

**US$0.50 per completed non-demo report, plus Apify platform usage.** Each report accepts up to 500 source rows. You receive a QA report, chunk operations and a manifest for later snapshot comparisons.

**[Open RAG Knowledge Base Sync & QA](https://apify.com/millgrah/rag-knowledge-base-sync-qa)**

## Try it directly in Apify

An Apify account is required. You can try the Actor in Apify Console without installing Python or n8n and without creating an API token.

1. Open the Actor above and choose its **Fictional demo** input mode.
2. Start the demo and review its QA report and output dataset. The sample includes a repeated source row; the verified demo produces two UPSERT chunks and removes one duplicate row, with no rejected rows or deletion suggestions.
3. For your own report, select an existing dataset you can access or supply inline source records. Use a stable source key such as `url` and the corresponding `text` or `markdown`.
4. Review the output before passing it to your embedding or indexing tools. Leave `completeSnapshot` false for a first trial with partial data.

**Demo pricing:** Fictional demo mode has no product-event charge; platform usage may apply. **Dataset and inline modes are paid**, including the example configurations below. Confirm the current Store price before starting a paid run.

### Choose an example

| Your use case | Open the configured example | What to inspect |
|---|---|---|
| Prepare help-center text | [Help-center example](https://apify.com/millgrah/rag-knowledge-base-sync-qa/examples/prepare-help-center-text-for-rag) | Source-linked chunks and removal of an exact repeated row |
| Check problematic records before indexing | [Data-quality example](https://apify.com/millgrah/rag-knowledge-base-sync-qa/examples/review-document-data-before-rag-indexing) | Rejected records, conflicting sources and the QA summary |

The Actor processes supplied text. It does not crawl websites, create embeddings or update a vector database.

## Free offline data-quality check

Before paying for a full sync report, check a local JSON export for missing fields, duplicate rows, conflicting source identifiers and common input-limit problems.

[Download the Python preflight script](https://raw.githubusercontent.com/millgrah719/rag-knowledge-base-sync-recipes/main/tools/rag_preflight.py) · [View source](tools/rag_preflight.py). Requires Python 3; no dependencies, API key, signup, network requests or uploaded data.

```bash
python3 tools/rag_preflight.py --demo
python3 tools/rag_preflight.py documents.json
```

For custom fields, use `--source-field source_id --text-field content`. This diagnostic is deliberately limited: it does not generate chunks, apply changes, compare snapshots or reproduce the Actor's full validation. Use the [Apify Actor](https://apify.com/millgrah/rag-knowledge-base-sync-qa) for production reports, stable chunks and repeatable synchronization.

## What problem does this solve?

When crawler output contains repeated source rows, missing text or conflicting versions of the same source, sending everything straight into an embedding pipeline can create avoidable rework. This Actor prepares supplied text deterministically, preserves provenance and exposes a QA report and optional snapshot change operations. It does not scrape websites, generate embeddings or modify a vector database.

Supply existing crawler data or JSON records, wait for a successful run and a `COMPLETE` report, then review the QA, UPSERT chunks and any DELETE suggestions. `COMPLETE` means report production finished; it does not mean the supplied data is approved for indexing.

## n8n workflow (importable JSON)

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

**Automatic handoff requires a clean, explicitly complete snapshot and matching approval fields in both QA and SYNC_STATUS.** Rejected rows block the handoff. Partial input and fictional demos remain review-only. Older Actor outputs, including build 0.0.3, do not have the new approval contract and therefore remain review-only with `ACTOR_APPROVAL_UNAVAILABLE`. Updating this recipe does not deploy a new Actor build.

Read the [handoff and validation contract](docs/n8n-validation.md) before attaching a destination. The contract approves preparation of supplied records only; it cannot establish whether an upstream crawl captured the whole source.

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

This is the native Apify integration input, not an n8n expression. This partial-data example produces a report for review. A partial or failed crawl must not be treated as a complete authoritative snapshot.

## Compare snapshots safely

For a complete authoritative first snapshot, set `completeSnapshot: true` only after verifying source completeness. After the run succeeds, confirm `SYNC_STATUS.status` is `COMPLETE`, inspect QA, and require `downstreamReady: true` in both QA and SYNC_STATUS for an automatic handoff. The manifest must be complete and baseline-eligible. Older reports without the approval contract require manual review.

Review `DELETE` suggestions before applying them. Preserve the candidate run's default key-value store ID as the next `previousManifestStoreId` **only after the destination confirms all UPSERTs and reviewed DELETEs were accepted**. Until then, keep the previous baseline. Keep the corpus ID, field mappings and chunk settings the same between comparisons. The n8n workflow exposes a candidate store ID but leaves `baseline.commitAllowed` and `baseline.updated` false because it has no destination acknowledgement or persistence step.

A report with rejected input rows or partial input cannot replace the previous accepted full baseline. Do not apply partial-batch operations between full snapshots while retaining an older baseline: changed chunk IDs from the partial update can become untracked and survive later cleanup. This recipe keeps partial batches review-only. An unchanged full snapshot can return zero chunk operations.

## Costs and limits

- Fictional demo: no product-event charge; platform usage may apply.
- Non-demo: US$0.50 per completed report plus Apify usage, subject to the Store's displayed pricing.
- The workflow specifies a US$0.75 maximum run charge, 256 MB memory, and a 90-second timeout. Check your account's own usage limits as well.
- Maximum 500 input rows per report, 120,000 characters per document, 6 MB of input text, and 8,000 chunks per snapshot. Character chunks are not model token counts.
- Use authorized data only. No external model credentials are needed.

## Validation and feedback

Earlier Actor releases have had live demo, paid-report and dataset-comparison checks. This workflow's exported JavaScript is tested along its connection graph with mocked HTTP responses, including rejected records, partial input, older Actor output, manifest disagreement and demo isolation. Full import and execution in a live n8n instance have not been verified. These checks do not establish customer sales, destination delivery or deployment of a new Actor release. Start with the fictional demo and report reproducible issues using the [Actor's Issues tab](https://apify.com/millgrah/rag-knowledge-base-sync-qa/issues). Do not include customer data or credentials.

Questions about reducing re-embedding work or maintaining multiple client knowledge bases are welcome. Try the demo first, then use a real dataset when ready.

## Build a product-catalog knowledge base

For ecommerce and agency teams using structured product data in support tools, this recipe connects two separate services:

1. Normalize an authorized product JSON-LD export using [Variant Ledger on RapidAPI](https://rapidapi.com/GrahamMiller/api/variant-ledger-product-variant-normalizer). Save the actual normalization response as `normalized.json`.
2. Run the free, local [commerce knowledge-base input adapter](tools/commerce_kb_input.py):

   ```bash
   python3 tools/commerce_kb_input.py --self-test
   python3 tools/commerce_kb_input.py normalized.json --corpus-id catalog-support > apify-input.json
   ```

3. Review the resulting inline input, then use [RAG Knowledge Base Sync & QA on Apify](https://apify.com/millgrah/rag-knowledge-base-sync-qa). Choose Inline JSON records and use the generated input.

The adapter uses stable SKU keys, rejects normalization warnings and errors, and excludes prices and stock availability so volatile offers are not presented as permanent knowledge. It defaults to a partial snapshot and does not perform network calls, indexing, or destructive operations. Preserve the original normalization output separately for provenance. Review all generated content before using it in retrieval systems. Offline self-tests passed; a combined paid live workflow has not been tested. Marketplace pricing and platform usage charges apply to actual service calls.

## Try the commerce adapter without spending

Start with these fictional fixtures instead of your own catalog:

- [Product-group request JSON](examples/commerce-product-group-input.json) — paste into the Variant Ledger RapidAPI playground using your own subscription and check the displayed charges.
- [Synthetic normalization fixture](examples/commerce-normalized-offline-fixture.json) — use this to test the local adapter without an account, key, network call or payment. It is illustrative data, not a captured live API response.

```bash
python3 tools/commerce_kb_input.py examples/commerce-normalized-offline-fixture.json --corpus-id catalog-support > apify-input.json
```

The expected local output is two SKU-keyed text records, with `completeSnapshot: false` and no price or stock attributes. Inspect the result before submitting any data to Apify. Running the offline example costs nothing; a non-demo Apify report and any applicable marketplace usage are charged separately. [Try Variant Ledger](https://rapidapi.com/GrahamMiller/api/variant-ledger-product-variant-normalizer) · [Open the Apify Actor](https://apify.com/millgrah/rag-knowledge-base-sync-qa).

## Agent-ready catalog QA guide

[Catalog knowledge-base QA skill](skills/catalog-knowledge-base-qa/SKILL.md) provides a local review and conversion workflow for existing product and documentation exports. It is free to read and uses the two paid services only if the user separately requests and authorizes the applicable external calls. It does not crawl, create embeddings, or automatically modify a database. [Variant Ledger](https://rapidapi.com/GrahamMiller/api/variant-ledger-product-variant-normalizer) and [RAG Knowledge Base Sync & QA](https://apify.com/millgrah/rag-knowledge-base-sync-qa) remain separately billed marketplace services.

