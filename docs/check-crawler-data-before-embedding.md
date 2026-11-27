# Check crawler records before a RAG refresh

An extraction job can finish while its dataset still contains repeated rows, empty text or two different versions of one source. Check those records before preparing an update for your embedding and indexing workflow.

This walkthrough uses **fictional help-center records**. You can reproduce the first part locally with Python 3, without an account, token, dependency installation or network request. The local check is free; the optional hosted Actor has separate pricing below.

## Reproduce three input problems locally

Download this repository, then run from its root:

```bash
python3 tools/rag_preflight.py examples/rag-preflight-input.json
```

The [five-row input](../examples/rag-preflight-input.json) deliberately includes:

| Source | Supplied data | Finding |
| --- | --- | --- |
| `/help/export` | The same source and text appear twice | One duplicate row |
| `/help/billing` | A source URL with empty text | One missing-text row |
| `/help/workspaces` | Two different texts under the same source URL | One conflicting source key |

These are separate problems. A repeated identical row can be collapsed. Missing text needs a corrected extraction. Conflicting versions need an authoritative source decision; keeping whichever row arrived first is not a reliable way to choose.

The actual local result includes:

```json
{
  "input_rows": 5,
  "rows_with_source_and_text": 4,
  "duplicate_rows": 1,
  "conflicting_source_keys": 1,
  "unique_nonconflicting_sources": 1,
  "invalid_row_counts": {
    "missing text": 1
  }
}
```

The script reports findings. A successful script exit means the inspection completed, not that the records are approved for indexing. It does not create chunks, compare snapshots, inspect HTTP failure metadata, verify source completeness or reproduce the hosted Actor's complete validation.

## Check a corrected example

For the fictional correction, the repeated row is removed, the missing article is supplied and one workspace article is designated authoritative:

```bash
python3 tools/rag_preflight.py examples/rag-preflight-fixed.json
```

The [corrected input](../examples/rag-preflight-fixed.json) produces three nonconflicting sources, zero duplicate rows, zero conflicting source keys and an empty `invalid_row_counts` object. The example demonstrates the input checks; it is not evidence of improved chatbot accuracy or a customer deployment.

For your own local JSON array, run:

```bash
python3 tools/rag_preflight.py your-documents.json
```

By default, `url` identifies a source and non-empty `markdown` takes precedence over `text`. Use `--source-field` and `--text-field` for other top-level fields. Identical text at different source URLs stays separate. The script sends nothing to a remote service.

## Use the hosted report when you need prepared chunks and comparisons

[RAG Knowledge Base Sync & QA](https://apify.com/millgrah/rag-knowledge-base-sync-qa) accepts supplied text or an authorized Apify dataset. It prepares stable source-linked chunks, reports supported recorded source failures and compares eligible complete snapshots with a previous manifest. It returns QA and readiness decisions plus `UPSERT` operations and guarded `DELETE` suggestions for your own ingestion workflow.

**US$0.50 per completed non-demo report, plus Apify platform usage; at most 500 input rows per report.** Confirm the current Store price. Completed unchanged reports and completed reports with rejected rows are still billable. Empty or entirely rejected input fails before the product event; platform usage may still accrue. Fictional demo mode has no product-event charge, although platform usage may apply.

Start with **Fictional demo** in Apify Console. For your own data, check an existing dataset using the [recurring documentation guide](recurring-documentation-checks.md). Teams with a Python job can use the [standalone dataset runner](python-dataset-runner.md); it starts one explicitly authorized report, saves its run receipt and supports resuming that same run.

The Actor does not crawl, create embeddings, write to a vector database, measure retrieval quality or certify that your crawler captured every expected page.

## Keep incomplete refreshes out of the accepted baseline

Only declare a snapshot complete when your collection process establishes that it covers the entire intended corpus. An absent page without an error record cannot be inferred from supplied rows alone.

Before an automated handoff, require a successful Actor run, a `COMPLETE` report and matching `downstreamReady: true` decisions in both QA and completion status. Check the full readiness contract in the [recurring guide](recurring-documentation-checks.md). Partial input, rejected rows and fictional demo output stay review-only.

Apply approved operations through your existing destination workflow and review deletion suggestions. Advance the accepted manifest only after that destination acknowledges the entire update. If an update fails or its result is uncertain, retain the previous accepted baseline and reconcile what happened.

## Ask an integration question

Use the [integration question form](https://github.com/millgrah719/rag-knowledge-base-sync-recipes/issues/new?template=integration-question.yml) for a small fictional reproduction or a question about connecting an existing dataset. Posts are public. Include the input shape and the result you expected; keep client records, tokens, private IDs and contact details out of the issue.

Independent software maintained by the Actor's developer; not an official Apify integration.
