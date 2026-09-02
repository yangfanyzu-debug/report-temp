from __future__ import annotations

import re
from contextlib import contextmanager
from typing import Any, Iterator

from ..database import Database


class MySqlJiraRepository:
    WORKER_LOCK_NAME = "report-management-jira-worker"

    def __init__(self, database: Database):
        self.database = database

    @contextmanager
    def processing_lock(self) -> Iterator[bool]:
        with self.database.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT GET_LOCK(%s, 0) AS acquired",
                    [self.WORKER_LOCK_NAME],
                )
                acquired = bool(cursor.fetchone()["acquired"])
                try:
                    yield acquired
                finally:
                    if acquired:
                        cursor.execute(
                            "SELECT RELEASE_LOCK(%s)",
                            [self.WORKER_LOCK_NAME],
                        )

    def recover_interrupted_jobs(self) -> int:
        with self.database.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE capability_report_log
                       SET jira_status = 'pending',
                           jira_attempts = GREATEST(jira_attempts - 1, 0),
                           jira_error = 'JIRA任务执行中断，已自动重新排队'
                     WHERE jira_status = 'creating'
                       AND COALESCE(jira_id, '') = ''
                    """
                )
                return int(cursor.rowcount)

    def next_pending_job(self) -> dict[str, Any] | None:
        with self.database.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT report.id AS report_id, report.systemId, report.title,
                           report.report_month, report.jira_version_id, report.jira_audit_id,
                           report.jira_attempts, audit.result_text
                      FROM capability_report_log report
                      JOIN capability_report_version version
                        ON version.id = report.jira_version_id
                      JOIN capability_report_audit audit
                        ON audit.id = report.jira_audit_id
                     WHERE report.jira_status IN ('pending', 'error')
                       AND report.jira_attempts < 3
                       AND COALESCE(report.jira_id, '') = ''
                       AND audit.conclusion = 'passed'
                     ORDER BY report.id ASC
                     LIMIT 1
                     FOR UPDATE
                    """
                )
                row = cursor.fetchone()
                if row is None:
                    return None
                cursor.execute(
                    """
                    UPDATE capability_report_log
                       SET jira_status = 'creating',
                           jira_attempts = jira_attempts + 1,
                           jira_error = NULL
                     WHERE id = %s
                       AND jira_status IN ('pending', 'error')
                    """,
                    [row["report_id"]],
                )
                if cursor.rowcount != 1:
                    return None
        return {
            "reportId": row["report_id"],
            "versionId": row["jira_version_id"],
            "auditId": row["jira_audit_id"],
            "systemId": row["systemId"],
            "title": row["title"],
            "reportMonth": row["report_month"],
            "auditResult": row["result_text"],
            "jiraTitle": _extract_jira_title(row["result_text"]),
            "jiraAttempts": int(row["jira_attempts"]) + 1,
        }

    def mark_created(self, report_id: int, jira_id: str) -> None:
        with self.database.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE capability_report_log
                       SET jira_id = %s, jira_status = 'created', jira_error = NULL
                     WHERE id = %s AND jira_status = 'creating'
                    """,
                    [jira_id, report_id],
                )

    def mark_error(self, report_id: int, message: str) -> None:
        with self.database.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE capability_report_log
                       SET jira_status = 'error', jira_error = %s
                     WHERE id = %s AND jira_status = 'creating'
                    """,
                    [message[:2000], report_id],
                )


def _extract_jira_title(result_text: Any) -> str:
    match = re.search(
        r"JIRA标题\s*[：:]\s*([^\r\n]+)", str(result_text or "")[:500], re.IGNORECASE
    )
    if not match:
        return ""
    title = re.sub(r"^[`*_#\s]+|[`*_#\s]+$", "", match.group(1)).strip()
    return title[:15]
