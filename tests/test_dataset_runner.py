"""Customer runner checks with fictional outputs and a fake API; no network or charges."""
import argparse
import contextlib
import copy
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock
import urllib.error

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "examples"))
import run_dataset_report as runner

RUN_ID = "ExampleRun12345"
STORE_ID = "ExampleStore123"
OUTPUT_ID = "OutputDataset123"
SOURCE = "https://example.com/guide"


def arguments(directory, **changes):
    return argparse.Namespace(dataset_id="FreshDataset123", corpus_id="help-center", output_dir=str(directory),
        complete_snapshot=True, previous_manifest_store_id=None, source_field="url", text_field="auto",
        chunk_chars=1800, overlap_chars=150, wait_seconds=5, start_paid_report=True, resume_run_id=None, **changes)


def fixture(data):
    run = {"id": RUN_ID, "actId": runner.ACTOR_ID, "buildId": runner.BUILD_ID, "buildNumber": runner.BUILD_NUMBER,
           "status": "SUCCEEDED", "defaultKeyValueStoreId": STORE_ID, "defaultDatasetId": OUTPUT_ID}
    approval = {"downstreamReady": True, "approvalStatus": "READY", "approvalReasons": [], "approvalScope": "SUPPLIED_RECORDS_ONLY"}
    qa = {"inputRows": 1, "acceptedDocuments": 1, "duplicateRowsRemoved": 0, "rejectedRows": 0,
          "unchangedDocuments": 0, "totalChunks": 1, "upsertCount": 1, "deleteCount": 0,
          "issues": [], "completeSnapshot": True, "deletionEnabled": False, **approval}
    status = {"status": "COMPLETE", "baselineEligible": True, "operationCount": 1, **approval}
    manifest = {"schemaVersion": 1, "complete": True, "config": {"version": 1, "corpus": data["corpusId"],
                "sourceField": data["sourceField"], "textField": data["textField"], "chunkChars": 1800, "overlapChars": 150},
                "documents": {SOURCE: {"contentHash": "a" * 64, "chunkIds": ["chunk-one"]}}}
    operations = [{"operation": "UPSERT", "chunkId": "chunk-one", "source": SOURCE, "corpusId": data["corpusId"],
                   "text": "Fictional documentation text supplied by the customer."}]
    return run, status, qa, manifest, operations


class FakeApi:
    def __init__(self, data):
        self.data = copy.deepcopy(data)
        self.run, status, qa, manifest, self.operations = fixture(data)
        self.records = {"INPUT": self.data, "SYNC_STATUS": status, "QA": qa, "MANIFEST": manifest}
        self.calls = []

    def request(self, method, path, payload=None, timeout=25):
        self.calls.append((method, path, payload))
        if method == "POST" or path.startswith("/actor-runs/"):
            return {"data": copy.deepcopy(self.run)}
        if "/records/" in path:
            return copy.deepcopy(self.records[path.rsplit("/", 1)[-1]])
        if path.startswith("/datasets/"):
            return copy.deepcopy(self.operations)
        raise AssertionError("Unexpected API call")


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name) / "report"
        self.args = arguments(self.directory)
        self.data = runner.actor_input(self.args)

    def execute(self, args, api, **kwargs):
        with contextlib.redirect_stderr(io.StringIO()):
            return runner.execute(args, api, **kwargs)

    def test_paid_start_is_explicit_pinned_capped_and_baseline_never_committed(self):
        api = FakeApi(self.data)
        result = self.execute(self.args, api)
        posts = [call for call in api.calls if call[0] == "POST"]
        self.assertEqual(len(posts), 1)
        for parameter in ("build=0.1.1", "maxTotalChargeUsd=0.75", "restartOnError=false"):
            self.assertIn(parameter, posts[0][1])
        self.assertTrue(result["downstreamReady"])
        self.assertEqual(len(result["upserts"]), 1)
        self.assertFalse(result["baseline"]["updated"])
        self.assertFalse(result["baseline"]["commitAllowed"])
        self.assertEqual(result["baseline"]["candidateManifestStoreId"], STORE_ID)
        self.assertEqual({p.name for p in self.directory.iterdir()}, {"run.json", "result.json"})

    def test_start_failure_is_never_retried_and_keeps_uncertain_receipt(self):
        api = Mock()
        api.request.side_effect = runner.ReportError("Start response could not be confirmed")
        with self.assertRaises(runner.ReportError):
            self.execute(self.args, api)
        self.assertEqual(api.request.call_count, 1)
        self.assertEqual(api.request.call_args.args[0], "POST")
        receipt = json.loads((self.directory / "run.json").read_text())
        self.assertIsNone(receipt["runId"])
        self.assertEqual(receipt["status"], "START_UNCONFIRMED")
        self.assertFalse((self.directory / "result.json").exists())

    def test_receipt_reuse_refuses_second_start_and_resume_only_reads(self):
        api = FakeApi(self.data)
        self.execute(self.args, api)
        before = len(api.calls)
        with self.assertRaisesRegex(runner.ReportError, "already exists"):
            self.execute(self.args, api)
        self.assertEqual(len(api.calls), before)
        self.assertEqual(json.loads((self.directory / "run.json").read_text())["runId"], RUN_ID)
        resumed = copy.copy(self.args)
        resumed.start_paid_report = False
        resumed.resume_run_id = RUN_ID
        resumed.output_dir = str(Path(self.temp.name) / "resumed")
        reads = FakeApi(self.data)
        self.assertTrue(self.execute(resumed, reads)["downstreamReady"])
        self.assertTrue(all(call[0] == "GET" for call in reads.calls))

    def test_invalid_inputs_fail_before_any_network(self):
        for field, value in [("dataset_id", "YOUR_DATASET_ID"), ("corpus_id", "not valid"), ("wait_seconds", 0),
                             ("overlap_chars", 900), ("complete_snapshot", "true"), ("start_paid_report", False),
                             ("resume_run_id", RUN_ID)]:
            args = copy.copy(self.args)
            setattr(args, field, value)
            api = Mock()
            with self.assertRaises(runner.ReportError):
                self.execute(args, api)
            api.request.assert_not_called()
        self.assertFalse(self.directory.exists())

    def test_partial_even_with_ready_flags_has_no_automatic_operations(self):
        self.args.complete_snapshot = False
        data = runner.actor_input(self.args)
        api = FakeApi(data)
        api.records["QA"]["completeSnapshot"] = False
        api.records["MANIFEST"]["complete"] = False
        api.records["SYNC_STATUS"]["baselineEligible"] = False
        result = self.execute(self.args, api)
        self.assertFalse(result["downstreamReady"])
        self.assertEqual(result["upserts"], [])
        self.assertEqual(result["deleteSuggestions"], [])
        self.assertIsNone(result["baseline"]["candidateManifestStoreId"])
        self.assertEqual(len(result["review"]["operations"]), 1)

    def test_rejected_record_blocks_valid_remaining_chunks(self):
        api = FakeApi(self.data)
        api.records["QA"].update(inputRows=2, rejectedRows=1, issues=[{"row": 1, "reason": "RECORDED_HTTP_FAILURE"}],
                                 completeSnapshot=False, downstreamReady=False, approvalStatus="BLOCKED")
        api.records["MANIFEST"]["complete"] = False
        api.records["SYNC_STATUS"].update(baselineEligible=False, downstreamReady=False, approvalStatus="BLOCKED")
        result = self.execute(self.args, api)
        self.assertFalse(result["downstreamReady"])
        self.assertEqual(result["upserts"], [])

    def test_demo_cannot_produce_handoff_even_with_ready_flags(self):
        data = {**self.data, "inputMode": "demo", "corpusId": "demo"}
        run, status, qa, manifest, operations = fixture(data)
        status["baselineEligible"] = False
        result = runner.prepare_result(data, run, status, qa, manifest, operations)
        self.assertFalse(result["downstreamReady"])
        self.assertEqual(result["upserts"], [])

    def test_legacy_or_withheld_approval_blocks_handoff(self):
        for change in ({"downstreamReady": False}, {"approvalScope": "UNKNOWN"}, {"approvalReasons": ["REVIEW_REQUIRED"]}):
            run, status, qa, manifest, operations = fixture(self.data)
            qa.update(change)
            result = runner.prepare_result(self.data, run, status, qa, manifest, operations)
            self.assertFalse(result["downstreamReady"])
            self.assertEqual(result["upserts"], [])

    def test_incomplete_report_or_truncated_operations_fail_closed(self):
        for change in ("incomplete", "truncated", "foreign"):
            run, status, qa, manifest, operations = fixture(self.data)
            if change == "incomplete":
                status["status"] = "OUTPUT_READY"
            elif change == "truncated":
                operations.clear()
            else:
                operations[0]["corpusId"] = "another-corpus"
            with self.assertRaises(runner.ReportError):
                runner.prepare_result(self.data, run, status, qa, manifest, operations)

    def test_resume_checks_actor_build_and_exact_saved_input(self):
        for change in ("actor", "build", "input"):
            args = copy.copy(self.args)
            args.start_paid_report = False
            args.resume_run_id = RUN_ID
            args.output_dir = str(Path(self.temp.name) / change)
            api = FakeApi(self.data)
            if change == "actor":
                api.run["actId"] = "DifferentActor123"
            elif change == "build":
                api.run["buildId"] = "DifferentBuild123"
            else:
                api.records["INPUT"]["datasetId"] = "DifferentDataset123"
            with self.assertRaises(runner.ReportError):
                self.execute(args, api)
            self.assertTrue(all(call[0] == "GET" for call in api.calls))
            self.assertFalse((Path(args.output_dir) / "result.json").exists())

    def test_wait_is_bounded_and_receipt_retains_same_run(self):
        api = FakeApi(self.data)
        api.run["status"] = "RUNNING"
        api.run["buildNumber"] = None
        current = [0.0]
        def clock():
            return current[0]
        def pause(seconds):
            current[0] += seconds
        with self.assertRaisesRegex(runner.ReportError, "Bounded wait"):
            self.execute(self.args, api, clock=clock, pause=pause)
        self.assertLessEqual(current[0], self.args.wait_seconds)
        self.assertEqual(sum(method == "POST" for method, _, _ in api.calls), 1)
        self.assertTrue(all(RUN_ID in path for method, path, _ in api.calls if method == "GET"))
        self.assertEqual(json.loads((self.directory / "run.json").read_text())["runId"], RUN_ID)

    def test_unchanged_approved_snapshot_can_have_zero_operations(self):
        run, status, qa, manifest, operations = fixture(self.data)
        qa.update(unchangedDocuments=1, upsertCount=0)
        status["operationCount"] = 0
        result = runner.prepare_result(self.data, run, status, qa, manifest, [])
        self.assertTrue(result["downstreamReady"])
        self.assertEqual(result["upserts"], [])

    def test_transport_keeps_token_out_of_errors_and_refuses_redirects(self):
        secret = "test-secret-token"
        client = runner.Apify(secret)
        client.opener = Mock()
        for failure in (urllib.error.HTTPError("https://api.apify.com/v2/test", 403, secret, {}, None), urllib.error.URLError(secret)):
            client.opener.open.side_effect = failure
            with self.assertRaises(runner.ReportError) as raised:
                client.request("POST", "/test", {})
            self.assertNotIn(secret, str(raised.exception))
        self.assertIsNone(runner.NoRedirect().redirect_request(None, None, 307, "redirect", {}, "https://example.com"))
        with self.assertRaises(runner.ReportError):
            runner.Apify(None)


if __name__ == "__main__":
    unittest.main()
