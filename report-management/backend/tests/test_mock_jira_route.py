from __future__ import annotations

import sys
import unittest
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app import create_app  # noqa: E402


class MockJiraRouteTest(unittest.TestCase):
    def setUp(self):
        self.app = create_app(
            {
                "TESTING": True,
                "REPORT_REPOSITORY": object(),
                "AUDIT_REPOSITORY": object(),
            }
        )
        self.client = self.app.test_client()

    def test_create_mock_issue_matches_jira_contract(self):
        response = self.client.post(
            "/api/report-management/mock/jira",
            json={"systemId": "LMP", "title": "性能容量报告审核"},
            headers={"Idempotency-Key": "capability-report-14370"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["retCode"], 200)
        self.assertEqual(payload["retDesc"], "success")
        self.assertRegex(payload["retData"]["key"], r"^MOCK-\d{9}$")

    def test_same_idempotency_key_returns_same_issue(self):
        headers = {"Idempotency-Key": "capability-report-14370"}

        first = self.client.post(
            "/api/report-management/mock/jira",
            json={"systemId": "LMP", "title": "标题一"},
            headers=headers,
        )
        second = self.client.post(
            "/api/report-management/mock/jira",
            json={"systemId": "LMP", "title": "标题二"},
            headers=headers,
        )

        self.assertEqual(
            first.get_json()["retData"]["key"],
            second.get_json()["retData"]["key"],
        )

    def test_title_is_optional(self):
        response = self.client.post(
            "/api/report-management/mock/jira", json={"systemId": "LMP"}
        )

        self.assertEqual(response.status_code, 200)
        self.assertRegex(response.get_json()["retData"]["key"], r"^MOCK-\d{9}$")

    def test_rejects_non_object_json(self):
        response = self.client.post(
            "/api/report-management/mock/jira", json=["invalid"]
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["retCode"], 400)


if __name__ == "__main__":
    unittest.main()
