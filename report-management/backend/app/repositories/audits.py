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

    def list_checkpoints(self) -> list[dict[str, Any]]:
        ...

    def get_active_checkpoints(self) -> list[dict[str, Any]]:
        ...

    def create_checkpoint(self, payload: dict[str, Any]) -> dict[str, Any]:
        ...

    def update_checkpoint(self, checkpoint_id: int, payload: dict[str, Any]) -> dict[str, Any] | None:
        ...

    def save_checkpoint_snapshot(self, audit_id: int, checkpoints: list[dict[str, Any]]) -> None:
        ...

    def get_report_conversation(self, report_id: int) -> dict[str, Any] | None:
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
                      result_text,
                      conclusion,
                      checkpoint_snapshot,
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
            "resultText": row["result_text"],
            "conclusion": row["conclusion"],
            "checkpointSnapshot": _json_value(row["checkpoint_snapshot"]),
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

    def list_checkpoints(self) -> list[dict[str, Any]]:
        with self.database.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id, checkpoint_name, checkpoint_content, sort_order, enabled, create_time, update_time
                    FROM capability_report_audit_checkpoint
                    ORDER BY sort_order ASC, id ASC
                    """
                )
                rows = cursor.fetchall()
        return [self._to_checkpoint(row) for row in rows]

    def get_active_checkpoints(self) -> list[dict[str, Any]]:
        return [checkpoint for checkpoint in self.list_checkpoints() if checkpoint["enabled"]]

    def create_checkpoint(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self.database.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO capability_report_audit_checkpoint
                      (`checkpoint_name`, `checkpoint_content`, `sort_order`, `enabled`)
                    VALUES (%s, %s, %s, %s)
                    """,
                    [payload["name"], payload["content"], payload["sortOrder"], int(payload["enabled"])],
                )
                checkpoint_id = int(cursor.lastrowid)
                row = self._select_checkpoint(cursor, checkpoint_id)
        return self._to_checkpoint(row)

    def update_checkpoint(self, checkpoint_id: int, payload: dict[str, Any]) -> dict[str, Any] | None:
        with self.database.connection() as connection:
            with connection.cursor() as cursor:
                if self._select_checkpoint(cursor, checkpoint_id) is None:
                    return None
                cursor.execute(
                    """
                    UPDATE capability_report_audit_checkpoint
                       SET checkpoint_name = %s,
                           checkpoint_content = %s,
                           sort_order = %s,
                           enabled = %s
                     WHERE id = %s
                    """,
                    [payload["name"], payload["content"], payload["sortOrder"], int(payload["enabled"]), checkpoint_id],
                )
                row = self._select_checkpoint(cursor, checkpoint_id)
        return self._to_checkpoint(row)

    def save_checkpoint_snapshot(self, audit_id: int, checkpoints: list[dict[str, Any]]) -> None:
        with self.database.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE capability_report_audit SET checkpoint_snapshot = %s WHERE id = %s",
                    [json.dumps(checkpoints, ensure_ascii=False), audit_id],
                )

    def get_report_conversation(self, report_id: int) -> dict[str, Any] | None:
        with self.database.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT id, systemId, title, report_month, jira_id FROM capability_report_log WHERE id = %s",
                    [report_id],
                )
                report = cursor.fetchone()
                if report is None:
                    return None
                cursor.execute(
                    """
                    SELECT
                      version.id AS version_id, version.version_no, version.version_type, version.file_name,
                      version.uploader, version.source, version.audit_status, version.create_time AS version_create_time,
                      audit.id AS audit_id, audit.status, audit.result_text, audit.conclusion,
                      audit.summary, audit.result_data, audit.checkpoint_snapshot,
                      audit.model_name, audit.error_message, audit.started_at, audit.finished_at
                    FROM capability_report_version version
                    LEFT JOIN capability_report_audit audit ON audit.version_id = version.id
                    WHERE version.report_id = %s
                    ORDER BY version.version_no ASC, audit.create_time ASC, audit.id ASC
                    """,
                    [report_id],
                )
                rows = cursor.fetchall()
        versions: list[dict[str, Any]] = []
        for row in rows:
            versions.append(
                {
                    "versionId": row["version_id"],
                    "versionNo": row["version_no"],
                    "versionType": row["version_type"],
                    "fileName": row["file_name"],
                    "uploader": row["uploader"],
                    "source": row["source"],
                    "auditStatus": row["status"] or row["audit_status"],
                    "createTime": _format_time(row["version_create_time"]),
                    "auditId": row["audit_id"],
                    "resultText": row["result_text"] or self._legacy_result_text(row["summary"], row["result_data"]),
                    "conclusion": row["conclusion"] or self._legacy_conclusion(row["status"]),
                    "checkpointSnapshot": _json_value(row["checkpoint_snapshot"]),
                    "modelName": row["model_name"],
                    "errorMessage": row["error_message"],
                    "startedAt": _format_time(row["started_at"]),
                    "finishedAt": _format_time(row["finished_at"]),
                }
            )
        return {
            "reportId": report["id"],
            "systemId": report["systemId"],
            "title": report["title"],
            "reportMonth": report["report_month"],
            "jiraId": report["jira_id"],
            "versions": versions,
        }

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
        conclusion = result["conclusion"]
        status = conclusion if conclusion in {"passed", "failed"} else "completed"
        with self.database.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE capability_report_audit
                       SET status = %s,
                           result_text = %s,
                           conclusion = %s,
                           finished_at = CURRENT_TIMESTAMP(3),
                           error_message = NULL
                     WHERE id = %s
                    """,
                    [
                        status,
                        result["resultText"],
                        conclusion,
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

    def _select_checkpoint(self, cursor: Any, checkpoint_id: int) -> dict[str, Any] | None:
        cursor.execute(
            """
            SELECT id, checkpoint_name, checkpoint_content, sort_order, enabled, create_time, update_time
            FROM capability_report_audit_checkpoint WHERE id = %s
            """,
            [checkpoint_id],
        )
        return cursor.fetchone()

    def _to_checkpoint(self, row: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": row["id"],
            "name": row["checkpoint_name"],
            "content": row["checkpoint_content"],
            "sortOrder": row["sort_order"],
            "enabled": bool(row["enabled"]),
            "createTime": _format_time(row["create_time"]),
            "updateTime": _format_time(row["update_time"]),
        }

    def _legacy_conclusion(self, status: str | None) -> str | None:
        return status if status in {"passed", "failed"} else None

    def _legacy_result_text(self, summary: Any, result_data: Any) -> str | None:
        parsed_summary = _json_value(summary)
        parsed_data = _json_value(result_data)
        if not parsed_summary and not parsed_data:
            return None
        lines: list[str] = []
        if isinstance(parsed_summary, dict):
            conclusion = parsed_summary.get("结论")
            if conclusion:
                lines.append(f"审核结论：{conclusion}")
            suggestion = parsed_summary.get("建议")
            if suggestion:
                lines.extend(["", "## 审核总结", str(suggestion)])
        items = parsed_data.get("data", []) if isinstance(parsed_data, dict) else []
        if items:
            lines.extend(["", "## 检查点结果"])
            for item in items:
                lines.extend([f"### {item.get('检查点', '检查点')}", str(item.get("分析结果", ""))])
        return "\n\n".join(part for part in lines if part != "")
