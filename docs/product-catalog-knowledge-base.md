# Build a product-catalog knowledge base

[Back to documentation dataset checks](../README.md)

Run the commands below from the repository root. This is an optional workflow for existing product exports; the documentation dataset workflow does not require Variant Ledger.

For ecommerce and agency teams using structured product data in support tools, this recipe connects two separate services:

1. Normalize an authorized product JSON-LD export using [Variant Ledger on RapidAPI](https://rapidapi.com/GrahamMiller/api/variant-ledger-product-variant-normalizer). Save the actual normalization response as `normalized.json`.
2. Run the free, local [commerce knowledge-base input adapter](../tools/commerce_kb_input.py):

   ```bash
   python3 tools/commerce_kb_input.py --self-test
   python3 tools/commerce_kb_input.py normalized.json --corpus-id catalog-support > apify-input.json
   ```

3. Review the resulting inline input, then use [RAG Knowledge Base Sync & QA on Apify](https://apify.com/millgrah/rag-knowledge-base-sync-qa). Choose Inline JSON records and use the generated input.

The adapter uses stable SKU keys, rejects normalization warnings and errors, and excludes prices and stock availability so volatile offers are not presented as permanent knowledge. It defaults to a partial snapshot and does not perform network calls, indexing, or destructive operations. Preserve the original normalization output separately for provenance. Review all generated content before using it in retrieval systems. Offline self-tests passed; a combined paid live workflow has not been tested. Marketplace pricing and platform usage charges apply to actual service calls.

## Try the commerce adapter without spending

Start with these fictional fixtures instead of your own catalog:

- [Product-group request JSON](../examples/commerce-product-group-input.json) — paste into the Variant Ledger RapidAPI playground using your own subscription and check the displayed charges.
- [Synthetic normalization fixture](../examples/commerce-normalized-offline-fixture.json) — use this to test the local adapter without an account, key, network call or payment. It is illustrative data, not a captured live API response.

```bash
python3 tools/commerce_kb_input.py examples/commerce-normalized-offline-fixture.json --corpus-id catalog-support > apify-input.json
```

The expected local output is two SKU-keyed text records, with `completeSnapshot: false` and no price or stock attributes. Inspect the result before submitting any data to Apify. Running the offline example costs nothing; a non-demo Apify report and any applicable marketplace usage are charged separately. [Try Variant Ledger](https://rapidapi.com/GrahamMiller/api/variant-ledger-product-variant-normalizer) · [Open the Apify Actor](https://apify.com/millgrah/rag-knowledge-base-sync-qa).

## Agent-ready catalog QA guide

[Catalog knowledge-base QA skill](../skills/catalog-knowledge-base-qa/SKILL.md) provides a local review and conversion workflow for existing product and documentation exports. It is free to read and uses the two paid services only if the user separately requests and authorizes the applicable external calls. It does not crawl, create embeddings, or automatically modify a database. [Variant Ledger](https://rapidapi.com/GrahamMiller/api/variant-ledger-product-variant-normalizer) and [RAG Knowledge Base Sync & QA](https://apify.com/millgrah/rag-knowledge-base-sync-qa) remain separately billed marketplace services.
