from __future__ import annotations

import json
from pathlib import Path
from datetime import date, datetime
from typing import Any, Protocol

from ..database import Database


class ReportRepository(Protocol):
    def list_reports(self, filters: dict[str, Any], page_num: int, page_size: int) -> dict[str, Any]:
        ...

    def get_report_detail(self, report_id: int) -> dict[str, Any] | None:
        ...

    def register_initial_report(self, payload: dict[str, Any]) -> dict[str, Any]:
        ...

    def prepare_uploaded_version(self, report_id: int) -> dict[str, Any] | None:
        ...

    def create_uploaded_version(self, payload: dict[str, Any]) -> dict[str, Any]:
        ...

    def get_version_file(self, version_id: int) -> dict[str, Any] | None:
        ...


def _json_value(value: Any) -> Any:
    if value is None or isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def _format_time(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(value, date):
        return value.strftime("%Y-%m-%d")
    return str(value)


def _summary_text(summary: Any, key: str) -> str:
    parsed = _json_value(summary)
    if isinstance(parsed, dict):
        value = parsed.get(key)
        return "" if value is None else str(value)
    return ""


class MySqlReportRepository:
    def __init__(self, database: Database):
        self.database = database

    def list_reports(self, filters: dict[str, Any], page_num: int, page_size: int) -> dict[str, Any]:
        where, params = self._build_filters(filters)
        offset = (page_num - 1) * page_size
        latest_version_join = """
            LEFT JOIN capability_report_version latest_version
              ON latest_version.report_id = report.id
             AND latest_version.version_no = (
                 SELECT MAX(inner_version.version_no)
                   FROM capability_report_version inner_version
                  WHERE inner_version.report_id = report.id
             )
        """
        latest_audit_join = """
            LEFT JOIN capability_report_audit latest_audit
              ON latest_audit.version_id = latest_version.id
             AND latest_audit.create_time = (
                 SELECT MAX(inner_audit.create_time)
                   FROM capability_report_audit inner_audit
                  WHERE inner_audit.version_id = latest_version.id
             )
        """
        with self.database.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(f"SELECT COUNT(*) AS total FROM capability_report_log report {latest_version_join} {where}", params)
                total = int(cursor.fetchone()["total"])
                cursor.execute(
                    f"""
                    SELECT
                      report.id,
                      report.systemId,
                      report.title,
                      report.report_month,
                      report.jira_id,
                      report.create_time,
                      latest_version.id AS latest_version_id,
                      latest_version.version_no AS latest_version_no,
                      latest_version.version_type AS latest_version_type,
                      latest_version.audit_status AS latest_audit_status,
                      latest_audit.id AS latest_audit_id,
                      latest_audit.summary AS latest_audit_summary
                    FROM capability_report_log report
                    {latest_version_join}
                    {latest_audit_join}
                    {where}
                    ORDER BY report.create_time DESC, report.id DESC
                    LIMIT %s OFFSET %s
                    """,
                    [*params, page_size, offset],
                )
                rows = [self._to_report_row(row) for row in cursor.fetchall()]
        return {"rows": rows, "total": total}

    def get_report_detail(self, report_id: int) -> dict[str, Any] | None:
        with self.database.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id, systemId, title, report_month, jira_id, report_data, meta_data, create_time
                      FROM capability_report_log
                     WHERE id = %s
                    """,
                    [report_id],
                )
                report = cursor.fetchone()
                if report is None:
                    return None
                cursor.execute(
                    """
                    SELECT
                      version.id,
                      version.version_no,
                      version.version_type,
                      version.file_name,
                      version.file_size,
                      version.audit_status,
                      version.uploader,
                      version.source,
                      version.create_time,
                      latest_audit.id AS latest_audit_id,
                      latest_audit.summary AS latest_audit_summary
                    FROM capability_report_version version
                    LEFT JOIN capability_report_audit latest_audit
                      ON latest_audit.version_id = version.id
                     AND latest_audit.create_time = (
                         SELECT MAX(inner_audit.create_time)
                           FROM capability_report_audit inner_audit
                          WHERE inner_audit.version_id = version.id
                     )
                    WHERE version.report_id = %s
                    ORDER BY version.version_no ASC
                    """,
                    [report_id],
                )
                versions = [self._to_version_row(row) for row in cursor.fetchall()]

        return {
            "id": report["id"],
            "systemId": report["systemId"],
            "title": report["title"],
            "reportMonth": report["report_month"],
            "jiraId": report["jira_id"],
            "reportData": _json_value(report["report_data"]),
            "metaData": _json_value(report["meta_data"]),
            "createTime": _format_time(report["create_time"]),
            "versions": versions,
        }

    def register_initial_report(self, payload: dict[str, Any]) -> dict[str, Any]:
        file_path = payload["filePath"]
        file_name = Path(file_path).name
        file_size = Path(file_path).stat().st_size if Path(file_path).is_file() else 0
        report_data = json.dumps({"data": file_path, "type": "file"}, ensure_ascii=False)
        with self.database.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO capability_report_log
                      (`systemId`, `title`, `report_month`, `report_data`, `meta_data`, `jira_id`)
                    VALUES (%s, %s, %s, %s, NULL, %s)
                    ON DUPLICATE KEY UPDATE
                      `report_data` = VALUES(`report_data`),
                      `jira_id` = VALUES(`jira_id`),
                      `id` = LAST_INSERT_ID(`id`)
                    """,
                    [payload["systemId"], payload["title"], payload["reportMonth"], report_data, payload.get("jiraId", "")],
                )
                report_id = int(cursor.lastrowid)
                cursor.execute(
                    """
                    SELECT id FROM capability_report_version
                     WHERE report_id = %s AND version_no = 1
                    """,
                    [report_id],
                )
                existing_version = cursor.fetchone()
                if existing_version:
                    version_id = int(existing_version["id"])
                    cursor.execute(
                        "UPDATE capability_report_version SET audit_status = 'pending' WHERE id = %s",
                        [version_id],
                    )
                else:
                    cursor.execute(
                        """
                        INSERT INTO capability_report_version
                          (`report_id`, `version_no`, `version_type`, `file_name`, `file_path`, `file_size`, `audit_status`, `uploader`, `source`)
                        VALUES (%s, 1, 'initial', %s, %s, %s, 'pending', '批次任务', 'batch')
                        """,
                        [report_id, file_name, file_path, file_size],
                    )
                    version_id = int(cursor.lastrowid)
                audit_id = self._create_pending_audit(cursor, report_id, version_id)
        return {"reportId": report_id, "versionId": version_id, "auditId": audit_id, "auditStatus": "pending"}

    def prepare_uploaded_version(self, report_id: int) -> dict[str, Any] | None:
        with self.database.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT report.id, report.systemId, report.title, report.report_month, COALESCE(MAX(version.version_no), 0) AS latest_version_no
                      FROM capability_report_log report
                      LEFT JOIN capability_report_version version ON version.report_id = report.id
                     WHERE report.id = %s
                     GROUP BY report.id, report.systemId, report.title, report.report_month
                    """,
                    [report_id],
                )
                row = cursor.fetchone()
        if row is None:
            return None
        return {
            "reportId": row["id"],
            "systemId": row["systemId"],
            "title": row["title"],
            "reportMonth": row["report_month"],
            "nextVersionNo": int(row["latest_version_no"]) + 1,
        }

    def create_uploaded_version(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self.database.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO capability_report_version
                      (`report_id`, `version_no`, `version_type`, `file_name`, `file_path`, `file_size`, `audit_status`, `uploader`, `source`)
                    VALUES (%s, %s, 'uploaded', %s, %s, %s, 'pending', %s, 'upload')
                    """,
                    [
                        payload["reportId"],
                        payload["versionNo"],
                        payload["fileName"],
                        payload["filePath"],
                        payload["fileSize"],
                        payload["uploader"],
                    ],
                )
                version_id = int(cursor.lastrowid)
                audit_id = self._create_pending_audit(cursor, payload["reportId"], version_id)
        return {
            "reportId": payload["reportId"],
            "versionId": version_id,
            "versionNo": payload["versionNo"],
            "auditId": audit_id,
            "auditStatus": "pending",
        }

    def get_version_file(self, version_id: int) -> dict[str, Any] | None:
        with self.database.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id, file_name, file_path
                      FROM capability_report_version
                     WHERE id = %s
                    """,
                    [version_id],
                )
                row = cursor.fetchone()
        if row is None:
            return None
        return {"id": row["id"], "fileName": row["file_name"], "filePath": row["file_path"]}

    def _build_filters(self, filters: dict[str, Any]) -> tuple[str, list[Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        if filters.get("systemId"):
            clauses.append("report.systemId LIKE %s")
            params.append(f"%{filters['systemId']}%")
        if filters.get("title"):
            clauses.append("report.title LIKE %s")
            params.append(f"%{filters['title']}%")
        if filters.get("reportMonth"):
            clauses.append("report.report_month = %s")
            params.append(filters["reportMonth"])
        if filters.get("auditStatus"):
            clauses.append("latest_version.audit_status = %s")
            params.append(filters["auditStatus"])
        return (f"WHERE {' AND '.join(clauses)}" if clauses else "", params)

    def _create_pending_audit(self, cursor: Any, report_id: int, version_id: int) -> int:
        cursor.execute(
            """
            INSERT INTO capability_report_audit
              (`report_id`, `version_id`, `status`, `summary`, `result_data`)
            VALUES (%s, %s, 'pending', NULL, NULL)
            """,
            [report_id, version_id],
        )
        audit_id = int(cursor.lastrowid)
        cursor.execute(
            """
            INSERT INTO capability_report_audit_event
              (`audit_id`, `event_type`, `phase`, `content`)
            VALUES (%s, 'system', 'queued', '报告已登记，等待AI审核')
            """,
            [audit_id],
        )
        return audit_id

    def _to_report_row(self, row: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": row["id"],
            "systemId": row["systemId"],
            "title": row["title"],
            "reportMonth": row["report_month"],
            "jiraId": row["jira_id"],
            "latestVersionId": row["latest_version_id"],
            "latestVersionNo": row["latest_version_no"],
            "latestVersionType": row["latest_version_type"],
            "latestAuditId": row["latest_audit_id"],
            "latestAuditStatus": row["latest_audit_status"] or "pending",
            "latestAuditConclusion": _summary_text(row["latest_audit_summary"], "结论"),
            "latestAuditSuggestion": _summary_text(row["latest_audit_summary"], "建议"),
            "createTime": _format_time(row["create_time"]),
        }

    def _to_version_row(self, row: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": row["id"],
            "versionNo": row["version_no"],
            "versionType": row["version_type"],
            "fileName": row["file_name"],
            "fileSize": row["file_size"],
            "auditStatus": row["audit_status"],
            "uploader": row["uploader"],
            "source": row["source"],
            "createTime": _format_time(row["create_time"]),
            "latestAuditId": row["latest_audit_id"],
            "latestAuditConclusion": _summary_text(row["latest_audit_summary"], "结论"),
        }
