# Run a fresh dataset report from an existing Python workflow

[Customer runner](../examples/run_dataset_report.py) · [Recurring dataset guide](recurring-documentation-checks.md) · [Actor](https://apify.com/millgrah/rag-knowledge-base-sync-qa)

Use this standard-library Python 3 example when you already have a script, CI job or other execution environment that receives a **fresh Apify dataset ID**. It needs no n8n instance, package installation, model key or additional hosted service. The runner does not start a crawler or provision a scheduler. For Console-only report delivery, the native crawler-success integration in the recurring guide remains the shortest setup.

## One-time setup

Download `examples/run_dataset_report.py`, or run it from this repository. Supply your own Apify token through the **`APIFY_TOKEN` environment variable**, using your existing environment/CI secret setting. Do not paste the token into the script, a command argument, a shared log or source control. The token needs permission to run the Actor and read the relevant run/input/output storages; the Actor must be allowed to read the supplied source dataset and accepted baseline.

The example pins the verified **0.1.1** build and checks its immutable identity. It requests 256 MB memory, a 90-second Actor timeout and a **US$0.75 maximum run charge**. Each completed non-demo report is currently **US$0.50 plus platform usage**, subject to Store pricing. An unchanged snapshot and a completed report with rejected rows can still be charged. `--start-paid-report` is the deliberate opt-in to one paid start; it has no automatic retry.

## Check the next fresh dataset

Have your existing workflow replace the dataset placeholder with the actual new dataset ID. Keep the corpus ID stable for this collection. The output directory must not already exist.

```bash
python3 examples/run_dataset_report.py \
  --start-paid-report \
  --dataset-id NEW_DATASET_ID \
  --corpus-id client-help-center \
  --output-dir reports/new-crawl
```

This defaults to **partial/review-only** input. It saves the QA, manifest and inspectable operations but exposes no automatic handoff operations. It cannot independently prove that the dataset is fresh or complete; the caller supplies the correct new ID.

If you have verified that the dataset covers the **entire authoritative collection**, add `--complete-snapshot`. On later comparisons, also supply only the last full manifest that the destination actually accepted:

```bash
python3 examples/run_dataset_report.py \
  --start-paid-report \
  --dataset-id NEW_DATASET_ID \
  --corpus-id client-help-center \
  --complete-snapshot \
  --previous-manifest-store-id LAST_ACCEPTED_STORE_ID \
  --output-dir reports/next-crawl
```

Omit the previous-store option for the first full snapshot. The displayed placeholders are deliberately rejected; use real Apify IDs. Optional `--source-field`, `--text-field`, `--chunk-chars` and `--overlap-chars` must stay consistent between snapshots. Limits remain 500 input rows, 6 MB of source text and 8,000 chunks. Preserve recorded HTTP/error metadata in source records.

## Use the result safely

The runner creates a private local output directory with:

- **`run.json`**: token-free input and run ID for recovery, saved as soon as the ID is known.
- **`result.json`**: produced only after a successful run and a `COMPLETE` report, with validated QA, manifest and operation counts.

| Exit code | Meaning |
|---|---|
| `0` | Full, clean, explicitly approved report; `downstreamReady` is true. Inspect/apply its top-level operations through your existing destination workflow. |
| `2` | Completed report held for review; top-level `upserts` and `deleteSuggestions` are empty. |
| `1` | Invalid input, API/output failure, unconfirmed start or bounded wait expiry. Inspect the receipt/run before another start. |

An approved unchanged snapshot can have zero operations. Rejected records, partial batches, missing approval fields and demo data cannot produce an automatic handoff. The `review.operations` field is for inspection only. Never wire it to a destination. DELETEs remain suggestions requiring review.

The result exposes a candidate manifest-store ID only when ready. **It never writes to an index, deletes destination records, acknowledges delivery or advances a baseline.** `baseline.updated` and `baseline.commitAllowed` remain false. After your destination confirms all approved UPSERTs and reviewed DELETEs were accepted, your existing workflow may save the candidate ID as its next accepted baseline. On a failed or uncertain destination write, retain the previous baseline. Process one accepted update per corpus at a time.

## Resume without another paid start

Polling waits at most 180 seconds by default; `--wait-seconds` allows 1–600 seconds. Individual API requests also have timeouts. Expiry does not abort a queued/running Actor, refund it or start another run.

Read the run ID in `run.json` or the printed recovery message, then resume with the **same dataset/corpus/chunk/full-snapshot/baseline arguments** and a new output directory:

```bash
python3 examples/run_dataset_report.py \
  --resume-run-id EXISTING_RUN_ID \
  --dataset-id NEW_DATASET_ID \
  --corpus-id client-help-center \
  --complete-snapshot \
  --previous-manifest-store-id LAST_ACCEPTED_STORE_ID \
  --output-dir reports/next-crawl-resumed
```

Resume performs only GET requests and verifies the run's Actor/build and saved INPUT against your arguments. Reusing an existing output directory is refused before any API call, helping prevent an accidental second start. Use a distinct directory for each fresh dataset/report attempt.

If the POST response was lost, `run.json` can remain `START_UNCONFIRMED` without a run ID. Inspect your recent Apify runs in Console, identify the matching input, and resume that run ID. Do not retry the paid start blindly. No start request or HTTP redirect is automatically retried.

## Validation and integration

Run `python3 -m unittest discover -s tests -p test_dataset_runner.py` for focused offline tests. They use fictional outputs and a fake API; no token or live run is needed. The runner has not been tested with a new live paid customer run. The underlying Actor build has separate live verification; that does not establish a destination integration.

For recurring use, call this script immediately after your existing collection workflow produces its new dataset ID. Gate downstream work on exit code 0 **and** `result.json.downstreamReady === true`. Do not schedule the fixed sample command against a historical dataset. The existing [recurring guide](recurring-documentation-checks.md) explains source completeness and accepted-baseline handling.

API references: [Run Actor](https://docs.apify.com/api/v2/actors-runs-post) and [Get Actor run](https://docs.apify.com/api/v2/actor-run-get).
