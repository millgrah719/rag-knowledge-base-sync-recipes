"""Offline regression tests: no GitHub requests or external writes."""
import base64
import copy
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import public_demand_review as demand

NOW = "2026-11-27T12:00:00Z"
LATER = "2026-11-28T12:00:00Z"
URL = "https://github.com/example/project/issues/1"
HEAD = "a" * 40
TREE = "b" * 40
NEW_HEAD = "c" * 40
CONTEXT = {
    "GITHUB_ACTIONS": "true", "GITHUB_REPOSITORY": demand.REPOSITORY,
    "GITHUB_REF": "refs/heads/main", "GITHUB_EVENT_NAME": "schedule",
    "GITHUB_SHA": "d" * 40, "GITHUB_TOKEN": "offline-test-token",
    "GITHUB_WORKFLOW_REF": demand.REPOSITORY + "/.github/workflows/integration-checks.yml@refs/heads/main",
}


def issue(**changes):
    return {"html_url": URL, "state": "open", "title": "Apify dataset contains duplicate source records",
            "body": "How can I prepare this text for my RAG pipeline?", "labels": [], "updated_at": NOW, **changes}


def search_result(items):
    def request(method, path, **kwargs):
        assert method == "GET" and path.startswith("/search/issues?")
        return {"items": copy.deepcopy(items), "incomplete_results": False}
    return request


def populated():
    return demand.collect(demand.empty_ledger(), NOW, search_result([issue()]))[0]


class CollectionTests(unittest.TestCase):
    def test_supported_rag_problems_and_separate_commerce(self):
        cases = [
            ("Apify dataset contains duplicate source records", "DUPLICATE_SOURCE_RECORDS"),
            ("Website Content Crawler returns empty markdown text", "MISSING_CRAWLER_TEXT"),
            ("RAG source pages with HTTP 503 still reach my index", "RECORDED_SOURCE_FAILURE"),
            ("RAG re-embedding the entire corpus on every refresh", "FULL_SNAPSHOT_REEMBEDDING"),
        ]
        for title, expected in cases:
            self.assertIn(expected, demand.classify(issue(title=title, body=""), "rag"))
        commerce = issue(title="Product JSON-LD offers.price is zero: product feed price mismatch", body="")
        self.assertEqual(demand.classify(commerce, "rag"), [])
        self.assertEqual(demand.classify(commerce, "commerce"), ["PRODUCT_PRICE_DATA_MISMATCH"])

    def test_unrelated_audit_roadmap_and_learning_cards_rejected(self):
        for title, labels in [
            ("Complete engineering audit", []),
            ("Evergreen capability roadmap", []),
            ("spike(knowledge): VitePress backlinks and Vue components", []),
            ("W02-D4.1 Reject unfair comparisons", [{"name": "learning-plan"}]),
        ]:
            self.assertEqual(demand.classify(issue(title=title, labels=labels, body="RAG duplicate datasets; Tests — how to write them; recommendation"), "rag"), [])
        self.assertEqual(demand.classify(issue(title="Editorial campaign recommendation", body="need a plan"), "commerce"), [])

    def test_wrong_sources_and_closed_issues_rejected(self):
        for change in [{"state": "closed"}, {"pull_request": {}},
                       {"html_url": "https://github.com/millgrah719/project/issues/1"},
                       {"html_url": "https://example.com/issues/1"}]:
            self.assertEqual(demand.classify(issue(**change), "rag"), [])

    def test_deduplicates_queries_and_repeated_runs(self):
        first, status = demand.collect(demand.empty_ledger(), NOW, search_result([issue(), issue()]))
        self.assertEqual(list(first["records"]), [URL])
        self.assertEqual(status["new_urls"], [URL])
        again, status = demand.collect(first, LATER, search_result([issue()]))
        self.assertEqual(status["new_urls"], [])
        self.assertEqual(status["changed_urls"], [])
        self.assertEqual(again["records"][URL]["first_seen_at"], NOW)
        self.assertEqual(again["records"][URL]["last_seen_at"], LATER)

    def test_preserves_manual_disposition_and_note_on_changed_issue(self):
        for disposition in ("qualified_problem", "dismissed", "resolved"):
            ledger = populated()
            ledger["records"][URL].update(review_status=disposition, review_note="Reviewed; do not reset this decision.")
            changed, status = demand.collect(ledger, LATER, search_result([issue(updated_at=LATER)]))
            self.assertEqual(changed["records"][URL]["review_status"], disposition)
            self.assertEqual(changed["records"][URL]["review_note"], "Reviewed; do not reset this decision.")
            self.assertEqual(status["changed_urls"], [URL])

    def test_partial_search_failure_preserves_old_and_adds_available_match(self):
        ledger = populated()
        other = issue(html_url="https://github.com/example/project/issues/2")
        calls = []
        def request(method, path):
            calls.append(path)
            if len(calls) == 1:
                raise OSError("offline fixture")
            return {"items": [other]}
        updated, status = demand.collect(ledger, LATER, request)
        self.assertEqual(len(updated["records"]), 2)
        self.assertEqual(updated["records"][URL], ledger["records"][URL])
        self.assertEqual(status["failed_queries"], ["rag_duplicates"])
        self.assertFalse(status["all_failed"])

    def test_total_search_failure_keeps_exact_existing_state(self):
        ledger = populated()
        def failure(*args, **kwargs):
            raise OSError("offline fixture")
        updated, status = demand.collect(ledger, LATER, failure)
        self.assertEqual(updated, ledger)
        self.assertTrue(status["all_failed"])

    def test_capacity_never_evicts_existing_review(self):
        ledger = populated()
        ledger["records"][URL]["review_status"] = "dismissed"
        with patch.object(demand, "MAX_RECORDS", 1):
            updated, status = demand.collect(ledger, LATER, search_result([issue(html_url="https://github.com/example/project/issues/2")]))
        self.assertEqual(updated["records"], ledger["records"])
        self.assertEqual(status["new_urls"], [])
        self.assertEqual(status["deferred_candidates"], 1)
        self.assertTrue(status["ledger_at_capacity"])

    def test_search_sample_and_new_record_limits(self):
        items = [issue(html_url="https://github.com/example/project/issues/" + str(i)) for i in range(1, 40)]
        with patch.object(demand, "MAX_NEW_PER_RUN", 3):
            updated, status = demand.collect(demand.empty_ledger(), NOW, search_result(items))
        self.assertEqual(len(updated["records"]), 3)
        self.assertEqual(status["deferred_candidates"], demand.PER_QUERY - 3)

    def test_no_body_author_or_payment_classification_is_stored(self):
        body = "RAG duplicate chunks. PRIVATE_BODY_MARKER <script>alert(1)</script> I pay for Apify."
        updated, _ = demand.collect(demand.empty_ledger(), NOW, search_result([issue(body=body, user={"login": "someone"})]))
        self.assertEqual(updated["records"][URL]["review_status"], "needs_review")
        saved = json.dumps(updated) + demand.render_report(updated)
        for unwanted in ("PRIVATE_BODY_MARKER", "<script>", "someone", "I pay for Apify"):
            self.assertNotIn(unwanted, saved)


class PersistenceTests(unittest.TestCase):
    def fake_publisher(self, heads):
        calls = []
        sequence = iter(heads)
        def request(method, path, data=None, missing_ok=False):
            calls.append((method, path, data))
            if method == "GET":
                self.assertEqual(path, demand.REF_PATH)
                head = next(sequence)
                return None if head is None else {"ref": "refs/heads/" + demand.QUEUE_BRANCH, "object": {"type": "commit", "sha": head}}
            if path.endswith("/git/trees"):
                return {"sha": TREE}
            if path.endswith("/git/commits"):
                return {"sha": NEW_HEAD}
            return {}
        return request, calls

    def test_initial_seed_is_isolated_and_contains_only_two_files(self):
        request, calls = self.fake_publisher([None, None])
        ledger = populated()
        with patch.dict(os.environ, CONTEXT, clear=True):
            demand.publish_queue(None, ledger, demand.render_report(ledger), request)
        tree = next(data for method, path, data in calls if path.endswith("/git/trees"))
        self.assertEqual({entry["path"] for entry in tree["tree"]}, {"queue.json", "report.md"})
        self.assertNotIn("base_tree", tree)
        commit = next(data for method, path, data in calls if path.endswith("/git/commits"))
        self.assertEqual(commit["parents"], [])
        self.assertEqual(calls[-1], ("POST", demand.API_ROOT + "/git/refs", {"ref": "refs/heads/demand-review-queue", "sha": NEW_HEAD}))

    def test_existing_branch_update_is_fast_forward_only(self):
        request, calls = self.fake_publisher([HEAD, HEAD])
        with patch.dict(os.environ, CONTEXT, clear=True):
            demand.publish_queue(HEAD, populated(), "report", request)
        commit = next(data for method, path, data in calls if path.endswith("/git/commits"))
        self.assertEqual(commit["parents"], [HEAD])
        self.assertEqual(calls[-1], ("PATCH", demand.API_ROOT + "/git/refs/heads/demand-review-queue", {"sha": NEW_HEAD, "force": False}))

    def test_concurrent_manual_change_fails_without_updating_ref(self):
        for heads in ([NEW_HEAD], [HEAD, NEW_HEAD]):
            request, calls = self.fake_publisher(heads)
            with patch.dict(os.environ, CONTEXT, clear=True), self.assertRaisesRegex(ValueError, "Queue changed"):
                demand.publish_queue(HEAD, populated(), "report", request)
            self.assertFalse(any(method == "PATCH" or path.endswith("/git/refs") for method, path, _ in calls))

    def test_untrusted_fork_ref_event_and_workflow_cannot_publish(self):
        for key, value in [("GITHUB_REPOSITORY", "someone/fork"), ("GITHUB_REF", "refs/pull/1/merge"),
                           ("GITHUB_EVENT_NAME", "pull_request_target"), ("GITHUB_WORKFLOW_REF", "other"), ("GITHUB_TOKEN", "")]:
            with patch.dict(os.environ, {**CONTEXT, key: value}, clear=True), self.assertRaises(ValueError):
                demand.require_publish_context()

    def test_load_requires_regular_expected_files_and_preserves_ledger(self):
        ledger = populated()
        raw = json.dumps(ledger).encode()
        entries = [{"path": "queue.json", "type": "blob", "mode": "100644", "sha": "e" * 40, "size": len(raw)},
                   {"path": "report.md", "type": "blob", "mode": "100644", "sha": "f" * 40, "size": 10}]
        def request(method, path, **kwargs):
            self.assertEqual(method, "GET")
            self.assertNotIn("recursive", path)
            if path == demand.REF_PATH:
                return {"ref": "refs/heads/" + demand.QUEUE_BRANCH, "object": {"type": "commit", "sha": HEAD}}
            if "/git/commits/" in path:
                return {"tree": {"sha": TREE}}
            if "/git/trees/" in path:
                return {"tree": entries, "truncated": False}
            return {"encoding": "base64", "content": base64.b64encode(raw).decode()}
        self.assertEqual(demand.load_queue(request), (HEAD, ledger))
        entries[1]["mode"] = "120000"
        with self.assertRaisesRegex(ValueError, "regular"):
            demand.load_queue(request)

    def test_unknown_schema_is_not_silently_reset(self):
        with self.assertRaisesRegex(ValueError, "schema"):
            demand.validate_ledger({"schema_version": 2, "records": {}, "last_run": None})

    def test_byte_limit_uses_exact_published_json_including_formatting(self):
        ledger = populated()
        ledger["records"][URL]["review_note"] = "Reviewed café data."
        size = len(demand.serialize_ledger(ledger).encode("utf-8"))
        self.assertLess(len(json.dumps(ledger).encode()), size)
        with patch.object(demand, "MAX_LEDGER_BYTES", size):
            self.assertEqual(demand.validate_ledger(ledger), ledger)
        with patch.object(demand, "MAX_LEDGER_BYTES", size - 1), self.assertRaisesRegex(ValueError, "byte bound"):
            demand.validate_ledger(ledger)


if __name__ == "__main__":
    unittest.main()
