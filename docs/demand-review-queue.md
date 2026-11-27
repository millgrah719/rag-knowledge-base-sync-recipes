# Public demand review queue

The existing daily integration workflow collects public GitHub issue signals at **14:23 UTC**. Its acquisition job runs independently of service-health checks. These are technical problem-fit candidates, not verified buyers, purchasing intent, permission to contact, or evidence of an author's Apify subscription.

## Canonical queue

The first successful published collection creates the separate **`demand-review-queue`** branch with only:

- [`queue.json`](https://github.com/millgrah719/rag-knowledge-base-sync-recipes/blob/demand-review-queue/queue.json): the durable URL-keyed ledger.
- [`report.md`](https://github.com/millgrah719/rag-knowledge-base-sync-recipes/blob/demand-review-queue/report.md): the latest generated review report.

These links exist only after initialization. The job summary also shows the report. There are no Actions artifact uploads, paid service calls, Actor runs, comments, emails or direct messages.

## Qualification and limits

Four RAG queries prioritize duplicate source records/chunks, missing crawler text, recorded source failures, source provenance and unnecessary re-embedding of full snapshots. Two separate commerce queries retain product-variant and price-data problems. A generic question or recommendation phrase is insufficient. Broad audits, roadmaps, learning-plan cards and research spikes are excluded conservatively. Keyword classification can still miss relevant issues or include unsuitable ones; review the actual request.

Each run searches issues updated within 21 days, takes at most 15 results per query, and adds at most 20 new records. RAG candidates rank first, then the number of matched fit reasons and source recency. The ledger holds at most 1,000 records and 1 MB. Existing records and decisions are never evicted: when the record limit is reached, new candidates are deferred and saturation is reported. Invalid or oversized saved state stops the update rather than replacing it.

All automatically added records start as **`needs_review`**. The collector stores issue URLs, topic/reason codes, query identifiers and timestamps; it does not save titles, full issue bodies, author profiles, contact details or financial attributes. An update timestamp is not evidence of new demand. Source changes are reported separately from first discovery. Older saved issues may have closed or changed outside the bounded search sample.

## Reviewing a candidate

Open the current issue and decide whether the supplied-record QA/chunking report actually helps. The RAG Actor does not crawl, embed, write to an index or automatically apply arbitrary incremental batches. Review-only partial input is not a complete destination integration.

Edit only the record's `review_status` and optional `review_note` in **queue.json on the queue branch**:

- `needs_review`: not yet assessed.
- `qualified_problem`: a reviewer confirmed a supported technical problem; this says nothing about willingness or ability to pay.
- `dismissed`: unsuitable; retain the record so it does not return as new.
- `resolved`: no remaining action identified.

Notes may contain at most 500 characters. Keep them factual and free of personal/customer data. Later runs preserve both fields and `first_seen_at`, including when the source changes. Do not remove records to dismiss them or edit the generated report. Any outreach is a separate action requiring authorization; this workflow never performs it.

## Persistence and maintenance

Only the acquisition job receives `contents: write`. It is restricted to the canonical repository, `main`, and push/schedule/manual-dispatch events; the Python publisher checks the same context. The token is passed only to the collection/publishing step and is not stored. The fixed write target is the queue branch, never main. GitHub's contents permission is repository-scoped, so these restrictions are enforced by the reviewed workflow/code rather than a branch-scoped token permission.

Initialization creates an isolated root commit containing only the ledger and report. Later commits use the observed queue head as their sole parent. The publisher checks for a changed head and uses a non-force update. A concurrent manual change, malformed queue or permission failure stops publishing; no force or automatic mutation retry is used. Partial search failures are disclosed while existing state is preserved; total search failure leaves the queue unchanged. The previous report remains current only as of its displayed collection time.

No external initialization is required once the workflow is published and its requested repository permission is allowed. If repository policy blocks branch creation/writes, fix the applicable permission or rule deliberately; do not broaden fork permissions or force a write. Do not merge the queue branch into main.

Run `python3 tools/public_demand_review.py --self-test` for focused offline tests. Running the script without `--publish` produces a read-only preview. Publishing is permitted only from the trusted workflow.
