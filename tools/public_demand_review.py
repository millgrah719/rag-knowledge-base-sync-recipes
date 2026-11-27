#!/usr/bin/env python3
"""Bounded public problem discovery; optional writes only to our isolated queue branch."""
import argparse
import base64
import copy
import datetime as dt
import json
import os
from pathlib import Path
import re
import sys
import unittest
import urllib.error
import urllib.parse
import urllib.request

REPOSITORY = "millgrah719/rag-knowledge-base-sync-recipes"
QUEUE_BRANCH = "demand-review-queue"
API_ROOT = "/repos/" + REPOSITORY
REF_PATH = API_ROOT + "/git/ref/heads/" + QUEUE_BRANCH
MAX_RESPONSE_BYTES = 4_000_000
MAX_LEDGER_BYTES = 1_000_000
MAX_RECORDS = 1000
MAX_NEW_PER_RUN = 20
PER_QUERY = 15
QUERIES = (
    ("rag_duplicates", "rag", 'apify dataset duplicate in:title,body'),
    ("rag_crawler_text", "rag", '"Website Content Crawler" text in:title,body'),
    ("rag_chunks", "rag", 'RAG "duplicate chunks" in:title,body'),
    ("rag_reembedding", "rag", 'RAG "re-embedding" in:title,body'),
    ("commerce_variants", "commerce", '"JSON-LD" "product variants" in:title,body'),
    ("commerce_prices", "commerce", '"product feed" "price mismatch" in:title,body'),
)
REASONS = {
    "DUPLICATE_SOURCE_RECORDS": "rag",
    "MISSING_CRAWLER_TEXT": "rag",
    "RECORDED_SOURCE_FAILURE": "rag",
    "FULL_SNAPSHOT_REEMBEDDING": "rag",
    "SOURCE_PROVENANCE_NEEDED": "rag",
    "PRODUCT_VARIANT_NORMALIZATION": "commerce",
    "PRODUCT_PRICE_DATA_MISMATCH": "commerce",
}
STATUSES = {"needs_review", "qualified_problem", "dismissed", "resolved"}
URL_PATTERN = re.compile(r"https://github\.com/[\w.-]+/[\w.-]+/issues/[1-9][0-9]*")
SHA_PATTERN = re.compile(r"[0-9a-f]{40}")


def api(method, path, data=None, missing_ok=False):
    """Fixed-host requests, bounded replies, no automatic mutation retries."""
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "rag-demand-review/2.0",
               "X-GitHub-Api-Version": "2022-11-28"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = "Bearer " + token
    body = None if data is None else json.dumps(data).encode()
    if body is not None:
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request("https://api.github.com" + path, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            raw = response.read(MAX_RESPONSE_BYTES + 1)
    except urllib.error.HTTPError as exc:
        if missing_ok and exc.code == 404:
            return None
        raise
    if len(raw) > MAX_RESPONSE_BYTES:
        raise ValueError("GitHub response exceeds the bound")
    return json.loads(raw)


def valid_url(value):
    return isinstance(value, str) and bool(URL_PATTERN.fullmatch(value)) and value.split("/")[3].lower() != "millgrah719"


def timestamp(value):
    if not isinstance(value, str) or len(value) > 32 or not value.endswith("Z"):
        raise ValueError("Invalid queue timestamp")
    dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    return value


def empty_ledger():
    return {"schema_version": 1, "records": {}, "last_run": None}


def serialize_ledger(ledger):
    return json.dumps(ledger, indent=2, sort_keys=True) + "\n"


def validate_ledger(ledger):
    if not isinstance(ledger, dict) or ledger.get("schema_version") != 1 or set(ledger) != {"schema_version", "records", "last_run"}:
        raise ValueError("Unknown queue schema; existing state was not replaced")
    records = ledger["records"]
    if not isinstance(records, dict) or len(records) > MAX_RECORDS:
        raise ValueError("Queue exceeds the record bound")
    required = {"topic", "reason_codes", "query_ids", "first_seen_at", "last_seen_at", "source_updated_at", "review_status", "review_note"}
    for url, row in records.items():
        if not valid_url(url) or not isinstance(row, dict) or set(row) != required:
            raise ValueError("Malformed queue record; existing state was not replaced")
        if row["topic"] not in {"rag", "commerce"} or row["review_status"] not in STATUSES:
            raise ValueError("Unknown topic or review status")
        if not isinstance(row["review_note"], str) or len(row["review_note"]) > 500:
            raise ValueError("Review notes must be text of at most 500 characters")
        reasons, queries = row["reason_codes"], row["query_ids"]
        if not isinstance(reasons, list) or not reasons or len(reasons) > len(REASONS) or any(not isinstance(r, str) or REASONS.get(r) != row["topic"] for r in reasons):
            raise ValueError("Invalid problem-fit reasons")
        if not isinstance(queries, list) or not queries or len(queries) > len(QUERIES) or any(q not in {v[0] for v in QUERIES} for q in queries):
            raise ValueError("Invalid source queries")
        for field in ("first_seen_at", "last_seen_at", "source_updated_at"):
            timestamp(row[field])
    if ledger["last_run"] is not None and not isinstance(ledger["last_run"], dict):
        raise ValueError("Invalid collection metadata")
    if len(serialize_ledger(ledger).encode("utf-8")) > MAX_LEDGER_BYTES:
        raise ValueError("Queue exceeds the byte bound")
    return ledger


def classify(item, topic):
    """Technical fit only. Titles/bodies are read as data and never persisted."""
    if not isinstance(item, dict) or not valid_url(item.get("html_url")) or item.get("state") != "open" or "pull_request" in item:
        return []
    title = str(item.get("title") or "")[:500]
    labels = {str(v.get("name", "")).lower() for v in item.get("labels", []) if isinstance(v, dict)}
    if labels & {"learning-plan", "type: step", "roadmap"} or re.search(r"\b(audit|roadmap|spike|learning.plan)\b|\bW\d+-D\d", title, re.I):
        return []
    text = " ".join((title + " " + str(item.get("body") or "")[:15000]).split())
    def has(pattern):
        return bool(re.search(pattern, text, re.I))
    def near(left, right):
        return has("(?:" + left + ").{0,100}(?:" + right + ")|(?:" + right + ").{0,100}(?:" + left + ")")
    reasons = []
    if topic == "rag" and has(r"\b(rag|apify|knowledge.base)\b|website content crawler|retrieval.augmented"):
        if near(r"\bduplicat\w*", r"\b(sources?|documents?|records?|chunks?|datasets?)\b"):
            reasons.append("DUPLICATE_SOURCE_RECORDS")
        if near(r"\b(missing|empty|blank)\b", r"\b(markdown|text|content|documents?|pages?)\b"):
            reasons.append("MISSING_CRAWLER_TEXT")
        if near(r"\b([45][0-9]{2}|failed|failure|errors?)\b", r"\b(crawl\w*|source|pages?|records?)\b"):
            reasons.append("RECORDED_SOURCE_FAILURE")
        if has(r"\bre[- ]?embed\w*") and has(r"\b(full|complete|entire|whole|all documents|all chunks|all pages)\b"):
            reasons.append("FULL_SNAPSHOT_REEMBEDDING")
        if near(r"\b(missing|lost|preserve|keep|need)\b", r"source (url|metadata|link|id)|provenance"):
            reasons.append("SOURCE_PROVENANCE_NEEDED")
    elif topic == "commerce" and has(r"json.ld|product (feed|variants?|data)|offers\.price"):
        if has(r"\bvariants?\b") and has(r"\b(normaliz\w*|flatten\w*|pars\w*|extract\w*|missing|incorrect|duplicate\w*)\b"):
            reasons.append("PRODUCT_VARIANT_NORMALIZATION")
        if near(r"\bprice\b|offers\.price", r"\b(mismatch|incorrect|wrong|zero)\b|(?<!\d)0(?!\d)"):
            reasons.append("PRODUCT_PRICE_DATA_MISMATCH")
    return reasons


def collect(ledger, now, request=api):
    result = copy.deepcopy(validate_ledger(ledger))
    timestamp(now)
    since = (dt.datetime.fromisoformat(now.replace("Z", "+00:00")).date() - dt.timedelta(days=21)).isoformat()
    candidates, failures, incomplete = {}, [], []
    for query_id, topic, query in QUERIES:
        params = urllib.parse.urlencode({"q": query + " is:issue is:open is:public updated:>=" + since,
                                        "sort": "updated", "order": "desc", "per_page": PER_QUERY})
        try:
            response = request("GET", "/search/issues?" + params)
            if not isinstance(response, dict) or not isinstance(response.get("items"), list):
                raise ValueError("Invalid search response")
            if response.get("incomplete_results"):
                incomplete.append(query_id)
            for item in response["items"][:PER_QUERY]:
                reasons = classify(item, topic)
                if not reasons:
                    continue
                try:
                    updated = timestamp(item.get("updated_at"))
                except (ValueError, TypeError):
                    continue
                url = item["html_url"]
                candidate = candidates.setdefault(url, {"topic": topic, "reason_codes": [], "query_ids": [], "source_updated_at": updated})
                if candidate["topic"] == topic:
                    candidate["reason_codes"] = sorted(set(candidate["reason_codes"] + reasons))
                    candidate["query_ids"] = sorted(set(candidate["query_ids"] + [query_id]))
        except (OSError, ValueError, KeyError, TypeError):
            failures.append(query_id)
    if len(failures) == len(QUERIES):
        return result, {"failed_queries": failures, "all_failed": True}
    new_urls, changed_urls, deferred = [], [], 0
    # RAG first, then more supported reasons and newer source updates.
    ordered = sorted(candidates, key=lambda u: (len(candidates[u]["reason_codes"]), candidates[u]["source_updated_at"], u), reverse=True)
    ordered.sort(key=lambda u: candidates[u]["topic"] != "rag")
    for url in ordered:
        candidate = candidates[url]
        if url in result["records"]:
            row = result["records"][url]
            if row["source_updated_at"] != candidate["source_updated_at"]:
                changed_urls.append(url)
            if row["topic"] == candidate["topic"]:
                row["reason_codes"] = sorted(set(row["reason_codes"] + candidate["reason_codes"]))
                row["query_ids"] = sorted(set(row["query_ids"] + candidate["query_ids"]))
            row["last_seen_at"] = now
            row["source_updated_at"] = candidate["source_updated_at"]
            # Human review_status, review_note and first_seen_at are never reset.
        elif len(result["records"]) >= MAX_RECORDS or len(new_urls) >= MAX_NEW_PER_RUN:
            deferred += 1
        else:
            result["records"][url] = {**candidate, "first_seen_at": now, "last_seen_at": now,
                                      "review_status": "needs_review", "review_note": ""}
            new_urls.append(url)
    result["last_run"] = {"at": now, "new_urls": new_urls, "changed_urls": changed_urls,
                          "deferred_candidates": deferred, "failed_queries": failures,
                          "incomplete_queries": incomplete, "ledger_at_capacity": len(result["records"]) >= MAX_RECORDS}
    return validate_ledger(result), {**result["last_run"], "all_failed": False}


def render_report(ledger):
    run = ledger["last_run"] or {}
    lines = ["# Public demand review queue", "", "Technical problem-fit candidates only. No buyer, budget, Apify plan, permission to contact or revenue is inferred.", "",
             "New candidates: " + str(len(run.get("new_urls", []))) + "; source updates: " + str(len(run.get("changed_urls", []))) + ".",
             "Last collection: " + str(run.get("at", "not yet collected")) + ".",
             "Failed queries: " + (", ".join(run.get("failed_queries", [])) or "none") + ".",
             "Incomplete query results: " + (", ".join(run.get("incomplete_queries", [])) or "none") + ".",
             "Deferred candidates: " + str(run.get("deferred_candidates", 0)) + "; ledger at capacity: " + str(run.get("ledger_at_capacity", False)).lower() + ".",
             "No stored records or review decisions are evicted. The bounded sample is not exhaustive. See queue.json for the full ledger.", ""]
    new = set(run.get("new_urls", []))
    changed = set(run.get("changed_urls", []))
    for topic, heading in [("rag", "RAG preparation problems"), ("commerce", "Separate commerce data problems")]:
        rows = [(url, row) for url, row in ledger["records"].items() if row["topic"] == topic and row["review_status"] in {"needs_review", "qualified_problem"}]
        rows.sort(key=lambda pair: (pair[0] not in new, pair[0] not in changed, pair[1]["first_seen_at"], pair[0]))
        lines += ["## " + heading, "", "| Issue | Fit reasons | Review | Change | Last seen |", "|---|---|---|---|---|"]
        for url, row in rows[:50]:
            lines.append("| " + url + " | " + ", ".join(row["reason_codes"]) + " | " + row["review_status"] + " | " + ("new" if url in new else "source updated" if url in changed else "seen before") + " | " + row["last_seen_at"] + " |")
        lines += ["", str(len(rows)) + " active candidates; at most 50 shown. Dismissed/resolved records remain in queue.json.", ""]
    lines += ["Review the current issue before making a decision; an older record may have closed or changed. No comments, DMs, emails, paid calls or Actor runs are performed.", ""]
    return "\n".join(lines)


def checked_sha(value):
    if not isinstance(value, str) or not SHA_PATTERN.fullmatch(value):
        raise ValueError("Invalid Git object identity")
    return value


def read_head(request):
    ref = request("GET", REF_PATH, missing_ok=True)
    if ref is None:
        return None
    if ref.get("ref") != "refs/heads/" + QUEUE_BRANCH or ref.get("object", {}).get("type") != "commit":
        raise ValueError("Unexpected queue reference")
    return checked_sha(ref["object"]["sha"])


def load_queue(request=api):
    head = read_head(request)
    if head is None:
        return None, empty_ledger()
    commit = request("GET", API_ROOT + "/git/commits/" + head)
    tree_sha = checked_sha(commit["tree"]["sha"])
    tree = request("GET", API_ROOT + "/git/trees/" + tree_sha)
    entries = tree.get("tree", [])
    if tree.get("truncated") or len(entries) != 2 or {e.get("path") for e in entries} != {"queue.json", "report.md"} or any(e.get("type") != "blob" or e.get("mode") != "100644" for e in entries):
        raise ValueError("Queue branch must contain only regular queue.json and report.md files")
    entry = next(e for e in entries if e["path"] == "queue.json")
    if not isinstance(entry.get("size"), int) or entry["size"] > MAX_LEDGER_BYTES:
        raise ValueError("Queue blob exceeds the bound")
    blob = request("GET", API_ROOT + "/git/blobs/" + checked_sha(entry["sha"]))
    if blob.get("encoding") != "base64":
        raise ValueError("Unexpected queue blob encoding")
    raw = base64.b64decode("".join(blob["content"].split()), validate=True)
    if len(raw) > MAX_LEDGER_BYTES:
        raise ValueError("Queue blob exceeds the bound")
    return head, validate_ledger(json.loads(raw))


def require_publish_context():
    if not (os.environ.get("GITHUB_ACTIONS") == "true"
            and os.environ.get("GITHUB_REPOSITORY") == REPOSITORY
            and os.environ.get("GITHUB_REF") == "refs/heads/main"
            and os.environ.get("GITHUB_EVENT_NAME") in {"push", "schedule", "workflow_dispatch"}
            and os.environ.get("GITHUB_WORKFLOW_REF") == REPOSITORY + "/.github/workflows/integration-checks.yml@refs/heads/main"
            and os.environ.get("GITHUB_TOKEN")):
        raise ValueError("Queue publishing is restricted to the canonical main-branch workflow")
    checked_sha(os.environ.get("GITHUB_SHA"))


def publish_queue(head, ledger, report, request=api):
    require_publish_context()
    validate_ledger(ledger)
    if head is not None:
        checked_sha(head)
    if read_head(request) != head:
        raise ValueError("Queue changed during collection; no update attempted")
    contents = {"queue.json": serialize_ledger(ledger), "report.md": report}
    tree = request("POST", API_ROOT + "/git/trees", {"tree": [
        {"path": name, "mode": "100644", "type": "blob", "content": content}
        for name, content in sorted(contents.items())]})
    # A missing branch is seeded as an isolated root commit, never from main.
    commit = request("POST", API_ROOT + "/git/commits", {"message": "Update technical demand review queue",
                     "tree": checked_sha(tree["sha"]), "parents": [] if head is None else [head]})
    new_head = checked_sha(commit["sha"])
    if read_head(request) != head:
        raise ValueError("Queue changed before publishing; existing branch was preserved")
    if head is None:
        request("POST", API_ROOT + "/git/refs", {"ref": "refs/heads/" + QUEUE_BRANCH, "sha": new_head})
    else:
        request("PATCH", API_ROOT + "/git/refs/heads/" + QUEUE_BRANCH, {"sha": new_head, "force": False})
    return new_head


def self_test():
    suite = unittest.defaultTestLoader.discover(str(Path(__file__).resolve().parents[1] / "tests"), pattern="test_public_demand_review.py")
    if suite.countTestCases() == 0 or not unittest.TextTestRunner(verbosity=1).run(suite).wasSuccessful():
        raise SystemExit(1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--publish", action="store_true", help="Update only the canonical isolated queue branch, from its trusted workflow")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return
    if args.publish:
        require_publish_context()
    head, ledger = load_queue()
    now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    updated, status = collect(ledger, now)
    if status["all_failed"]:
        raise ValueError("All demand searches failed; existing queue was preserved")
    report = render_report(updated)
    if args.publish:
        publish_queue(head, updated, report)
        report += "\nPublished queue: https://github.com/" + REPOSITORY + "/blob/" + QUEUE_BRANCH + "/report.md\n"
    else:
        report += "\nRead-only preview; the canonical queue was not changed.\n"
    print(report)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as output:
            output.write(report)


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, TypeError) as error:
        print("Demand review stopped (" + type(error).__name__ + "): " + str(error), file=sys.stderr)
        sys.exit(1)

