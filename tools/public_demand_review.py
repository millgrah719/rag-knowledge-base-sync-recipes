#!/usr/bin/env python3
"""Read-only, bounded discovery of public developer questions. No outreach or sales claims."""
import datetime as dt
import json
import os
import re
import sys
import urllib.parse
import urllib.request

QUERIES = (
    '"JSON-LD" "product variants"',
    '"product feed" "price mismatch"',
    '"RAG" "duplicate" "dataset"',
    '"RAG" "incremental" "indexing"',
)
QUESTION = re.compile(r'\b(how (?:can|do|to|should|would)|looking for|recommend(?:ation|ed)?|any (?:tool|solution|way)|need (?:a|an|to)|best (?:way|tool)|what (?:tool|approach))\b', re.I)


def search(query, since):
    # Standard GitHub Actions read-only token; no writes or credential persistence.
    params = urllib.parse.urlencode({
        "q": query + " is:issue is:open is:public updated:>=" + since,
        "sort": "updated", "order": "desc", "per_page": 15
    })
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "catalog-qa-demand-review/1.0"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = "Bearer " + token
    request = urllib.request.Request("https://api.github.com/search/issues?" + params, headers=headers)
    with urllib.request.urlopen(request, timeout=20) as response:
        data = response.read(4_000_001)
        if len(data) > 4_000_000:
            raise ValueError("Search response exceeded bound")
        return json.loads(data)


def eligible(item):
    # Review signals, not known buyers. Never retain personal details or issue bodies.
    url = item.get("html_url", "")
    if not re.fullmatch(r"https://github\.com/[\w.-]+/[\w.-]+/issues/\d+", url):
        return False
    if "/millgrah719/" in url.lower() or item.get("state") != "open":
        return False
    text = str(item.get("title", "")) + " " + str(item.get("body") or "")[:15000]
    return bool(QUESTION.search(text))


def self_test():
    item = {"state": "open", "html_url": "https://github.com/example/project/issues/1",
            "title": "Looking for a tool for product variants"}
    assert eligible(item)
    assert not eligible(dict(item, state="closed"))
    assert not eligible(dict(item, html_url="https://github.com/millgrah719/repo/issues/1"))
    assert not eligible(dict(item, html_url="https://example.com/issues/1"))
    assert not eligible(dict(item, title="Regression in version 3"))
    print("Demand-filter self-tests passed.")


def main():
    if "--self-test" in sys.argv:
        self_test()
        return
    since = (dt.datetime.now(dt.timezone.utc).date() - dt.timedelta(days=21)).isoformat()
    seen = set()
    lines = [
        "# Public demand review",
        "",
        "Read-only search of recent open GitHub questions. Results are possible technical needs, "
        "not verified prospective buyers, permission to contact, or revenue.",
        "",
    ]
    failed = 0
    for query in QUERIES:
        lines += ["## " + query, ""]
        try:
            result = search(query, since)
            matches = [i for i in result.get("items", []) if eligible(i) and i["html_url"] not in seen][:5]
            if result.get("incomplete_results"):
                lines.append("Provider returned incomplete results.")
            if not matches:
                lines.append("No qualifying new questions in returned sample.")
            for item in matches:
                url = item["html_url"]
                seen.add(url)
                # URLs only; no usernames, issue bodies, or unsanitized text.
                lines.append("- " + url + " — review actual request and repository rules before any response.")
        except (OSError, ValueError, KeyError) as exc:
            failed += 1
            lines.append("Search unavailable (" + type(exc).__name__ + "). No demand inference.")
        lines.append("")
    lines += ["---", "Unique public question links: " + str(len(seen)),
              "Unavailable queries: " + str(failed),
              "No comments, DMs, emails, purchases, or paid calls were initiated."]
    output = "\n".join(lines) + "\n"
    print(output)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as f:
            f.write(output)
    if failed == len(QUERIES):
        sys.exit(1)


if __name__ == "__main__":
    main()
