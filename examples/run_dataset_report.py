#!/usr/bin/env python3
"""Run one customer-owned dataset report, or inspect the same run without another charge."""
import argparse
import json
import os
from pathlib import Path
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

ACTOR_ID = "ttX2wguGh2oSOsfxF"
BUILD_NUMBER = "0.1.1"
BUILD_ID = "8MokcYD3PsETBwlqV"
MAX_RUN_CHARGE_USD = "0.75"
MAX_RESPONSE_BYTES = 32_000_000
ID = re.compile(r"[A-Za-z0-9]{5,80}")


class ReportError(Exception):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, newurl):
        return None


class Apify:
    def __init__(self, token):
        if not isinstance(token, str) or not token.strip() or "\n" in token or "\r" in token:
            raise ReportError("Set APIFY_TOKEN in the environment; do not put it in command arguments.")
        self.token = token.strip()
        self.opener = urllib.request.build_opener(NoRedirect())

    def request(self, method, path, payload=None, timeout=25):
        # No retries or redirects, including for the paid start. Token stays in a header.
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        request = urllib.request.Request("https://api.apify.com/v2" + path, data=body, method=method,
                  headers={"Authorization": "Bearer " + self.token, "Content-Type": "application/json"})
        try:
            with self.opener.open(request, timeout=timeout) as response:
                raw = response.read(MAX_RESPONSE_BYTES + 1)
        except urllib.error.HTTPError as error:
            raise ReportError("Apify request failed with HTTP " + str(error.code) + ". Inspect the existing run before starting again.") from None
        except (OSError, ValueError):
            raise ReportError("Apify request could not be confirmed. Inspect the existing run before starting again.") from None
        if len(raw) > MAX_RESPONSE_BYTES:
            raise ReportError("Apify response exceeded the size limit; no handoff was produced.")
        try:
            return json.loads(raw)
        except (ValueError, UnicodeError):
            raise ReportError("Apify returned an invalid JSON response; no handoff was produced.") from None


def checked_id(value, label):
    if not isinstance(value, str) or not ID.fullmatch(value):
        raise ReportError(label + " must be a real Apify ID (5–80 letters or digits), not a URL or placeholder.")
    return value


def actor_input(args):
    checked_id(args.dataset_id, "Dataset ID")
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", args.corpus_id or ""):
        raise ReportError("Corpus ID must contain 1–80 letters, digits, underscores or hyphens.")
    if not all(re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", field or "") for field in (args.source_field, args.text_field)):
        raise ReportError("Source/text fields must be valid literal top-level field names.")
    if not 250 <= args.chunk_chars <= 5000 or not 0 <= args.overlap_chars <= 800 or args.overlap_chars >= args.chunk_chars // 2:
        raise ReportError("Use 250–5000 chunk characters and 0–800 overlap, strictly below half the chunk size.")
    if not 1 <= args.wait_seconds <= 600:
        raise ReportError("Wait must be between 1 and 600 seconds.")
    if type(args.complete_snapshot) is not bool:
        raise ReportError("Complete-snapshot input must be a boolean.")
    if bool(args.start_paid_report) == bool(args.resume_run_id):
        raise ReportError("Choose --start-paid-report or --resume-run-id, never both.")
    if args.resume_run_id:
        checked_id(args.resume_run_id, "Resume run ID")
    data = {"inputMode": "dataset", "datasetId": args.dataset_id, "corpusId": args.corpus_id,
            "sourceField": args.source_field, "textField": args.text_field,
            "chunkChars": args.chunk_chars, "overlapChars": args.overlap_chars,
            "completeSnapshot": args.complete_snapshot}
    if args.previous_manifest_store_id:
        data["previousManifestStoreId"] = checked_id(args.previous_manifest_store_id, "Accepted manifest-store ID")
    return data


def write_json(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as output:
        json.dump(value, output, indent=2, ensure_ascii=False)
        output.write("\n")
    temporary.replace(path)


def run_object(response, expected_id=None):
    run = response.get("data") if isinstance(response, dict) else None
    if not isinstance(run, dict):
        raise ReportError("Apify did not return a run object. Inspect recent runs before another paid start.")
    checked_id(run.get("id"), "Returned run ID")
    if expected_id and run["id"] != expected_id:
        raise ReportError("Response belongs to another run; no handoff is allowed.")
    # Run metadata may omit the display number while queued; the immutable ID must match.
    if run.get("actId") != ACTOR_ID or run.get("buildId") != BUILD_ID or run.get("buildNumber") not in {None, BUILD_NUMBER}:
        raise ReportError("Run does not use this Actor's approved 0.1.1 build; inspect it without starting another report.")
    return run


def prepare_result(data, run, status, qa, manifest, operations):
    if not isinstance(status, dict) or status.get("status") != "COMPLETE":
        raise ReportError("Report is not COMPLETE; no operations or baseline candidate are available.")
    counters = ("inputRows", "acceptedDocuments", "duplicateRowsRemoved", "rejectedRows", "unchangedDocuments", "totalChunks", "upsertCount", "deleteCount")
    if not isinstance(qa, dict) or any(type(qa.get(k)) is not int or qa[k] < 0 for k in counters):
        raise ReportError("Malformed QA counters; no handoff is allowed.")
    if (not isinstance(qa.get("issues"), list) or len(qa["issues"]) != qa["rejectedRows"]
            or qa["acceptedDocuments"] + qa["duplicateRowsRemoved"] + qa["rejectedRows"] != qa["inputRows"]
            or qa["inputRows"] > 500 or qa["totalChunks"] > 8000 or qa["deleteCount"] > 8000
            or qa["upsertCount"] > qa["totalChunks"] or qa["totalChunks"] < qa["acceptedDocuments"]
            or qa["unchangedDocuments"] > qa["acceptedDocuments"]):
        raise ReportError("QA counts or issues disagree; no handoff is allowed.")
    expected_config = {"version": 1, "corpus": data["corpusId"], "sourceField": data["sourceField"],
                       "textField": data["textField"], "chunkChars": data["chunkChars"], "overlapChars": data["overlapChars"]}
    if (not isinstance(manifest, dict) or manifest.get("schemaVersion") != 1
            or manifest.get("config") != expected_config or not isinstance(manifest.get("documents"), dict)
            or type(manifest.get("complete")) is not bool or type(qa.get("completeSnapshot")) is not bool
            or type(status.get("baselineEligible")) is not bool or type(qa.get("deletionEnabled")) is not bool
            or manifest["complete"] != qa["completeSnapshot"]
            or (data["inputMode"] != "demo" and manifest["complete"] != status["baselineEligible"])):
        raise ReportError("Manifest/configuration and report status disagree; keep the previous baseline.")
    documents = manifest["documents"]
    if len(documents) != qa["acceptedDocuments"] or any(not isinstance(doc, dict) or not isinstance(doc.get("chunkIds"), list) for doc in documents.values()):
        raise ReportError("Manifest documents do not match QA.")
    if sum(len(doc["chunkIds"]) for doc in documents.values()) != qa["totalChunks"]:
        raise ReportError("Manifest chunk counts do not match QA.")
    if (not isinstance(operations, list) or len(operations) > 16000
            or len(operations) != qa["upsertCount"] + qa["deleteCount"]
            or status.get("operationCount") != len(operations)):
        raise ReportError("Incomplete or inconsistent operation list; no handoff is allowed.")
    seen, upserts, deletes = set(), [], []
    for operation in operations:
        if not isinstance(operation, dict) or operation.get("operation") not in {"UPSERT", "DELETE"}:
            raise ReportError("Unexpected chunk operation.")
        chunk_id, source = operation.get("chunkId"), operation.get("source")
        if not isinstance(chunk_id, str) or not chunk_id.strip() or chunk_id in seen or not isinstance(source, str) or not source.strip() or operation.get("corpusId") != data["corpusId"]:
            raise ReportError("Malformed, duplicate or foreign-corpus operation.")
        seen.add(chunk_id)
        if operation["operation"] == "UPSERT":
            if not isinstance(operation.get("text"), str) or not operation["text"].strip() or source not in documents or chunk_id not in documents[source]["chunkIds"]:
                raise ReportError("UPSERT text or manifest membership is invalid.")
            upserts.append(operation)
        else:
            deletes.append(operation)
    if len(upserts) != qa["upsertCount"] or len(deletes) != qa["deleteCount"]:
        raise ReportError("Operation types do not match QA counts.")
    if deletes and not (qa["deletionEnabled"] and manifest["complete"] and data.get("previousManifestStoreId")):
        raise ReportError("DELETE suggestions are not eligible; keep the previous baseline.")
    reasons = []
    if data["inputMode"] != "dataset":
        reasons.append("Only customer dataset reports are eligible; demo data is review-only.")
    if data.get("completeSnapshot") is not True or not manifest["complete"] or not status["baselineEligible"]:
        reasons.append("Automatic handoff requires an explicitly confirmed full snapshot and eligible manifest.")
    if qa["rejectedRows"] or qa["issues"] or qa["acceptedDocuments"] == 0:
        reasons.append("QA rejected records or accepted no documents.")
    for record in (qa, status):
        if not (record.get("downstreamReady") is True and record.get("approvalStatus") == "READY"
                and record.get("approvalReasons") == [] and record.get("approvalScope") == "SUPPLIED_RECORDS_ONLY"):
            reasons.append("Matching explicit Actor approval is missing or withheld.")
            break
    ready = not reasons
    return {"runId": run["id"], "storeId": run["defaultKeyValueStoreId"], "sourceDatasetId": data["datasetId"],
            "reportComplete": True, "downstreamReady": ready, "blockedReasons": reasons,
            "qa": qa, "manifest": manifest, "upserts": upserts if ready else [], "deleteSuggestions": deletes if ready else [],
            "review": {"operations": operations, "note": "Inspection only; never connect this review object to a destination."},
            "baseline": {"previousManifestStoreId": data.get("previousManifestStoreId"),
                         "candidateManifestStoreId": run["defaultKeyValueStoreId"] if ready else None,
                         "updated": False, "commitAllowed": False, "requiresDestinationAcknowledgement": True}}


def execute(args, client, clock=time.monotonic, pause=time.sleep):
    data = actor_input(args)  # Validate everything before a request or new paid run.
    directory = Path(args.output_dir)
    try:
        directory.mkdir(mode=0o700, parents=True, exist_ok=False)
    except FileExistsError:
        raise ReportError("Output directory already exists. Inspect its run.json; resume that run into a new directory instead of starting again.") from None
    receipt = {"actorId": ACTOR_ID, "buildNumber": BUILD_NUMBER, "maxRunChargeUsd": MAX_RUN_CHARGE_USD,
               "input": data, "runId": args.resume_run_id, "status": "RESUMING" if args.resume_run_id else "START_UNCONFIRMED"}
    receipt_path = directory / "run.json"
    write_json(receipt_path, receipt)
    if args.resume_run_id:
        run = run_object(client.request("GET", "/actor-runs/" + args.resume_run_id), args.resume_run_id)
    else:
        query = urllib.parse.urlencode({"build": BUILD_NUMBER, "memory": 256, "timeout": 90,
                 "maxTotalChargeUsd": MAX_RUN_CHARGE_USD, "waitForFinish": 0, "restartOnError": "false"})
        # Exactly one POST. A lost response is ambiguous; there is no automatic retry.
        response = client.request("POST", "/actors/" + ACTOR_ID + "/runs?" + query, data)
        if isinstance(response, dict) and isinstance(response.get("data"), dict):
            candidate_id = response["data"].get("id")
            if isinstance(candidate_id, str) and ID.fullmatch(candidate_id):
                receipt["runId"] = candidate_id
                write_json(receipt_path, receipt)
        run = run_object(response)
    receipt.update(runId=run["id"], status=run.get("status"))
    write_json(receipt_path, receipt)
    print("Run ID: " + run["id"] + ". Saved recovery receipt: " + str(receipt_path), file=sys.stderr)
    deadline = clock() + args.wait_seconds
    while run.get("status") in {"READY", "RUNNING"}:
        remaining = deadline - clock()
        if remaining <= 0:
            raise ReportError("Bounded wait expired. Resume run " + run["id"] + "; do not repeat the paid start.")
        wait = max(0, min(20, int(remaining) - 1))
        response = client.request("GET", "/actor-runs/" + run["id"] + "?waitForFinish=" + str(wait), timeout=min(25, remaining))
        run = run_object(response, run["id"])
        receipt["status"] = run.get("status")
        write_json(receipt_path, receipt)
        if run.get("status") in {"READY", "RUNNING"}:
            pause(min(1, max(0, deadline - clock())))
    if run.get("status") != "SUCCEEDED":
        raise ReportError("Run " + run["id"] + " did not succeed. Inspect it before another paid start.")
    store_id = checked_id(run.get("defaultKeyValueStoreId"), "Output store ID")
    dataset_id = checked_id(run.get("defaultDatasetId"), "Output dataset ID")
    prefix = "/key-value-stores/" + store_id + "/records/"
    stored_input = client.request("GET", prefix + "INPUT")
    if not isinstance(stored_input, dict) or any(stored_input.get(k) != v for k, v in data.items()) or stored_input.get("previousManifestStoreId") != data.get("previousManifestStoreId"):
        raise ReportError("Saved run INPUT differs from these arguments; no handoff is allowed.")
    status = client.request("GET", prefix + "SYNC_STATUS")
    qa = client.request("GET", prefix + "QA")
    manifest = client.request("GET", prefix + "MANIFEST")
    operations = client.request("GET", "/datasets/" + dataset_id + "/items?format=json&limit=16001")
    result = prepare_result(data, run, status, qa, manifest, operations)
    write_json(directory / "result.json", result)
    return result


class Parser(argparse.ArgumentParser):
    def error(self, message):
        self.print_usage(sys.stderr)
        self.exit(1, "Input error: " + message + "\n")


def main(argv=None):
    parser = Parser(description="Paid customer dataset report: US$0.50 per completed report plus usage; maximum run charge US$0.75. No destination writes.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--start-paid-report", action="store_true", help="Explicitly authorize one report start; never automatically retried")
    mode.add_argument("--resume-run-id", help="Read/wait for the same run; starts no new report")
    parser.add_argument("--dataset-id", required=True, help="The actual fresh snapshot dataset ID from your existing workflow")
    parser.add_argument("--corpus-id", required=True)
    parser.add_argument("--output-dir", required=True, help="A new local directory; existing directories are refused")
    parser.add_argument("--complete-snapshot", action="store_true", help="Assert the input is the entire authoritative corpus, not a partial batch")
    parser.add_argument("--previous-manifest-store-id", help="Only a full baseline your destination already accepted")
    parser.add_argument("--source-field", default="url")
    parser.add_argument("--text-field", default="auto")
    parser.add_argument("--chunk-chars", type=int, default=1800)
    parser.add_argument("--overlap-chars", type=int, default=150)
    parser.add_argument("--wait-seconds", type=int, default=180)
    args = parser.parse_args(argv)
    try:
        actor_input(args)
        result = execute(args, Apify(os.environ.get("APIFY_TOKEN")))
        print(json.dumps({"runId": result["runId"], "downstreamReady": result["downstreamReady"], "resultFile": str(Path(args.output_dir) / "result.json")}))
        return 0 if result["downstreamReady"] else 2
    except (ReportError, OSError) as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
