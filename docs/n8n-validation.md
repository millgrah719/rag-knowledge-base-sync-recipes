# n8n report review and handoff contract

This workflow starts one Apify report and reads its outputs. It does not generate embeddings, write to an index, apply deletions, or save a new baseline.

## Import and first run

Import `n8n/rag-dataset-qa.json`. Select an n8n Header Auth credential containing `Authorization: Bearer YOUR_TOKEN` in all six HTTP Request nodes: Start Apify report, Wait for same run, Read completion status, Read QA, Read manifest, and Read chunk operations. The exported workflow contains no credential and is inactive.

The default input is a fictional demo. Its chunks appear under `review.upserts`. The top-level `upserts` and `deleteSuggestions` arrays stay empty because a demo must not be handed to a real index. Platform usage may apply to the demo; non-demo completed reports use the Actor's separately advertised pricing. Check current pricing and available credit before starting a run.

The workflow makes one POST, then one bounded GET for the same run. Neither automatically retries the paid start. If the start response is lost or the wait expires, inspect that exact run or recent runs in Apify before starting another report.

## Three separate states

| Field | Meaning |
| --- | --- |
| `reportComplete` | The run succeeded and `SYNC_STATUS.status` is `COMPLETE`. Report production finished. |
| `qaAccepted` | The supplied QA report has no rejected rows or issues and contains accepted documents. This alone does not permit downstream handoff. |
| `downstreamReady` | The input explicitly declares a full authoritative snapshot, the manifest and completion metadata agree, QA is clean, the Actor provides matching approval fields, and the output is not fictional demo data. This is a candidate for downstream processing, not proof of delivery. |

Any rejected source row blocks the entire automatic handoff. The remaining valid chunks remain inspectable under `review`, but the top-level operation arrays are empty. Malformed QA, manifest disagreement, truncated operation arrays, duplicate chunk IDs, unexpected operations, or another corpus's data stop the workflow with an error.

The approval contract must be present in both QA and completion metadata:

```json
{
  "downstreamReady": true,
  "approvalStatus": "READY",
  "approvalReasons": [],
  "approvalScope": "SUPPLIED_RECORDS_ONLY"
}
```

Older Actor outputs, including version 0.0.3, do not establish this approval contract. They remain available for review with `ACTOR_APPROVAL_UNAVAILABLE`, even when their report is complete and their QA counters are clean. This behavior does not assume that a new Actor build has been deployed.

The scope is deliberately limited to supplied records. A caller's `completeSnapshot: true` assertion does not independently prove that an upstream crawler captured every authoritative document. Only set it after verifying source completeness.

## Partial and incremental input

Omitted `completeSnapshot` becomes `false` before the POST. Strings such as `"true"`, numbers, and null are rejected; the workflow never infers completeness from crawler success or dataset presence.

Partial and incremental batches are always review-only. Applying their updates while retaining an older full baseline can leave obsolete chunks behind during later comparisons. This recipe therefore supplies no automatic handoff for that case. An incremental destination integration would need its own accepted-state tracking and replacement logic.

## Baseline advancement

The output's `baseline.previousManifestStoreId` preserves the baseline reference provided by the caller. A clean approved full snapshot may produce `baseline.candidateManifestStoreId`, but:

- `baseline.commitAllowed` remains `false`.
- `baseline.updated` remains `false`.
- `baseline.requiresDestinationAcknowledgement` remains `true`.

Keep the previous baseline until the destination confirms that all UPSERT operations and reviewed DELETE suggestions were accepted. A failed, partial, or uncertain destination write must not advance it. No destination acknowledgement or baseline persistence exists in this workflow. A downstream integration must implement that separately.

`review` is an inspection object. Do not connect it to an index writer. A downstream integration must check `downstreamReady` and consume only the top-level operation arrays; DELETE suggestions still require review.

## What has been tested

Run `node tests/workflow.test.mjs` to execute the exported Code-node JavaScript along the actual connection graph with mocked HTTP responses. The checks cover bounded same-run waiting, missing run IDs, incomplete billing/report states, QA rejection, partial inputs, legacy Actor output, approval fields, manifest mismatch, operation integrity, demo isolation, and pending baseline acceptance.

These are offline fixture tests. They do not establish live n8n import or execution, credentials, network behavior, actual Actor availability, charges, customer revenue, or destination writes. No live n8n server test has been performed for this export.
