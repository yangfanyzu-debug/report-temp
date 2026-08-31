from __future__ import annotations

import re
from typing import Any

from ..database import Database


class MySqlJiraRepository:
    def __init__(self, database: Database):
        self.database = database

    def next_pending_job(self) -> dict[str, Any] | None:
        with self.database.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT report.id AS report_id, report.systemId, report.title,
                           report.report_month, report.jira_version_id, report.jira_audit_id,
                           audit.result_text
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
