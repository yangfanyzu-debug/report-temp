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

    def finalize_report(self, report_id: int, operator: str) -> dict[str, Any] | None:
        ...


class ReportWorkflowConflict(RuntimeError):
    def __init__(self, message: str, code: str):
        super().__init__(message)
        self.code = code


class ReportFinalizedError(ReportWorkflowConflict):
    def __init__(self):
        super().__init__("报告已定稿，不能继续新增版本", "REPORT_FINALIZED")


class ReportNotReadyError(ReportWorkflowConflict):
    pass


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


def _audit_result_summary(result_text: Any) -> str:
    text = str(result_text or "").strip()
    if not text:
        return ""

    lines = [line.strip() for line in text.splitlines()]
    summary_heading_index = next(
        (
            index
            for index, line in enumerate(lines)
            if line.lstrip("#").strip() in {"审核总结", "总结"}
        ),
        None,
    )
    candidates = lines[summary_heading_index + 1 :] if summary_heading_index is not None else lines
    for line in candidates:
        if summary_heading_index is not None and line.startswith("#"):
            break
        content = line.lstrip("# -*").strip()
        if not content or line.startswith("#") or content.startswith("审核结论"):
            continue
        return content[:160]
    return ""


def _audit_type_label(audit_type: str | None) -> str:
    return {"initial": "初始审核", "revision": "修订审核"}.get(
        audit_type or "", "未知审核"
    )


def _latest_audit_join_sql(audit_alias: str, version_alias: str) -> str:
    return f"""
        LEFT JOIN capability_report_audit {audit_alias}
          ON {audit_alias}.id = (
              SELECT inner_{audit_alias}.id
                FROM capability_report_audit inner_{audit_alias}
               WHERE inner_{audit_alias}.version_id = {version_alias}.id
               ORDER BY inner_{audit_alias}.id DESC
               LIMIT 1
          )
    """


def _batch_state_result(
    report_id: int, version: dict[str, Any], debug_reregistration: bool
) -> dict[str, Any]:
    status = version.get("audit_status") or "pending"
    result = {
        "reportId": report_id,
        "versionId": int(version["id"]),
        "versionNo": int(version["version_no"]),
        "auditId": version.get("audit_id"),
        "auditType": "initial",
        "auditStatus": status,
        "created": False,
    }
    if status in {"pending", "running"}:
        return {
            **result,
            "deferred": True,
            "code": "AUDIT_IN_PROGRESS",
            "message": "当前批次版本仍在初审，请等待审核完成",
            "nextAction": "wait",
        }
    if status == "failed":
        return {
            **result,
            "code": "INITIAL_AUDIT_FAILED",
            "message": "初审不通过，请重新生成报告并使用新的generationId登记",
            "nextAction": "regenerate",
        }
    if status == "error":
        return {
            **result,
            "code": "INITIAL_AUDIT_ERROR",
            "message": "初审执行异常，可使用新的generationId重新登记",
            "nextAction": "retry",
        }
    if status == "passed":
        return {
            **result,
            "code": "INITIAL_AUDIT_PASSED",
            "message": (
                "初审已通过，调试模式下可使用新的generationId继续登记"
                if debug_reregistration
                else "初审已通过，批次无需继续登记"
            ),
            "nextAction": "new_generation" if debug_reregistration else "stop",
        }
    return {
        **result,
        "code": "BATCH_REGENERATION_NOT_ALLOWED",
        "message": "当前审核状态不支持重新登记",
        "nextAction": "stop",
    }


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
        latest_audit_join = _latest_audit_join_sql("latest_audit", "latest_version")
        initial_version_join = """
            LEFT JOIN capability_report_version initial_version
              ON initial_version.report_id = report.id
             AND initial_version.version_type = 'initial'
             AND initial_version.version_no = (
                 SELECT MAX(inner_initial.version_no)
                   FROM capability_report_version inner_initial
                  WHERE inner_initial.report_id = report.id
                    AND inner_initial.version_type = 'initial'
             )
        """
        initial_audit_join = _latest_audit_join_sql("initial_audit", "initial_version")
        revision_version_join = """
            LEFT JOIN capability_report_version revision_version
              ON revision_version.report_id = report.id
             AND revision_version.version_type = 'uploaded'
             AND revision_version.version_no = (
                 SELECT MAX(inner_revision.version_no)
                   FROM capability_report_version inner_revision
                  WHERE inner_revision.report_id = report.id
                    AND inner_revision.version_type = 'uploaded'
             )
        """
        revision_audit_join = _latest_audit_join_sql("revision_audit", "revision_version")
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
                      report.jira_status,
                      report.jira_attempts,
                      report.jira_error,
                      report.final_version_id,
                      report.finalized_at,
                      report.finalized_by,
                      report.create_time,
                      latest_version.id AS latest_version_id,
                      latest_version.version_no AS latest_version_no,
                      latest_version.version_type AS latest_version_type,
                      latest_version.uploader AS latest_version_uploader,
                      latest_version.create_time AS latest_version_create_time,
                      latest_version.audit_status AS latest_audit_status,
                      latest_audit.id AS latest_audit_id,
                      latest_audit.audit_type AS latest_audit_type,
                      latest_audit.summary AS latest_audit_summary,
                      latest_audit.result_text AS latest_audit_result_text,
                      latest_audit.conclusion AS latest_audit_conclusion,
                      latest_audit.error_message AS latest_audit_error_message,
                      initial_version.id AS initial_version_id,
                      initial_version.audit_status AS initial_audit_status,
                      initial_audit.id AS initial_audit_id,
                      revision_version.id AS revision_version_id,
                      revision_version.audit_status AS revision_audit_status,
                      revision_audit.id AS revision_audit_id
                    FROM capability_report_log report
                    {latest_version_join}
                    {latest_audit_join}
                    {initial_version_join}
                    {initial_audit_join}
                    {revision_version_join}
                    {revision_audit_join}
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
                    SELECT id, systemId, title, report_month, jira_id, jira_status, jira_error,
                           final_version_id, finalized_at, finalized_by,
                           report_data, meta_data, create_time
                      FROM capability_report_log
                     WHERE id = %s
                    """,
                    [report_id],
                )
                report = cursor.fetchone()
                if report is None:
                    return None
                cursor.execute(
                    f"""
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
                      latest_audit.audit_type AS latest_audit_type,
                      latest_audit.summary AS latest_audit_summary,
                      latest_audit.result_text AS latest_audit_result_text,
                      latest_audit.conclusion AS latest_audit_conclusion,
                      latest_audit.error_message AS latest_audit_error_message
                    FROM capability_report_version version
                    {_latest_audit_join_sql("latest_audit", "version")}
                    WHERE version.report_id = %s
                    ORDER BY version.version_no DESC
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
            "jiraStatus": report["jira_status"],
            "jiraError": report["jira_error"],
            "isFinalized": report["finalized_at"] is not None,
            "finalVersionId": report["final_version_id"],
            "finalizedAt": _format_time(report["finalized_at"]),
            "finalizedBy": report["finalized_by"],
            "reportData": _json_value(report["report_data"]),
            "metaData": _json_value(report["meta_data"]),
            "createTime": _format_time(report["create_time"]),
            "versions": versions,
        }

    def register_initial_report(self, payload: dict[str, Any]) -> dict[str, Any]:
        file_path = payload["filePath"]
        file_name = payload.get("fileName") or Path(file_path).name
        file_size = payload.get("fileSize")
        if file_size is None:
            file_size = Path(file_path).stat().st_size if Path(file_path).is_file() else 0
        report_data = json.dumps({"data": file_path, "type": "file"}, ensure_ascii=False)
        with self.database.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO capability_report_log
                      (`systemId`, `title`, `report_month`, `report_data`, `meta_data`)
                    VALUES (%s, %s, %s, %s, NULL)
                    ON DUPLICATE KEY UPDATE
                      `id` = LAST_INSERT_ID(`id`)
                    """,
                    [payload["systemId"], payload["title"], payload["reportMonth"], report_data],
                )
                report_id = int(cursor.lastrowid)
                cursor.execute(
                    """
                    SELECT id, finalized_at, jira_id, jira_status
                      FROM capability_report_log
                     WHERE id = %s
                     FOR UPDATE
                    """,
                    [report_id],
                )
                report = cursor.fetchone()
                debug_reregistration = bool(payload.get("debugReregistration"))
                cursor.execute(
                    """
                    SELECT version.id, version.version_no,
                           audit.id AS audit_id, audit.status AS audit_status
                      FROM capability_report_version version
                      LEFT JOIN capability_report_audit audit
                        ON audit.id = (
                           SELECT inner_audit.id
                             FROM capability_report_audit inner_audit
                            WHERE inner_audit.version_id = version.id
                            ORDER BY inner_audit.id DESC
                            LIMIT 1
                       )
                     WHERE version.report_id = %s
                       AND version.generation_id = %s
                     LIMIT 1
                    """,
                    [report_id, payload["generationId"]],
                )
                existing_generation = cursor.fetchone()
                if existing_generation:
                    return _batch_state_result(
                        report_id, existing_generation, debug_reregistration
                    )

                if report["finalized_at"] is not None:
                    raise ReportFinalizedError()

                cursor.execute(
                    """
                    SELECT version.id, version.version_no, version.source,
                           version.audit_status, latest_audit.id AS audit_id
                      FROM capability_report_version version
                      LEFT JOIN capability_report_audit latest_audit
                        ON latest_audit.id = (
                            SELECT inner_audit.id
                              FROM capability_report_audit inner_audit
                             WHERE inner_audit.version_id = version.id
                             ORDER BY inner_audit.id DESC
                             LIMIT 1
                        )
                     WHERE version.report_id = %s
                     ORDER BY version.version_no DESC
                     LIMIT 1
                    """,
                    [report_id],
                )
                latest_version = cursor.fetchone()
                if latest_version:
                    if latest_version["source"] != "batch":
                        raise ReportNotReadyError(
                            "报告已进入人工修订阶段，批次不能继续登记", "BATCH_STAGE_CLOSED"
                        )
                    latest_status = latest_version["audit_status"]
                    if latest_status in {"pending", "running"}:
                        return _batch_state_result(
                            report_id, latest_version, debug_reregistration
                        )
                    if latest_status == "passed" and not debug_reregistration:
                        return _batch_state_result(
                            report_id, latest_version, debug_reregistration
                        )
                    if latest_status not in {"failed", "error", "passed"}:
                        raise ReportNotReadyError(
                            "最新批次版本处于不支持重新登记的状态",
                            "BATCH_REGENERATION_NOT_ALLOWED",
                        )
                    if not debug_reregistration and (
                        report["jira_id"] or report["jira_status"] in {
                            "pending",
                            "creating",
                            "created",
                        }
                    ):
                        raise ReportNotReadyError(
                            "报告已进入JIRA创建或人工处理阶段", "BATCH_STAGE_CLOSED"
                        )
                version_no = int(latest_version["version_no"]) + 1 if latest_version else 1
                cursor.execute(
                    """
                    INSERT INTO capability_report_version
                      (`report_id`, `version_no`, `version_type`, `file_name`, `file_path`,
                       `file_size`, `audit_status`, `uploader`, `source`, `generation_id`)
                    VALUES (%s, %s, 'initial', %s, %s, %s, 'pending', '批次任务', 'batch', %s)
                    """,
                    [
                        report_id,
                        version_no,
                        file_name,
                        file_path,
                        file_size,
                        payload["generationId"],
                    ],
                )
                version_id = int(cursor.lastrowid)
                cursor.execute(
                    "UPDATE capability_report_log SET report_data = %s WHERE id = %s",
                    [report_data, report_id],
                )
                audit_id = self._create_pending_audit(cursor, report_id, version_id, "initial")
        return {
            "reportId": report_id,
            "versionId": version_id,
            "versionNo": version_no,
            "auditId": audit_id,
            "auditType": "initial",
            "auditStatus": "pending",
            "created": True,
        }

    def retry_jira_creation(self, report_id: int) -> dict[str, Any] | None:
        with self.database.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute('SELECT id, jira_id, jira_status FROM capability_report_log WHERE id = %s FOR UPDATE', [report_id])
                report = cursor.fetchone()
                if report is None:
                    return None
                if report['jira_id'] or report['jira_status'] in {'pending', 'creating', 'created'}:
                    return {'reportId': report_id, 'created': False, 'jiraStatus': report['jira_status']}
                if report['jira_status'] != 'error':
                    raise ReportNotReadyError('只有JIRA创建失败后才能重试', 'JIRA_RETRY_NOT_ALLOWED')
                cursor.execute(
                    """
                    SELECT version.id AS version_id, audit.id AS audit_id
                      FROM capability_report_version version
                      JOIN capability_report_audit audit ON audit.id = (
                          SELECT a.id FROM capability_report_audit a
                           WHERE a.version_id = version.id ORDER BY a.id DESC LIMIT 1
                      )
                     WHERE version.report_id = %s AND version.version_type = 'initial'
                       AND version.version_no = (
                           SELECT MAX(v.version_no) FROM capability_report_version v
                            WHERE v.report_id = %s AND v.version_type = 'initial'
                       )
                       AND version.audit_status = 'passed' AND audit.conclusion = 'passed'
                    """, [report_id, report_id],
                )
                initial = cursor.fetchone()
                if initial is None:
                    raise ReportNotReadyError('初审通过后才能创建JIRA', 'INITIAL_AUDIT_NOT_PASSED')
                cursor.execute(
                    """UPDATE capability_report_log
                       SET jira_status = 'pending', jira_attempts = 0, jira_error = NULL,
                           jira_version_id = %s, jira_audit_id = %s WHERE id = %s""",
                    [initial['version_id'], initial['audit_id'], report_id],
                )
        return {'reportId': report_id, 'created': True, 'jiraStatus': 'pending'}

    def prepare_uploaded_version(self, report_id: int) -> dict[str, Any] | None:
        with self.database.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT report.id, report.systemId, report.title, report.report_month,
                           report.finalized_at,
                           COALESCE(MAX(version.version_no), 0) AS latest_version_no,
                           (
                               SELECT initial_version.audit_status
                                 FROM capability_report_version initial_version
                                WHERE initial_version.report_id = report.id
                                  AND initial_version.version_type = 'initial'
                                ORDER BY initial_version.version_no DESC
                                LIMIT 1
                           ) AS initial_audit_status
                      FROM capability_report_log report
                      LEFT JOIN capability_report_version version ON version.report_id = report.id
                     WHERE report.id = %s
                     GROUP BY report.id, report.systemId, report.title, report.report_month,
                              report.finalized_at
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
            "isFinalized": row["finalized_at"] is not None,
            "initialAuditStatus": row["initial_audit_status"],
        }

    def create_uploaded_version(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self.database.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT finalized_at FROM capability_report_log WHERE id = %s FOR UPDATE",
                    [payload["reportId"]],
                )
                report = cursor.fetchone()
                if report is None:
                    raise ReportNotReadyError("未找到该报告", "REPORT_NOT_FOUND")
                if report["finalized_at"] is not None:
                    raise ReportFinalizedError()
                cursor.execute(
                    """
                    SELECT audit_status
                      FROM capability_report_version
                     WHERE report_id = %s
                       AND version_type = 'initial'
                     ORDER BY version_no DESC
                     LIMIT 1
                    """,
                    [payload["reportId"]],
                )
                initial_version = cursor.fetchone()
                if initial_version is None or initial_version["audit_status"] != "passed":
                    raise ReportNotReadyError(
                        "初审通过后才能上传修订版本", "INITIAL_AUDIT_NOT_PASSED"
                    )
                cursor.execute(
                    """
                    SELECT COALESCE(MAX(version_no), 0) AS latest_version_no
                      FROM capability_report_version
                     WHERE report_id = %s
                    """,
                    [payload["reportId"]],
                )
                version_no = int(cursor.fetchone()["latest_version_no"]) + 1
                cursor.execute(
                    """
                    INSERT INTO capability_report_version
                      (`report_id`, `version_no`, `version_type`, `file_name`, `file_path`, `file_size`, `audit_status`, `uploader`, `source`)
                    VALUES (%s, %s, 'uploaded', %s, %s, %s, 'pending', %s, 'upload')
                    """,
                    [
                        payload["reportId"],
                        version_no,
                        payload["fileName"],
                        payload["filePath"],
                        payload["fileSize"],
                        payload["uploader"],
                    ],
                )
                version_id = int(cursor.lastrowid)
                audit_id = self._create_pending_audit(
                    cursor, payload["reportId"], version_id, "revision"
                )
        return {
            "reportId": payload["reportId"],
            "versionId": version_id,
            "versionNo": version_no,
            "auditId": audit_id,
            "auditType": "revision",
            "auditStatus": "pending",
        }

    def finalize_report(self, report_id: int, operator: str) -> dict[str, Any] | None:
        with self.database.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id, final_version_id, finalized_at, finalized_by
                      FROM capability_report_log
                     WHERE id = %s
                     FOR UPDATE
                    """,
                    [report_id],
                )
                report = cursor.fetchone()
                if report is None:
                    return None
                if report["finalized_at"] is not None:
                    return {
                        "reportId": report_id,
                        "finalVersionId": report["final_version_id"],
                        "finalizedAt": _format_time(report["finalized_at"]),
                        "finalizedBy": report["finalized_by"],
                        "created": False,
                    }
                cursor.execute(
                    """
                    SELECT id, version_no, version_type, audit_status
                      FROM capability_report_version
                     WHERE report_id = %s
                     ORDER BY version_no DESC
                     LIMIT 1
                    """,
                    [report_id],
                )
                latest_version = cursor.fetchone()
                if latest_version is None or latest_version["version_type"] != "uploaded":
                    raise ReportNotReadyError(
                        "至少上传一个修订版本并通过AI审核后才能确认定稿",
                        "REVISION_REQUIRED",
                    )
                if latest_version["audit_status"] != "passed":
                    raise ReportNotReadyError(
                        "最新修订版本AI审核通过后才能确认定稿",
                        "REVISION_AUDIT_NOT_PASSED",
                    )
                cursor.execute(
                    """
                    UPDATE capability_report_log
                       SET final_version_id = %s,
                           finalized_at = CURRENT_TIMESTAMP(3),
                           finalized_by = %s
                     WHERE id = %s AND finalized_at IS NULL
                    """,
                    [latest_version["id"], operator, report_id],
                )
                cursor.execute(
                    "SELECT finalized_at FROM capability_report_log WHERE id = %s",
                    [report_id],
                )
                finalized = cursor.fetchone()
        return {
            "reportId": report_id,
            "finalVersionId": latest_version["id"],
            "finalVersionNo": latest_version["version_no"],
            "finalizedAt": _format_time(finalized["finalized_at"]),
            "finalizedBy": operator,
            "created": True,
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
            if filters["auditStatus"] == "processing":
                clauses.append("latest_version.audit_status IN ('pending', 'running')")
            else:
                clauses.append("latest_version.audit_status = %s")
                params.append(filters["auditStatus"])
        return (f"WHERE {' AND '.join(clauses)}" if clauses else "", params)

    def _create_pending_audit(
        self, cursor: Any, report_id: int, version_id: int, audit_type: str
    ) -> int:
        audit_type_labels = {"initial": "初始审核", "revision": "修订审核"}
        if audit_type not in audit_type_labels:
            raise ValueError("不支持的审核类型")
        cursor.execute(
            """
            INSERT INTO capability_report_audit
              (`report_id`, `version_id`, `audit_type`, `status`, `summary`, `result_data`)
            VALUES (%s, %s, %s, 'pending', NULL, NULL)
            """,
            [report_id, version_id, audit_type],
        )
        audit_id = int(cursor.lastrowid)
        cursor.execute(
            """
            INSERT INTO capability_report_audit_event
              (`audit_id`, `event_type`, `phase`, `content`)
            VALUES (%s, 'system', 'queued', %s)
            """,
            [audit_id, f"报告已登记，等待AI执行{audit_type_labels[audit_type]}"],
        )
        return audit_id

    def _to_report_row(self, row: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": row["id"],
            "systemId": row["systemId"],
            "title": row["title"],
            "reportMonth": row["report_month"],
            "jiraId": row["jira_id"],
            "jiraStatus": row.get("jira_status") or (
                "created" if row["jira_id"] else "not_created"
            ),
            "jiraError": row.get("jira_error"),
            "jiraAttempts": int(row.get("jira_attempts") or 0),
            "isFinalized": row.get("finalized_at") is not None,
            "finalVersionId": row.get("final_version_id"),
            "finalizedAt": _format_time(row.get("finalized_at")),
            "finalizedBy": row.get("finalized_by"),
            "latestVersionId": row["latest_version_id"],
            "latestVersionNo": row["latest_version_no"],
            "latestVersionType": row["latest_version_type"],
            "latestVersionUploader": row.get("latest_version_uploader"),
            "latestVersionCreateTime": _format_time(row.get("latest_version_create_time")),
            "latestAuditId": row["latest_audit_id"],
            "latestAuditType": row.get("latest_audit_type"),
            "latestAuditTypeLabel": _audit_type_label(row.get("latest_audit_type")),
            "latestAuditStatus": row["latest_audit_status"] or "pending",
            "latestAuditConclusion": self._audit_conclusion(row),
            "latestAuditSuggestion": self._audit_suggestion(row),
            "initialVersionId": row.get("initial_version_id"),
            "initialAuditId": row.get("initial_audit_id"),
            "initialAuditStatus": (
                row.get("initial_audit_status") or "pending"
                if row.get("initial_version_id")
                else None
            ),
            "revisionVersionId": row.get("revision_version_id"),
            "revisionAuditId": row.get("revision_audit_id"),
            "revisionAuditStatus": (
                row.get("revision_audit_status") or "pending"
                if row.get("revision_version_id")
                else None
            ),
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
            "auditType": row.get("latest_audit_type"),
            "auditTypeLabel": _audit_type_label(row.get("latest_audit_type")),
            "latestAuditConclusion": self._audit_conclusion(row),
            "latestAuditSuggestion": self._audit_suggestion(row),
            "latestAuditErrorMessage": row.get("latest_audit_error_message"),
        }

    def _audit_conclusion(self, row: dict[str, Any]) -> str:
        conclusion = row.get("latest_audit_conclusion")
        if conclusion:
            return {"passed": "通过", "failed": "不通过", "completed": "已完成"}.get(conclusion, str(conclusion))
        return _summary_text(row.get("latest_audit_summary"), "结论")

    def _audit_suggestion(self, row: dict[str, Any]) -> str:
        legacy = _summary_text(row.get("latest_audit_summary"), "建议")
        if legacy:
            return legacy
        return _audit_result_summary(row.get("latest_audit_result_text"))
