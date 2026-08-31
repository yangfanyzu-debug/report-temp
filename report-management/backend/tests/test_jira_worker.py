from __future__ import annotations

import io
import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.services.jira_client import JiraClient  # noqa: E402
from app.services.jira_worker import JiraWorker  # noqa: E402


class FakeJiraRepository:
    def __init__(self, job=None):
        self.job = job
        self.created = []
        self.errors = []

    def next_pending_job(self):
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
            "auditResult": "审核结论：通过",
        }

    def test_worker_creates_jira(self):
        repository = FakeJiraRepository(self.job)
        client = FakeJiraClient()

        result = JiraWorker(repository, client).run_once()

        self.assertEqual(result["status"], "created")
        self.assertEqual(repository.created, [(1, "CAP-100")])
        self.assertEqual(repository.errors, [])

    def test_worker_keeps_job_pending_when_not_configured(self):
        repository = FakeJiraRepository(self.job)

        result = JiraWorker(repository, FakeJiraClient(configured=False)).run_once()

        self.assertEqual(result, {"processed": False, "reason": "jira_not_configured"})
        self.assertIsNotNone(repository.job)

    def test_worker_records_jira_error_without_changing_audit(self):
        repository = FakeJiraRepository(self.job)

        result = JiraWorker(
            repository, FakeJiraClient(error=RuntimeError("JIRA不可用"))
        ).run_once()

        self.assertEqual(result["status"], "error")
        self.assertEqual(repository.errors, [(1, "JIRA不可用")])

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
            jira_issue_title="性能容量报告复核任务",
            jira_api_token="",
            jira_timeout_seconds=30,
        )

        jira_id = JiraClient(settings).create_issue(self.job)

        request = urlopen.call_args.args[0]
        self.assertEqual(jira_id, "LMP-1582")
        self.assertEqual(request.headers["Idempotency-key"], "capability-report-1")
        self.assertEqual(
            json.loads(request.data.decode("utf-8")),
            {"systemId": "credit-card-center", "title": "性能容量报告复核任务"},
        )

    @patch("app.services.jira_client.urllib.request.urlopen")
    def test_client_rejects_failed_business_response(self, urlopen):
        response = io.BytesIO(
            json.dumps({"retCode": 500, "retDesc": "创建失败"}).encode()
        )
        urlopen.return_value = response
        settings = SimpleNamespace(
            jira_create_url="http://jira-api/issues",
            jira_issue_title="性能容量报告复核任务",
            jira_api_token="",
            jira_timeout_seconds=30,
        )

        with self.assertRaisesRegex(RuntimeError, "创建失败"):
            JiraClient(settings).create_issue(self.job)


if __name__ == "__main__":
    unittest.main()
