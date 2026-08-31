from __future__ import annotations

import re
import unittest
from pathlib import Path


REPORT_MANAGEMENT_DIR = Path(__file__).resolve().parents[2]
MIGRATION = REPORT_MANAGEMENT_DIR / "db/migrations/007_report_workflow.sql"


class ReportWorkflowMigrationContractTest(unittest.TestCase):
    def test_migration_adds_idempotency_jira_and_finalization_fields(self):
        sql = MIGRATION.read_text(encoding="utf-8")

        for field in (
            "generation_id",
            "final_version_id",
            "finalized_at",
            "finalized_by",
            "jira_status",
            "jira_error",
            "jira_attempts",
            "jira_version_id",
            "jira_audit_id",
        ):
            self.assertIn(field, sql)
        self.assertIn("uk_report_generation", sql)
        self.assertIn("idx_jira_status", sql)

    def test_migration_is_additive_and_idempotent(self):
        sql = MIGRATION.read_text(encoding="utf-8")

        self.assertIn("information_schema.columns", sql)
        self.assertIn("information_schema.statistics", sql)
        self.assertNotRegex(sql.upper(), r"DROP\s+TABLE")
        self.assertNotRegex(sql.upper(), r"DROP\s+COLUMN")
        self.assertNotRegex(sql.upper(), r"\bTRUNCATE\b")
        self.assertIsNone(re.search(r"DELETE\s+FROM\s+CAPABILITY_REPORT", sql, re.IGNORECASE))


if __name__ == "__main__":
    unittest.main()
