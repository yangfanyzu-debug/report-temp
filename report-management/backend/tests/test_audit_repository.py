from __future__ import annotations

import sys
import unittest
from contextlib import contextmanager
from pathlib import Path
from typing import Any


BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.repositories.audits import MySqlAuditRepository  # noqa: E402


class RecordingCursor:
    def __init__(self, fail_on: str | None = None):
        self.executions: list[tuple[str, list[Any]]] = []
        self.fail_on = fail_on
        self.last_sql = ""
        self.lastrowid = 88
        self.rowcount = 1

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def execute(self, sql: str, params: list[Any] | None = None):
        self.last_sql = " ".join(sql.split())
        self.executions.append((self.last_sql, list(params or [])))
        if self.fail_on and self.fail_on in self.last_sql:
            raise RuntimeError("database write failed")

    def fetchone(self):
        if self.last_sql.startswith(
            "SELECT status FROM capability_report_audit WHERE id = %s FOR UPDATE"
        ):
            return {"status": getattr(self, "audit_status", "running")}
        if "SELECT id, api_key FROM capability_report_ai_config" in self.last_sql:
            return {"id": 1, "api_key": "kept-key"}
        if "SELECT id FROM capability_report_ai_config" in self.last_sql:
            return {"id": 1}
        if "COALESCE(MAX(version), 0)" in self.last_sql:
            return {"latest_version": 3}
        if "FROM capability_report_ai_config WHERE id" in self.last_sql:
            return {
                "id": 1,
                "api_url": "https://example.test/v1",
                "model_name": "new-model",
                "api_key": "kept-key",
                "create_time": None,
                "update_time": None,
            }
        return {
            "id": 88,
            "name": "修订审核提示词",
            "audit_type": "revision",
            "prompt_content": "审核内容",
            "version": 4,
            "enabled": 1,
            "create_time": None,
            "update_time": None,
        }

    def fetchall(self):
        if "FROM capability_report_audit_prompt" in self.last_sql and "FOR UPDATE" in self.last_sql:
            return [{"id": 44}]
        return []


class RecordingConnection:
    def __init__(self, cursor: RecordingCursor):
        self._cursor = cursor

    def cursor(self):
        return self._cursor


class RecordingDatabase:
    def __init__(self, fail_on: str | None = None):
        self.cursor = RecordingCursor(fail_on=fail_on)
        self.connection_object = RecordingConnection(self.cursor)
        self.commits = 0
        self.rollbacks = 0

    @contextmanager
    def connection(self):
        try:
            yield self.connection_object
            self.commits += 1
        except Exception:
            self.rollbacks += 1
            raise


class AuditClaimCursor:
    def __init__(self, update_rowcount: int = 1):
        self.update_rowcount = update_rowcount
        self.rowcount = 0
        self.last_sql = ""
        self.executions: list[tuple[str, list[Any]]] = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def execute(self, sql: str, params: list[Any] | None = None):
        self.last_sql = " ".join(sql.split())
        self.executions.append((self.last_sql, list(params or [])))
        if self.last_sql.startswith("UPDATE capability_report_audit SET status = 'running'"):
            self.rowcount = self.update_rowcount

    def fetchone(self):
        return {
            "audit_id": 99,
            "report_id": 1,
            "version_id": 10,
            "audit_type": "revision",
            "file_path": "/tmp/report.docx",
            "file_name": "report.docx",
            "systemId": "credit-card-center",
            "title": "报告",
            "report_month": "2026年08月",
        }


class AuditClaimDatabase(RecordingDatabase):
    def __init__(self, update_rowcount: int = 1):
        self.cursor = AuditClaimCursor(update_rowcount)
        self.connection_object = RecordingConnection(self.cursor)
        self.commits = 0
        self.rollbacks = 0


class AuditRepositoryTest(unittest.TestCase):
    def test_next_pending_audit_claims_with_lock_and_conditional_update(self):
        database = AuditClaimDatabase()

        job = MySqlAuditRepository(database).next_pending_audit()

        select_sql, select_params = database.cursor.executions[0]
        update_sql, update_params = database.cursor.executions[1]
        version_update_sql, version_update_params = database.cursor.executions[2]
        self.assertIn("audit.audit_type IN ('initial', 'revision')", select_sql)
        self.assertIn("audit.status = 'pending'", select_sql)
        self.assertIn("audit.status = 'running'", select_sql)
        self.assertIn("INTERVAL 10 MINUTE", select_sql)
        self.assertIn("FOR UPDATE", select_sql)
        self.assertEqual(select_params, [])
        self.assertIn("SET status = 'running'", update_sql)
        self.assertIn("status = 'pending'", update_sql)
        self.assertIn("status = 'running'", update_sql)
        self.assertIn("INTERVAL 10 MINUTE", update_sql)
        self.assertEqual(update_params, [99])
        self.assertIn("capability_report_version SET audit_status = 'running'", version_update_sql)
        self.assertEqual(version_update_params, [10])
        self.assertEqual(job["auditType"], "revision")
        self.assertEqual(database.commits, 1)
        self.assertEqual(database.rollbacks, 0)

    def test_next_pending_audit_rolls_back_when_conditional_update_loses_race(self):
        database = AuditClaimDatabase(update_rowcount=0)

        job = MySqlAuditRepository(database).next_pending_audit()

        self.assertIsNone(job)
        self.assertEqual(database.commits, 0)
        self.assertEqual(database.rollbacks, 1)

    def test_update_ai_config_preserves_empty_key(self):
        database = RecordingDatabase()
        repository = MySqlAuditRepository(database)

        config = repository.update_ai_config(
            {"apiUrl": "https://example.test/v1", "modelName": "new-model", "apiKey": ""}
        )

        update = next(sql for sql in database.cursor.executions if sql[0].startswith("UPDATE capability_report_ai_config"))
        self.assertEqual(update[1], ["https://example.test/v1", "new-model", "kept-key", 1])
        self.assertEqual(config["apiKey"], "kept-key")
        self.assertEqual(database.commits, 1)
        self.assertEqual(database.rollbacks, 0)

    def test_active_prompt_query_filters_by_audit_type(self):
        database = RecordingDatabase()
        repository = MySqlAuditRepository(database)

        prompt = repository.get_active_prompt("revision")

        statement, params = database.cursor.executions[0]
        self.assertIn("WHERE audit_type = %s AND enabled = 1", statement)
        self.assertEqual(params, ["revision"])
        self.assertEqual(prompt["auditType"], "revision")

    def test_set_audit_execution_context_builds_valid_update(self):
        database = RecordingDatabase()
        repository = MySqlAuditRepository(database)

        repository.set_audit_execution_context(
            14370,
            {"id": 7, "version": 2},
            {"modelName": "audit-model"},
        )

        lock_statement, lock_params = database.cursor.executions[0]
        statement, params = database.cursor.executions[1]
        self.assertIn("SELECT status FROM capability_report_audit", lock_statement)
        self.assertIn("FOR UPDATE", lock_statement)
        self.assertEqual(lock_params, [14370])
        self.assertIn("model_name = %s WHERE id = %s", statement)
        self.assertNotIn("model_name = %s, WHERE", statement)
        self.assertEqual(params, [7, 2, "audit-model", 14370])

    def test_set_audit_execution_context_rejects_non_running_audit(self):
        database = RecordingDatabase()
        database.cursor.audit_status = "failed"
        repository = MySqlAuditRepository(database)

        with self.assertRaisesRegex(RuntimeError, "审核任务不在运行状态"):
            repository.set_audit_execution_context(
                14370,
                {"id": 7, "version": 2},
                {"modelName": "audit-model"},
            )

        self.assertEqual(len(database.cursor.executions), 1)
        self.assertEqual(database.commits, 0)
        self.assertEqual(database.rollbacks, 1)

    def test_create_prompt_version_locks_before_calculating_and_updating_type(self):
        database = RecordingDatabase()
        repository = MySqlAuditRepository(database)

        repository.create_prompt_version("revision", {"name": "修订审核提示词", "promptContent": "新内容"})

        statements = database.cursor.executions
        self.assertIn("FROM capability_report_ai_config", statements[0][0])
        self.assertIn("FOR UPDATE", statements[0][0])
        self.assertIn("FROM capability_report_audit_prompt WHERE audit_type = %s FOR UPDATE", statements[1][0])
        self.assertEqual(statements[1][1], ["revision"])
        self.assertIn("COALESCE(MAX(version), 0)", statements[2][0])
        self.assertEqual(statements[2][1], ["revision"])
        self.assertIn("SET enabled = 0 WHERE audit_type = %s", statements[3][0])
        self.assertEqual(statements[3][1], ["revision"])
        self.assertEqual(database.commits, 1)

    def test_failed_prompt_creation_rolls_back_transaction(self):
        database = RecordingDatabase(fail_on="INSERT INTO capability_report_audit_prompt")
        repository = MySqlAuditRepository(database)

        with self.assertRaisesRegex(RuntimeError, "database write failed"):
            repository.create_prompt_version("initial", {"name": "初始审核提示词", "promptContent": "新内容"})

        self.assertEqual(database.commits, 0)
        self.assertEqual(database.rollbacks, 1)
