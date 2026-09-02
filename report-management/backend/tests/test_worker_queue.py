from __future__ import annotations

import inspect
import sys
import unittest
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.repositories.audits import MySqlAuditRepository  # noqa: E402
from run_worker import process_next, should_wait  # noqa: E402


class FakeWorker:
    def __init__(self, result):
        self.result = result
        self.calls = 0

    def run_once(self):
        self.calls += 1
        return self.result


class WorkerQueueTest(unittest.TestCase):
    def test_audit_jobs_take_priority_and_skip_other_workers(self):
        audit = FakeWorker({"processed": True, "kind": "audit"})
        agent = FakeWorker({"processed": True, "kind": "agent"})
        jira = FakeWorker({"processed": True, "kind": "jira"})

        result = process_next(audit, agent, jira)

        self.assertEqual(result["kind"], "audit")
        self.assertEqual((audit.calls, agent.calls, jira.calls), (1, 0, 0))

    def test_worker_waits_only_when_no_job_was_processed(self):
        self.assertFalse(should_wait({"processed": True}))
        self.assertTrue(should_wait({"processed": False}))

    def test_audit_claim_recovers_stale_running_jobs_and_syncs_version_status(self):
        source = inspect.getsource(MySqlAuditRepository.next_pending_audit)

        self.assertIn("INTERVAL 10 MINUTE", source)
        self.assertIn("audit.status = 'running'", source)
        self.assertIn("capability_report_version SET audit_status = 'running'", source)

    def test_worker_main_logs_unhandled_cycle_errors(self):
        from run_worker import main

        source = inspect.getsource(main)

        self.assertIn('logger.exception("worker_cycle_failed")', source)
        self.assertIn("time.sleep(settings.worker_interval_seconds)", source)


if __name__ == "__main__":
    unittest.main()
