from __future__ import annotations

import io
import json
import sys
import unittest
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch


BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.services.jira_client import JiraClient  # noqa: E402
from app.services.jira_worker import JiraWorker  # noqa: E402
from app.repositories.jira import MySqlJiraRepository, _extract_jira_title  # noqa: E402


class FakeJiraRepository:
    def __init__(self, job=None, lock_acquired=True):
        self.job = job
        self.lock_acquired = lock_acquired
        self.created = []
        self.errors = []
        self.calls = []

    @contextmanager
    def processing_lock(self):
        self.calls.append("lock")
        yield self.lock_acquired

    def recover_interrupted_jobs(self):
        self.calls.append("recover")
        return 0

    def next_pending_job(self):
        self.calls.append("next")
        job, self.job = self.job, None
        return job

    def mark_created(self, report_id, jira_id):
        self.created.append((report_id, jira_id))

    def mark_error(self, report_id, message):
        self.errors.append((report_id, message))


class FakeJiraClient:
    def __init__(self, configured=True, jira_id="CAP-100", error=None):
        self.configured = configured
        self.jira_id = jira_id
        self.error = error
        self.jobs = []

    def create_issue(self, job):
        self.jobs.append(job)
        if self.error:
            raise self.error
        return self.jira_id


class JiraWorkerTest(unittest.TestCase):
    def setUp(self):
        self.job = {
            "reportId": 1,
            "versionId": 9,
            "auditId": 88,
            "systemId": "credit-card-center",
            "title": "容量报告",
            "reportMonth": "2026年08月",
            "auditResult": "审核结论：通过\nJIRA标题：信用卡容量审核通过",
            "jiraTitle": "信用卡容量审核通过",
        }

    def test_worker_creates_jira(self):
        repository = FakeJiraRepository(self.job)
        client = FakeJiraClient()

        result = JiraWorker(repository, client).run_once()

        self.assertEqual(result["status"], "created")
        self.assertEqual(repository.created, [(1, "CAP-100")])
        self.assertEqual(repository.errors, [])
        self.assertEqual(repository.calls, ["lock", "recover", "next"])

    def test_worker_keeps_job_pending_when_not_configured(self):
        repository = FakeJiraRepository(self.job)

        result = JiraWorker(repository, FakeJiraClient(configured=False)).run_once()

        self.assertEqual(result, {"processed": False, "reason": "jira_not_configured"})
        self.assertIsNotNone(repository.job)
        self.assertEqual(repository.calls, [])

    def test_worker_does_not_consume_jira_jobs_in_batch_debug_mode(self):
        repository = FakeJiraRepository(self.job)

        result = JiraWorker(repository, FakeJiraClient(), enabled=False).run_once()

        self.assertEqual(
            result,
            {"processed": False, "reason": "jira_disabled_in_batch_debug_mode"},
        )
        self.assertIsNotNone(repository.job)
        self.assertEqual(repository.calls, [])

    def test_worker_skips_recovery_and_claim_when_lock_is_busy(self):
        repository = FakeJiraRepository(self.job, lock_acquired=False)

        result = JiraWorker(repository, FakeJiraClient()).run_once()

        self.assertEqual(result, {"processed": False, "reason": "jira_worker_busy"})
        self.assertEqual(repository.calls, ["lock"])
        self.assertIsNotNone(repository.job)

    def test_worker_records_jira_error_without_changing_audit(self):
        repository = FakeJiraRepository(self.job)

        result = JiraWorker(
            repository, FakeJiraClient(error=RuntimeError("JIRA不可用"))
        ).run_once()

        self.assertEqual(result["status"], "error")
        self.assertEqual(repository.errors, [(1, "JIRA不可用")])

    def test_repository_lock_is_released_and_interrupted_jobs_are_requeued(self):
        cursor = MagicMock()
        cursor.fetchone.return_value = {"acquired": 1}
        cursor.rowcount = 2
        connection = MagicMock()
        connection.cursor.return_value.__enter__.return_value = cursor
        database = MagicMock()

        @contextmanager
        def database_connection():
            yield connection

        database.connection.side_effect = database_connection
        repository = MySqlJiraRepository(database)

        with repository.processing_lock() as acquired:
            self.assertTrue(acquired)
        recovered = repository.recover_interrupted_jobs()

        statements = [" ".join(call.args[0].split()) for call in cursor.execute.call_args_list]
        self.assertTrue(statements[0].startswith("SELECT GET_LOCK"))
        self.assertTrue(statements[1].startswith("SELECT RELEASE_LOCK"))
        self.assertIn("jira_status = 'pending'", statements[2])
        self.assertIn("jira_attempts = GREATEST(jira_attempts - 1, 0)", statements[2])
        self.assertEqual(recovered, 2)

    @patch("app.services.jira_client.urllib.request.urlopen")
    def test_client_uses_internal_api_contract(self, urlopen):
        response = io.BytesIO(
            json.dumps(
                {
                    "retCode": 200,
                    "retData": {"id": "2377340", "key": "LMP-1582"},
                    "retDesc": "success",
                }
            ).encode()
        )
        urlopen.return_value = response
        settings = SimpleNamespace(
            jira_create_url="http://10.2.64.36:9212/osenv/cap/confirm/jira",
            jira_timeout_seconds=30,
        )

        jira_id = JiraClient(settings).create_issue(self.job)

        request = urlopen.call_args.args[0]
        self.assertEqual(jira_id, "LMP-1582")
        self.assertEqual(request.headers["Idempotency-key"], "capability-report-1")
        self.assertEqual(
            json.loads(request.data.decode("utf-8")),
            {"systemId": "credit-card-center", "title": "信用卡容量审核通过"},
        )
        self.assertIsNone(request.get_header("Authorization"))

    @patch("app.services.jira_client.urllib.request.urlopen")
    def test_client_rejects_failed_business_response(self, urlopen):
        response = io.BytesIO(
            json.dumps({"retCode": 500, "retDesc": "创建失败"}).encode()
        )
        urlopen.return_value = response
        settings = SimpleNamespace(
            jira_create_url="http://jira-api/issues",
            jira_timeout_seconds=30,
        )

        with self.assertRaisesRegex(RuntimeError, "创建失败"):
            JiraClient(settings).create_issue(self.job)

    def test_extracts_ai_generated_title_from_audit_result(self):
        title = _extract_jira_title(
            "审核结论：通过\nJIRA标题：信用卡中心容量审核通过\n\n## 审核总结"
        )

        self.assertEqual(title, "信用卡中心容量审核通过")

    def test_extracts_ai_generated_title_after_long_audit_result(self):
        title = _extract_jira_title(
            "## 审核总结\n" + "报告内容正常。" * 100 + "\n"
            "JIRA标题：容量报告初审通过\n"
            "审核结论：通过"
        )

        self.assertEqual(title, "容量报告初审通过")

    @patch("app.services.jira_client.urllib.request.urlopen")
    def test_client_uses_api_default_when_ai_title_is_missing(self, urlopen):
        urlopen.return_value = io.BytesIO(
            json.dumps(
                {"retCode": 200, "retData": {"key": "LMP-1583"}, "retDesc": "success"}
            ).encode()
        )
        settings = SimpleNamespace(
            jira_create_url="http://jira-api/issues",
            jira_timeout_seconds=30,
        )
        job = {**self.job, "jiraTitle": ""}

        jira_id = JiraClient(settings).create_issue(job)

        request = urlopen.call_args.args[0]
        self.assertEqual(jira_id, "LMP-1583")
        self.assertEqual(
            json.loads(request.data.decode("utf-8")),
            {"systemId": "credit-card-center"},
        )


if __name__ == "__main__":
    unittest.main()
