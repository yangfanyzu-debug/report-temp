from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any, Protocol

from ..database import Database


class AuditRepository(Protocol):
    def get_audit_detail(self, audit_id: int) -> dict[str, Any] | None:
        ...

    def get_audit_events(self, audit_id: int, after_id: int = 0) -> list[dict[str, Any]]:
        ...

    def append_audit_event(self, audit_id: int, event_type: str, phase: str, content: str) -> int:
        ...

    def get_active_prompt(self) -> dict[str, Any] | None:
        ...

    def create_prompt_version(self, payload: dict[str, Any]) -> dict[str, Any]:
        ...

    def next_pending_audit(self) -> dict[str, Any] | None:
        ...

    def mark_audit_running(self, audit_id: int, prompt: dict[str, Any]) -> None:
        ...

    def mark_audit_complete(self, audit_id: int, version_id: int, result: dict[str, Any]) -> None:
        ...

    def mark_audit_error(self, audit_id: int, version_id: int, message: str) -> None:
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


def _mask_secret(value: str | None) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "****"
    return f"{value[:4]}****{value[-4:]}"


class MySqlAuditRepository:
    def __init__(self, database: Database):
        self.database = database

    def get_audit_detail(self, audit_id: int) -> dict[str, Any] | None:
        with self.database.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                      id,
                      status,
                      summary,
                      result_data,
                      prompt_id,
                      prompt_version,
                      model_name,
                      error_message,
                      started_at,
                      finished_at,
                      create_time
                    FROM capability_report_audit
                    WHERE id = %s
                    """,
                    [audit_id],
                )
                row = cursor.fetchone()
        if row is None:
            return None
        return {
            "id": row["id"],
            "status": row["status"],
            "summary": _json_value(row["summary"]),
            "resultData": _json_value(row["result_data"]),
            "promptId": row["prompt_id"],
            "promptVersion": row["prompt_version"],
            "modelName": row["model_name"],
            "errorMessage": row["error_message"],
            "startedAt": _format_time(row["started_at"]),
            "finishedAt": _format_time(row["finished_at"]),
            "createTime": _format_time(row["create_time"]),
        }

    def get_audit_events(self, audit_id: int, after_id: int = 0) -> list[dict[str, Any]]:
        with self.database.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id, event_type, phase, content, create_time
                    FROM capability_report_audit_event
                    WHERE audit_id = %s AND id > %s
                    ORDER BY id ASC
                    LIMIT 500
                    """,
                    [audit_id, after_id],
                )
                rows = cursor.fetchall()
        return [
            {
                "id": row["id"],
                "type": row["event_type"],
                "phase": row["phase"],
                "content": row["content"],
                "createTime": _format_time(row["create_time"]),
            }
            for row in rows
        ]

    def append_audit_event(self, audit_id: int, event_type: str, phase: str, content: str) -> int:
        with self.database.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO capability_report_audit_event
                      (`audit_id`, `event_type`, `phase`, `content`)
                    VALUES (%s, %s, %s, %s)
                    """,
                    [audit_id, event_type, phase, content],
                )
                return int(cursor.lastrowid)

    def get_active_prompt(self) -> dict[str, Any] | None:
        with self.database.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id, name, prompt_content, version, enabled, model_name, api_url, api_key, create_time, update_time
                    FROM capability_report_audit_prompt
                    WHERE enabled = 1
                    ORDER BY version DESC, id DESC
                    LIMIT 1
                    """
                )
                row = cursor.fetchone()
        return self._to_prompt(row) if row else None

    def create_prompt_version(self, payload: dict[str, Any]) -> dict[str, Any]:
        name = payload["name"]
        with self.database.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT api_key
                    FROM capability_report_audit_prompt
                    WHERE name = %s AND enabled = 1
                    ORDER BY version DESC, id DESC
                    LIMIT 1
                    """,
                    [name],
                )
                active_prompt = cursor.fetchone()
                api_key = payload.get("apiKey") or (active_prompt["api_key"] if active_prompt else "")
                cursor.execute(
                    """
                    SELECT COALESCE(MAX(version), 0) AS latest_version
                    FROM capability_report_audit_prompt
                    WHERE name = %s
                    """,
                    [name],
                )
                version = int(cursor.fetchone()["latest_version"]) + 1
                cursor.execute(
                    "UPDATE capability_report_audit_prompt SET enabled = 0 WHERE name = %s",
                    [name],
                )
                cursor.execute(
                    """
                    INSERT INTO capability_report_audit_prompt
                      (`name`, `prompt_content`, `version`, `enabled`, `model_name`, `api_url`, `api_key`)
                    VALUES (%s, %s, %s, 1, %s, %s, %s)
                    """,
                    [name, payload["promptContent"], version, payload["modelName"], payload["apiUrl"], api_key],
                )
                prompt_id = int(cursor.lastrowid)
                cursor.execute(
                    """
                    SELECT id, name, prompt_content, version, enabled, model_name, api_url, api_key, create_time, update_time
                    FROM capability_report_audit_prompt
                    WHERE id = %s
                    """,
                    [prompt_id],
                )
                row = cursor.fetchone()
        return self._to_prompt(row)

    def next_pending_audit(self) -> dict[str, Any] | None:
        with self.database.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                      audit.id AS audit_id,
                      audit.report_id,
                      audit.version_id,
                      version.file_path,
                      version.file_name,
                      report.systemId,
                      report.title,
                      report.report_month
                    FROM capability_report_audit audit
                    JOIN capability_report_version version ON version.id = audit.version_id
                    JOIN capability_report_log report ON report.id = audit.report_id
                    WHERE audit.status = 'pending'
                    ORDER BY audit.create_time ASC, audit.id ASC
                    LIMIT 1
                    """
                )
                row = cursor.fetchone()
        if row is None:
            return None
        return {
            "auditId": row["audit_id"],
            "reportId": row["report_id"],
            "versionId": row["version_id"],
            "filePath": row["file_path"],
            "fileName": row["file_name"],
            "systemId": row["systemId"],
            "title": row["title"],
            "reportMonth": row["report_month"],
        }

    def mark_audit_running(self, audit_id: int, prompt: dict[str, Any]) -> None:
        with self.database.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE capability_report_audit
                       SET status = 'running',
                           prompt_id = %s,
                           prompt_version = %s,
                           model_name = %s,
                           started_at = CURRENT_TIMESTAMP(3),
                           error_message = NULL
                     WHERE id = %s
                    """,
                    [prompt["id"], prompt["version"], prompt["modelName"], audit_id],
                )

    def mark_audit_complete(self, audit_id: int, version_id: int, result: dict[str, Any]) -> None:
        summary = result["summary"]
        result_data = {"data": result["data"]}
        status = "passed" if summary.get("结论") == "通过" else "failed"
        with self.database.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE capability_report_audit
                       SET status = %s,
                           summary = %s,
                           result_data = %s,
                           finished_at = CURRENT_TIMESTAMP(3),
                           error_message = NULL
                     WHERE id = %s
                    """,
                    [
                        status,
                        json.dumps(summary, ensure_ascii=False),
                        json.dumps(result_data, ensure_ascii=False),
                        audit_id,
                    ],
                )
                cursor.execute(
                    "UPDATE capability_report_version SET audit_status = %s WHERE id = %s",
                    [status, version_id],
                )

    def mark_audit_error(self, audit_id: int, version_id: int, message: str) -> None:
        with self.database.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE capability_report_audit
                       SET status = 'error',
                           error_message = %s,
                           finished_at = CURRENT_TIMESTAMP(3)
                     WHERE id = %s
                    """,
                    [message, audit_id],
                )
                cursor.execute(
                    "UPDATE capability_report_version SET audit_status = 'error' WHERE id = %s",
                    [version_id],
                )

    def _to_prompt(self, row: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": row["id"],
            "name": row["name"],
            "promptContent": row["prompt_content"],
            "version": row["version"],
            "enabled": bool(row["enabled"]),
            "modelName": row["model_name"],
            "apiUrl": row["api_url"],
            "apiKey": row["api_key"],
            "apiKeyMasked": _mask_secret(row["api_key"]),
            "apiKeyConfigured": bool(row["api_key"]),
            "createTime": _format_time(row["create_time"]),
            "updateTime": _format_time(row["update_time"]),
        }
