#!/usr/bin/env python3
"""Local, offline RAG document preflight. No dependencies or network requests."""
import argparse
import collections
import json
import pathlib
import sys
import unicodedata

MAX_BYTES = 6_000_000
MAX_ROWS = 500

def normalize(value):
    if not isinstance(value, str):
        return ""
    return "\n".join(line.rstrip() for line in unicodedata.normalize("NFC", value).replace("\r\n", "\n").replace("\r", "\n").split("\n")).strip()

def inspect(rows, source="url", text="auto"):
    if not isinstance(rows, list):
        raise ValueError("Expected a JSON array of document objects.")
    groups = collections.defaultdict(set)
    invalid = collections.Counter()
    duplicate = 0
    total_chars = 0
    accepted_rows = 0
    for row in rows:
        if not isinstance(row, dict):
            invalid["non-object row"] += 1
            continue
        key = row.get(source)
        if not isinstance(key, str) or not key.strip():
            invalid["missing source identifier"] += 1
            continue
        body = (normalize(row.get("markdown")) or normalize(row.get("text"))) if text == "auto" else normalize(row.get(text))
        if not body:
            invalid["missing text"] += 1
            continue
        if len(body) > 120000:
            invalid["document exceeds 120000 characters"] += 1
            continue
        accepted_rows += 1
        total_chars += len(body)
        if body in groups[key.strip()]:
            duplicate += 1
        groups[key.strip()].add(body)
    conflicts = sum(len(variants) > 1 for variants in groups.values())
    return {
        "input_rows": len(rows),
        "rows_with_source_and_text": accepted_rows,
        "duplicate_rows": duplicate,
        "conflicting_source_keys": conflicts,
        "unique_nonconflicting_sources": len(groups) - conflicts,
        "invalid_row_counts": dict(invalid),
        "total_normalized_characters": total_chars,
        "within_actor_row_limit": 0 < len(rows) <= MAX_ROWS,
        "note": "Preflight estimates only. This local tool does not implement the Actor's complete validation, chunking, snapshot comparison, or deletion safeguards.",
        "next_step": "https://apify.com/millgrah/rag-knowledge-base-sync-qa",
        "hosted_report": {
            "includes": "QA report, stable source-linked chunks, and optional snapshot-change operations",
            "price": "US$0.50 per completed non-demo report plus Apify usage; confirm the current Store price.",
            "try": "Choose Fictional demo in Apify Console. No product-event charge; platform usage may apply.",
            "paid_examples": {
                "help_center": "https://apify.com/millgrah/rag-knowledge-base-sync-qa/examples/prepare-help-center-text-for-rag",
                "data_quality": "https://apify.com/millgrah/rag-knowledge-base-sync-qa/examples/review-document-data-before-rag-indexing",
            },
        },
    }

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("file", nargs="?", type=pathlib.Path, help="Local JSON array of records")
    p.add_argument("--source-field", default="url")
    p.add_argument("--text-field", default="auto")
    p.add_argument("--demo", action="store_true", help="Use fictional records instead of a file")
    args = p.parse_args()
    if args.demo and args.file or not args.demo and args.file is None:
        p.error("Supply either a local file or --demo.")
    try:
        if args.demo:
            rows = [{"url":"https://example.com/guide","text":"How to export a report."},{"url":"https://example.com/guide","text":"How to export a report."},{"url":"https://example.com/help","text":""}]
        else:
            with args.file.open("rb") as f:
                data = f.read(MAX_BYTES + 1)
            if len(data) > MAX_BYTES:
                raise ValueError("Local preflight file exceeds 6 MB; split it into smaller batches.")
            rows = json.loads(data.decode("utf-8"))
        print(json.dumps(inspect(rows, args.source_field, args.text_field), indent=2))
    except (OSError, ValueError) as e:
        print("Preflight error: " + str(e), file=sys.stderr)
        return 1
    return 0

if __name__ == "__main__":
    sys.exit(main())
