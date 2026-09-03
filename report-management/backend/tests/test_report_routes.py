from __future__ import annotations

import io
import sys
import tempfile
import unittest
import zipfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any


BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app import create_app  # noqa: E402


def make_docx(content: str = "报告内容") -> io.BytesIO:
    from docx import Document

    stream = io.BytesIO()
    document = Document()
    document.add_paragraph(content)
    document.save(stream)
    stream.seek(0)
    return stream


class RecordingCursor:
    def __init__(
        self,
        version_type: str = "uploaded",
        latest_audit: dict[str, Any] | None = None,
        latest_version_no: int = 2,
        initial_audit_status: str = "passed",
        latest_version_type: str = "uploaded",
        latest_version_audit_status: str = "passed",
        latest_report_version: dict[str, Any] | None = None,
        existing_generation: dict[str, Any] | None = None,
    ):
        self.version_type = version_type
        self.latest_audit = latest_audit
        self.latest_version_no = latest_version_no
        self.initial_audit_status = initial_audit_status
        self.latest_version_type = latest_version_type
        self.latest_version_audit_status = latest_version_audit_status
        self.latest_report_version = latest_report_version
        self.existing_generation = existing_generation
        self.executions: list[tuple[str, list[Any]]] = []
        self.last_sql = ""
        self.lastrowid = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def execute(self, sql: str, params: list[Any] | None = None):
        self.last_sql = " ".join(sql.split())
        self.executions.append((self.last_sql, list(params or [])))
        if self.last_sql.startswith("INSERT INTO capability_report_log"):
            self.lastrowid = 1
        elif self.last_sql.startswith("INSERT INTO capability_report_version"):
            self.lastrowid = 9 if "'initial'" in self.last_sql else 11
        elif self.last_sql.startswith("INSERT INTO capability_report_audit "):
            self.lastrowid = 88 if self.lastrowid == 9 else 101

    def fetchone(self):
        if "SELECT id, final_version_id, finalized_at, finalized_by" in self.last_sql:
            return {
                "id": 1,
                "final_version_id": None,
                "finalized_at": None,
                "finalized_by": None,
            }
        if "SELECT id, finalized_at, jira_id, jira_status" in self.last_sql:
            return {
                "id": 1,
                "finalized_at": None,
                "jira_id": "",
                "jira_status": "not_created",
            }
        if "version.generation_id" in self.last_sql:
            return self.existing_generation
        if "version.source" in self.last_sql and "latest_audit.id AS audit_id" in self.last_sql:
            return self.latest_report_version
        if "SELECT finalized_at FROM capability_report_log" in self.last_sql:
            return {"finalized_at": None}
        if "SELECT audit_status FROM capability_report_version" in self.last_sql:
            return {"audit_status": self.initial_audit_status}
        if "SELECT id, version_no, version_type, audit_status" in self.last_sql:
            return {
                "id": 11,
                "version_no": self.latest_version_no,
                "version_type": self.latest_version_type,
                "audit_status": self.latest_version_audit_status,
            }
        if "SELECT COALESCE(MAX(version_no), 0) AS latest_version_no" in self.last_sql:
            return {"latest_version_no": self.latest_version_no}
        if "FROM capability_report_version version" in self.last_sql:
            return {"id": 10, "version_type": self.version_type}
        if "FROM capability_report_audit" in self.last_sql:
            return self.latest_audit
        if "SELECT id FROM capability_report_version" in self.last_sql:
            return None
        return None


class RecordingConnection:
    def __init__(self, cursor: RecordingCursor):
        self.recording_cursor = cursor

    def cursor(self):
        return self.recording_cursor


class RecordingDatabase:
    def __init__(self, cursor: RecordingCursor):
        self.cursor = cursor

    @contextmanager
    def connection(self):
        yield RecordingConnection(self.cursor)


class FakeReportRepository:
    def __init__(self):
        self.last_filters = None
        self.last_page = None
        self.registered_payload = None
        self.created_upload_payload = None
        self.detail = {
            "id": 1,
            "systemId": "credit-card-center",
            "title": "中信银行信用卡中心授权交易资源分析报告",
            "reportMonth": "2025年08月",
            "jiraId": "JIRA-10086",
            "jiraStatus": "created",
            "jiraError": None,
            "isFinalized": False,
            "finalVersionId": None,
            "finalizedAt": None,
            "finalizedBy": "",
            "versions": [
                {
                    "id": 10,
                    "versionNo": 2,
                    "versionType": "uploaded",
                    "fileName": "修订版.docx",
                    "fileSize": 74200,
                    "auditStatus": "running",
                    "uploader": "未知用户",
                    "source": "upload",
                    "createTime": "2026-08-11 11:20:00",
                    "latestAuditId": 99,
                    "latestAuditConclusion": "审核中",
                }
            ],
        }
        self.version_file = None
        self.created_prompt_payload = None
        self.prompt_error = None
        self.updated_ai_config_payload = None
        self.ai_config = {
            "id": 1,
            "apiUrl": "https://ark.cn-beijing.volces.com/api/coding/v3",
            "modelName": "deepseek-chat",
            "apiKey": "ark-secret-abcd",
            "apiKeyMasked": "ark-****abcd",
            "apiKeyConfigured": True,
            "createTime": "2026-08-11 10:00:00",
            "updateTime": "2026-08-11 11:00:00",
        }
        self.active_prompts = {
            "revision": {
                "id": 1,
                "name": "修订审核提示词",
                "auditType": "revision",
                "promptContent": "请审核报告",
                "version": 2,
                "enabled": True,
                "apiKey": "ark-secret-abcd",
                "apiKeyMasked": "ark-****abcd",
                "apiKeyConfigured": True,
                "createTime": "2026-08-11 10:00:00",
                "updateTime": "2026-08-11 11:00:00",
            },
            "initial": {
                "id": 2,
                "name": "初始审核提示词",
                "auditType": "initial",
                "promptContent": "请审核初始报告",
                "version": 1,
                "enabled": True,
                "apiKey": "ark-secret-abcd",
                "apiKeyMasked": "ark-****abcd",
                "apiKeyConfigured": True,
                "createTime": "2026-08-11 10:00:00",
                "updateTime": "2026-08-11 11:00:00",
            },
        }
        self.audit_detail = {
            "id": 99,
            "status": "failed",
            "summary": {"结论": "不通过", "问题数量": 1, "建议": "请修正ES服务器数量"},
            "resultData": {
                "data": [
                    {
                        "检查点": "检测章节应用指标统计与分析是否空缺",
                        "分析结果": "内容完整，无空缺",
                    }
                ]
            },
            "promptId": 1,
            "promptVersion": 2,
            "modelName": "deepseek-chat",
            "errorMessage": None,
            "startedAt": "2026-08-11 11:20:01",
            "finishedAt": "2026-08-11 11:20:35",
            "createTime": "2026-08-11 11:20:00",
        }
        self.audit_events = [
            {
                "id": 10,
                "type": "system",
                "phase": "extracting",
                "content": "正在解析DOCX中的章节、正文和表格",
                "createTime": "2026-08-11 11:20:02",
            },
            {
                "id": 11,
                "type": "model",
                "phase": "streaming",
                "content": "正在检查章节完整性",
                "createTime": "2026-08-11 11:20:03",
            },
        ]
        self.checkpoints = [
            {
                "id": 1,
                "name": "章节完整性",
                "content": "检测章节是否空缺",
                "sortOrder": 10,
                "enabled": True,
                "createTime": "2026-08-11 10:00:00",
                "updateTime": "2026-08-11 10:00:00",
            }
        ]
        self.conversation = {
            "reportId": 1,
            "systemId": "credit-card-center",
            "title": "中信银行信用卡中心授权交易资源分析报告",
            "reportMonth": "2025年08月",
            "jiraId": "JIRA-10086",
            "versions": [
                {
                    "versionId": 10,
                    "versionNo": 2,
                    "fileName": "修订版.docx",
                    "auditId": 99,
                    "auditStatus": "failed",
                    "resultText": "审核结论：不通过\n请修正服务器数量。",
                    "conclusion": "failed",
                }
            ],
        }
        self.agent_messages = [
            {
                "id": 1,
                "replyToId": None,
                "role": "user",
                "content": "报告有什么问题？",
                "status": "completed",
                "modelName": None,
                "errorMessage": None,
                "createTime": "2026-08-11 12:00:00",
                "updateTime": "2026-08-11 12:00:00",
                "finishedAt": None,
            }
        ]
        self.created_agent_exchange = None
        self.retry_result = {
            "reportId": 1,
            "versionId": 10,
            "auditId": 101,
            "auditType": "revision",
            "auditStatus": "pending",
            "created": True,
        }
        self.finalize_result = {
            "reportId": 1,
            "finalVersionId": 10,
            "finalVersionNo": 2,
            "finalizedAt": "2026-08-31 10:00:00",
            "finalizedBy": "张三",
            "created": True,
        }
        self.finalized_report_ids = []
        self.upload_context_finalized = False
        self.upload_context_initial_audit_status = "passed"
        self.upload_error = None
        self.register_created = True
        self.register_result_override = None

    def list_reports(self, filters, page_num, page_size):
        self.last_filters = filters
        self.last_page = (page_num, page_size)
        return {
            "rows": [
                {
                    "id": 1,
                    "systemId": "credit-card-center",
                    "title": "中信银行信用卡中心授权交易资源分析报告",
                    "reportMonth": "2025年08月",
                    "jiraId": "JIRA-10086",
                    "jiraStatus": "created",
                    "isFinalized": False,
                    "latestVersionId": 10,
                    "latestVersionNo": 2,
                    "latestVersionType": "uploaded",
                    "latestAuditId": 99,
                    "latestAuditStatus": "failed",
                    "latestAuditConclusion": "不通过",
                    "latestAuditSuggestion": "请修正ES服务器数量",
                    "initialVersionId": 9,
                    "initialAuditId": 88,
                    "initialAuditStatus": "passed",
                    "revisionVersionId": 10,
                    "revisionAuditId": 99,
                    "revisionAuditStatus": "failed",
                    "createTime": "2026-08-11 10:30:00",
                }
            ],
            "total": 1,
        }

    def get_report_detail(self, report_id):
        return self.detail if report_id == 1 else None

    def register_initial_report(self, payload):
        self.registered_payload = payload
        if self.register_result_override is not None:
            return self.register_result_override
        result = {
            "reportId": 1,
            "versionId": 9,
            "auditId": 88,
            "auditType": "initial",
            "auditStatus": "pending",
            "versionNo": 1,
            "created": self.register_created,
        }
        if not self.register_created:
            result.update(
                {
                    "deferred": True,
                    "code": "AUDIT_IN_PROGRESS",
                    "nextAction": "wait",
                }
            )
        return result

    def prepare_uploaded_version(self, report_id):
        if report_id != 1:
            return None
        return {
            "reportId": 1,
            "systemId": "credit-card-center",
            "title": "中信银行信用卡中心授权交易资源分析报告",
            "reportMonth": "2025年08月",
            "nextVersionNo": 3,
            "isFinalized": self.upload_context_finalized,
            "initialAuditStatus": self.upload_context_initial_audit_status,
        }

    def create_uploaded_version(self, payload):
        self.created_upload_payload = payload
        if self.upload_error:
            raise self.upload_error
        return {
            "reportId": 1,
            "versionId": 11,
            "versionNo": 3,
            "auditId": 100,
            "auditType": "revision",
            "auditStatus": "pending",
        }

    def get_version_file(self, version_id):
        if version_id != 10:
            return None
        return self.version_file

    def finalize_report(self, report_id, operator):
        if report_id != 1:
            return None
        self.finalized_report_ids.append((report_id, operator))
        return {**self.finalize_result, "finalizedBy": operator}

    def get_audit_detail(self, audit_id):
        return self.audit_detail if audit_id == 99 else None

    def get_audit_events(self, audit_id, after_id=0):
        if audit_id != 99:
            return []
        return [event for event in self.audit_events if event["id"] > after_id]

    def get_ai_config(self):
        return self.ai_config

    def update_ai_config(self, payload):
        self.updated_ai_config_payload = payload
        api_key = payload.get("apiKey") or self.ai_config["apiKey"]
        self.ai_config = {
            "id": 1,
            "apiUrl": payload["apiUrl"],
            "modelName": payload["modelName"],
            "apiKey": api_key,
            "apiKeyMasked": "ark-****abcd",
            "apiKeyConfigured": bool(api_key),
        }
        return self.ai_config

    def get_active_prompt(self, audit_type):
        return self.active_prompts.get(audit_type)

    def create_prompt_version(self, audit_type, payload):
        if self.prompt_error:
            raise self.prompt_error
        self.created_prompt_payload = {"auditType": audit_type, **payload}
        return {
            "id": 2,
            "name": payload["name"],
            "auditType": audit_type,
            "promptContent": payload["promptContent"],
            "version": 3,
            "enabled": True,
            "apiKey": payload.get("apiKey", ""),
            "apiKeyMasked": "ark-****wxyz",
            "apiKeyConfigured": True,
            "createTime": "2026-08-11 12:00:00",
            "updateTime": "2026-08-11 12:00:00",
        }

    def list_checkpoints(self):
        return self.checkpoints

    def create_checkpoint(self, payload):
        checkpoint = {"id": 2, **payload, "createTime": "2026-08-11 12:00:00", "updateTime": "2026-08-11 12:00:00"}
        self.checkpoints.append(checkpoint)
        return checkpoint

    def update_checkpoint(self, checkpoint_id, payload):
        if checkpoint_id != 1:
            return None
        checkpoint = {"id": checkpoint_id, **payload, "createTime": "2026-08-11 10:00:00", "updateTime": "2026-08-11 12:00:00"}
        self.checkpoints[0] = checkpoint
        return checkpoint

    def get_report_conversation(self, report_id):
        return self.conversation if report_id == 1 else None

    def list_agent_messages(self, report_id, version_id):
        return self.agent_messages if report_id == 1 and version_id == 10 else None

    def create_agent_exchange(self, report_id, version_id, content):
        if report_id != 1 or version_id != 10:
            return None
        self.created_agent_exchange = (report_id, version_id, content)
        return {"userMessageId": 2, "assistantMessageId": 3, "status": "pending"}

    def retry_version_audit(self, report_id, version_id):
        if report_id != 1 or version_id != 10:
            return None
        return self.retry_result


class ReportRoutesTest(unittest.TestCase):
    def setUp(self):
        self.storage = tempfile.TemporaryDirectory()
        self.initial_report_dir = Path(self.storage.name) / "initial_reports"
        self.repository = FakeReportRepository()
        self.preview_path = Path(self.storage.name) / "preview.docx"
        self.preview_path.write_bytes(make_docx("预览内容").getvalue())
        self.repository.version_file = {
            "id": 10,
            "fileName": "预览报告.docx",
            "filePath": str(self.preview_path),
        }
        self.app = create_app(
            {
                "TESTING": True,
                "REPORT_REPOSITORY": self.repository,
                "UPLOAD_DIR": self.storage.name,
                "INITIAL_REPORT_DIR": str(self.initial_report_dir),
            }
        )
        self.client = self.app.test_client()

    def tearDown(self):
        self.storage.cleanup()

    @staticmethod
    def _batch_registration_payload(generation_id: str) -> dict[str, Any]:
        return {
            "systemId": "credit-card-center",
            "title": "容量报告",
            "reportMonth": "2026年08月",
            "filePath": "/tmp/report.docx",
            "fileName": "report.docx",
            "fileSize": 100,
            "generationId": generation_id,
            "source": "batch",
        }

    def test_list_reports_passes_filters_and_pagination(self):
        response = self.client.get(
            "/api/report-management/reports",
            query_string={
                "systemId": "credit",
                "title": "授权交易",
                "reportMonth": "2025年08月",
                "auditStatus": "failed",
                "pageNum": "2",
                "pageSize": "20",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        self.assertEqual(response.json["total"], 1)
        self.assertEqual(response.json["rows"][0]["jiraId"], "JIRA-10086")
        self.assertEqual(response.json["rows"][0]["latestAuditConclusion"], "不通过")
        self.assertEqual(response.json["rows"][0]["initialAuditStatus"], "passed")
        self.assertEqual(response.json["rows"][0]["revisionAuditStatus"], "failed")
        self.assertEqual(
            self.repository.last_filters,
            {
                "systemId": "credit",
                "title": "授权交易",
                "reportMonth": "2025年08月",
                "auditStatus": "failed",
            },
        )
        self.assertEqual(self.repository.last_page, (2, 20))

    def test_processing_filter_builds_pending_and_running_clause(self):
        from app.repositories.reports import MySqlReportRepository

        where, params = MySqlReportRepository(None)._build_filters({"auditStatus": "processing"})

        self.assertIn("audit_status IN ('pending', 'running')", where)
        self.assertEqual(params, [])

    def test_report_row_separates_initial_and_revision_audit_status(self):
        from app.repositories.reports import MySqlReportRepository

        row = {
            "id": 1,
            "systemId": "credit-card-center",
            "title": "容量报告",
            "report_month": "2026年08月",
            "jira_id": "",
            "jira_status": "not_created",
            "jira_error": None,
            "final_version_id": None,
            "finalized_at": None,
            "finalized_by": None,
            "latest_version_id": 9,
            "latest_version_no": 1,
            "latest_version_type": "initial",
            "latest_version_uploader": "批次任务",
            "latest_version_create_time": None,
            "latest_audit_id": 88,
            "latest_audit_type": "initial",
            "latest_audit_status": "passed",
            "latest_audit_summary": None,
            "latest_audit_result_text": "审核结论：通过",
            "latest_audit_conclusion": "passed",
            "latest_audit_error_message": None,
            "initial_version_id": 9,
            "initial_audit_id": 88,
            "initial_audit_status": "passed",
            "revision_version_id": None,
            "revision_audit_id": None,
            "revision_audit_status": None,
            "create_time": None,
        }

        result = MySqlReportRepository(None)._to_report_row(row)

        self.assertEqual(result["initialAuditStatus"], "passed")
        self.assertEqual(result["initialAuditId"], 88)
        self.assertIsNone(result["revisionAuditStatus"])
        self.assertIsNone(result["revisionAuditId"])

    def test_latest_audit_join_uses_monotonic_id(self):
        from app.repositories.reports import _latest_audit_join_sql

        sql = " ".join(_latest_audit_join_sql("latest_audit", "version").split())

        self.assertIn("latest_audit.id = (", sql)
        self.assertIn("ORDER BY inner_latest_audit.id DESC LIMIT 1", sql)
        self.assertNotIn("MAX(inner_latest_audit.create_time)", sql)

    def test_get_report_detail(self):
        response = self.client.get("/api/report-management/reports/1")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["reportMonth"], "2025年08月")
        self.assertEqual(response.json["versions"][0]["versionNo"], 2)

    def test_get_report_detail_returns_404(self):
        response = self.client.get("/api/report-management/reports/999")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json, {"message": "未找到该报告"})

    def test_register_initial_report(self):
        response = self.client.post(
            "/api/report-management/reports/register",
            json={
                "systemId": "credit-card-center",
                "title": "中信银行信用卡中心授权交易资源分析报告",
                "reportMonth": "2025年08月",
                "filePath": "/appdata/report.docx",
                "generationId": "batch-202508-credit-001",
            },
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json["auditType"], "initial")
        self.assertEqual(self.repository.registered_payload["source"], "batch")
        self.assertEqual(
            self.repository.registered_payload["generationId"],
            "batch-202508-credit-001",
        )
        self.assertFalse(self.repository.registered_payload["debugReregistration"])

    def test_register_initial_report_passes_debug_reregistration_setting(self):
        self.app.config["BATCH_DEBUG_REREGISTRATION"] = True

        response = self.client.post(
            "/api/report-management/reports/register",
            json={
                "systemId": "credit-card-center",
                "title": "中信银行信用卡中心授权交易资源分析报告",
                "reportMonth": "2025年08月",
                "filePath": "/appdata/report.docx",
                "generationId": "batch-debug-001",
            },
        )

        self.assertEqual(response.status_code, 201)
        self.assertTrue(self.repository.registered_payload["debugReregistration"])

    def test_register_initial_report_requires_fields(self):
        response = self.client.post("/api/report-management/reports/register", json={"systemId": "x"})

        self.assertEqual(response.status_code, 400)
        self.assertIn("缺少必要参数", response.json["message"])

    def test_register_initial_report_requires_generation_id(self):
        response = self.client.post(
            "/api/report-management/reports/register",
            json={
                "systemId": "credit-card-center",
                "title": "报告",
                "reportMonth": "2025年08月",
                "filePath": "/appdata/report.docx",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("generationId", response.json["message"])

    def test_upload_and_register_initial_report(self):
        response = self.client.post(
            "/api/report-management/reports/register-upload",
            data={
                "file": (make_docx(), "性能容量报告.docx"),
                "systemId": "credit-card-center",
                "title": "中信银行信用卡中心授权交易资源分析报告",
                "reportMonth": "2025年08月",
                "generationId": "batch-upload-001",
            },
            content_type="multipart/form-data",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json["auditStatus"], "pending")
        self.assertEqual(response.json["auditType"], "initial")
        payload = self.repository.registered_payload
        self.assertEqual(payload["source"], "batch")
        self.assertEqual(payload["generationId"], "batch-upload-001")
        self.assertEqual(payload["fileName"], "性能容量报告.docx")
        self.assertGreater(payload["fileSize"], 0)
        saved_path = Path(payload["filePath"])
        self.assertTrue(saved_path.is_file())
        self.assertEqual(saved_path.parent, self.initial_report_dir)
        self.assertNotEqual(saved_path.name, "性能容量报告.docx")
        self.assertIn("_v1_", saved_path.name)

    def test_upload_and_register_initial_report_uses_unique_server_names(self):
        paths = []
        for index in range(2):
            response = self.client.post(
                "/api/report-management/reports/register-upload",
                data={
                    "file": (make_docx(), "同名报告.docx"),
                    "systemId": "credit-card-center",
                    "title": "同名报告",
                    "reportMonth": "2025年08月",
                    "generationId": f"same-name-{index}",
                },
                content_type="multipart/form-data",
            )
            self.assertEqual(response.status_code, 201)
            paths.append(Path(self.repository.registered_payload["filePath"]))

        self.assertNotEqual(paths[0], paths[1])
        self.assertTrue(all(path.is_file() for path in paths))

    def test_upload_and_register_initial_report_removes_idempotent_replay_file(self):
        self.repository.register_created = False

        response = self.client.post(
            "/api/report-management/reports/register-upload",
            data={
                "file": (make_docx(), "重复报告.docx"),
                "systemId": "credit-card-center",
                "title": "重复报告",
                "reportMonth": "2025年08月",
                "generationId": "same-generation-001",
            },
            content_type="multipart/form-data",
        )

        self.assertEqual(response.status_code, 202)
        self.assertFalse(response.json["created"])
        self.assertEqual(response.json["nextAction"], "wait")
        self.assertEqual(list(self.initial_report_dir.iterdir()), [])

    def test_upload_and_register_returns_202_while_previous_audit_is_running(self):
        self.repository.register_result_override = {
            "reportId": 1,
            "versionId": 9,
            "versionNo": 1,
            "auditId": 88,
            "auditType": "initial",
            "auditStatus": "running",
            "created": False,
            "deferred": True,
            "code": "AUDIT_IN_PROGRESS",
            "nextAction": "wait",
        }

        response = self.client.post(
            "/api/report-management/reports/register-upload",
            data={
                "file": (make_docx(), "重复报告.docx"),
                "systemId": "credit-card-center",
                "title": "重复报告",
                "reportMonth": "2025年08月",
                "generationId": "next-generation-001",
            },
            content_type="multipart/form-data",
        )

        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json["code"], "AUDIT_IN_PROGRESS")
        self.assertEqual(response.json["nextAction"], "wait")
        self.assertEqual(list(self.initial_report_dir.iterdir()), [])

    def test_upload_and_register_initial_report_rejects_missing_fields_before_saving(self):
        response = self.client.post(
            "/api/report-management/reports/register-upload",
            data={"file": (make_docx(), "报告.docx"), "systemId": "credit-card-center"},
            content_type="multipart/form-data",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("缺少必要参数", response.json["message"])
        self.assertFalse(self.initial_report_dir.exists())

    def test_upload_and_register_initial_report_rejects_invalid_docx(self):
        response = self.client.post(
            "/api/report-management/reports/register-upload",
            data={
                "file": (io.BytesIO(b"not docx"), "报告.docx"),
                "systemId": "credit-card-center",
                "title": "测试报告",
                "reportMonth": "2025年08月",
                "generationId": "invalid-docx-001",
            },
            content_type="multipart/form-data",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json, {"message": "文件内容不是有效的 DOCX 文档"})
        self.assertEqual(list(self.initial_report_dir.iterdir()), [])

    def test_upload_report_version_creates_versioned_file(self):
        response = self.client.post(
            "/api/report-management/reports/1/versions",
            data={"file": (make_docx(), "报告 修订版.docx"), "uploader": "张三"},
            content_type="multipart/form-data",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json["versionNo"], 3)
        self.assertEqual(response.json["auditType"], "revision")
        self.assertEqual(self.repository.created_upload_payload["fileName"], "报告 修订版.docx")
        self.assertEqual(self.repository.created_upload_payload["uploader"], "张三")
        saved_path = Path(self.repository.created_upload_payload["filePath"])
        self.assertTrue(saved_path.exists())
        self.assertNotEqual(saved_path.name, "报告 修订版.docx")
        self.assertIn("_v3_", saved_path.name)

    def test_upload_report_version_returns_404_for_missing_report(self):
        response = self.client.post(
            "/api/report-management/reports/999/versions",
            data={"file": (make_docx(), "报告.docx")},
            content_type="multipart/form-data",
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json, {"message": "未找到该报告"})

    def test_upload_report_version_rejects_finalized_report(self):
        self.repository.upload_context_finalized = True

        response = self.client.post(
            "/api/report-management/reports/1/versions",
            data={"file": (make_docx(), "报告.docx")},
            content_type="multipart/form-data",
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json["code"], "REPORT_FINALIZED")

    def test_upload_report_version_rejects_report_before_initial_audit_passes(self):
        self.repository.upload_context_initial_audit_status = "failed"

        response = self.client.post(
            "/api/report-management/reports/1/versions",
            data={"file": (make_docx(), "报告.docx")},
            content_type="multipart/form-data",
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json["code"], "INITIAL_AUDIT_NOT_PASSED")
        self.assertIsNone(self.repository.created_upload_payload)
        self.assertEqual(
            sorted(path.name for path in Path(self.storage.name).iterdir()),
            ["preview.docx"],
        )

    def test_upload_report_version_removes_file_after_repository_error(self):
        self.repository.upload_error = RuntimeError("数据库不可用")

        with self.assertRaisesRegex(RuntimeError, "数据库不可用"):
            self.client.post(
                "/api/report-management/reports/1/versions",
                data={"file": (make_docx(), "报告.docx")},
                content_type="multipart/form-data",
            )

        self.assertEqual(
            sorted(path.name for path in Path(self.storage.name).iterdir()),
            ["preview.docx"],
        )

    def test_finalize_report(self):
        response = self.client.post(
            "/api/report-management/reports/1/finalize", json={"operator": "张三"}
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json["finalVersionId"], 10)
        self.assertEqual(self.repository.finalized_report_ids, [(1, "张三")])

    def test_finalize_report_returns_404(self):
        response = self.client.post("/api/report-management/reports/999/finalize")

        self.assertEqual(response.status_code, 404)

    def test_upload_report_version_rejects_invalid_docx(self):
        response = self.client.post(
            "/api/report-management/reports/1/versions",
            data={"file": (io.BytesIO(b"not docx"), "报告.docx")},
            content_type="multipart/form-data",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json, {"message": "文件内容不是有效的 DOCX 文档"})
        self.assertEqual(sorted(path.name for path in Path(self.storage.name).iterdir()), ["preview.docx"])

    def test_preview_version(self):
        response = self.client.get("/api/report-management/versions/10/preview")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        self.assertTrue(zipfile.is_zipfile(io.BytesIO(response.data)))
        response.close()

    def test_download_version(self):
        response = self.client.get("/api/report-management/versions/10/download")

        self.assertEqual(response.status_code, 200)
        self.assertIn("attachment", response.headers["Content-Disposition"])
        response.close()

    def test_version_file_returns_404(self):
        missing_version = self.client.get("/api/report-management/versions/999/preview")
        self.assertEqual(missing_version.status_code, 404)
        self.assertEqual(missing_version.json, {"message": "未找到该报告版本"})

        self.preview_path.unlink()
        missing_file = self.client.get("/api/report-management/versions/10/download")
        self.assertEqual(missing_file.status_code, 404)
        self.assertEqual(missing_file.json, {"message": "报告文件不存在"})

    def test_get_audit_detail(self):
        response = self.client.get("/api/report-management/audits/99")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        self.assertEqual(response.json["summary"]["结论"], "不通过")
        self.assertEqual(response.json["resultData"]["data"][0]["检查点"], "检测章节应用指标统计与分析是否空缺")

    def test_get_audit_detail_returns_404(self):
        response = self.client.get("/api/report-management/audits/404")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json, {"message": "未找到该审核记录"})

    def test_get_audit_events_incrementally(self):
        response = self.client.get("/api/report-management/audits/99/events?afterId=10")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        self.assertEqual(response.json["lastEventId"], 11)
        self.assertEqual(response.json["events"][0]["type"], "model")

    def test_get_audit_events_rejects_invalid_after_id(self):
        response = self.client.get("/api/report-management/audits/99/events?afterId=invalid")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json, {"message": "afterId 必须是整数"})

    def test_get_report_conversation(self):
        response = self.client.get("/api/report-management/audits/reports/1/conversation")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["versions"][0]["resultText"].splitlines()[0], "审核结论：不通过")

    def test_retry_version_audit(self):
        response = self.client.post("/api/report-management/audits/reports/1/versions/10/retry")

        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json["auditStatus"], "pending")
        self.assertEqual(response.json["auditType"], "revision")
        self.assertTrue(response.json["created"])

    def test_report_repository_writes_explicit_audit_types(self):
        from app.repositories.reports import MySqlReportRepository

        initial_cursor = RecordingCursor()
        initial_result = MySqlReportRepository(RecordingDatabase(initial_cursor)).register_initial_report(
            {
                "systemId": "credit-card-center",
                "title": "初始报告",
                "reportMonth": "2026年08月",
                "filePath": "/tmp/initial.docx",
                "fileName": "initial.docx",
                "fileSize": 100,
                "generationId": "initial-001",
            }
        )
        uploaded_cursor = RecordingCursor()
        uploaded_result = MySqlReportRepository(RecordingDatabase(uploaded_cursor)).create_uploaded_version(
            {
                "reportId": 1,
                "versionNo": 2,
                "fileName": "revision.docx",
                "filePath": "/tmp/revision.docx",
                "fileSize": 200,
                "uploader": "张三",
            }
        )

        initial_insert = next(
            item for item in initial_cursor.executions if item[0].startswith("INSERT INTO capability_report_audit ")
        )
        uploaded_insert = next(
            item for item in uploaded_cursor.executions if item[0].startswith("INSERT INTO capability_report_audit ")
        )
        self.assertEqual(initial_insert[1], [1, 9, "initial"])
        self.assertEqual(uploaded_insert[1], [1, 11, "revision"])
        self.assertEqual(initial_result["auditType"], "initial")
        self.assertEqual(uploaded_result["auditType"], "revision")

    def test_batch_registration_returns_current_audit_while_running(self):
        from app.repositories.reports import MySqlReportRepository

        cursor = RecordingCursor(
            latest_report_version={
                "id": 9,
                "version_no": 1,
                "source": "batch",
                "audit_status": "running",
                "audit_id": 88,
            }
        )

        result = MySqlReportRepository(RecordingDatabase(cursor)).register_initial_report(
            self._batch_registration_payload("batch-002")
        )

        self.assertFalse(result["created"])
        self.assertTrue(result["deferred"])
        self.assertEqual(result["code"], "AUDIT_IN_PROGRESS")
        self.assertEqual(result["auditId"], 88)
        self.assertFalse(
            any(
                sql.startswith("INSERT INTO capability_report_version")
                for sql, _ in cursor.executions
            )
        )

    def test_same_generation_is_idempotent_and_returns_state_action(self):
        from app.repositories.reports import MySqlReportRepository

        cursor = RecordingCursor(
            existing_generation={
                "id": 9,
                "version_no": 1,
                "audit_id": 88,
                "audit_status": "failed",
            }
        )

        result = MySqlReportRepository(RecordingDatabase(cursor)).register_initial_report(
            self._batch_registration_payload("batch-001")
        )

        self.assertFalse(result["created"])
        self.assertEqual(result["code"], "INITIAL_AUDIT_FAILED")
        self.assertEqual(result["nextAction"], "regenerate")
        self.assertFalse(
            any(
                sql.startswith("INSERT INTO capability_report_version")
                for sql, _ in cursor.executions
            )
        )

    def test_batch_registration_allows_failed_and_error_versions(self):
        from app.repositories.reports import MySqlReportRepository

        for status in ("failed", "error"):
            with self.subTest(status=status):
                cursor = RecordingCursor(
                    latest_report_version={
                        "id": 9,
                        "version_no": 1,
                        "source": "batch",
                        "audit_status": status,
                        "audit_id": 88,
                    }
                )
                result = MySqlReportRepository(
                    RecordingDatabase(cursor)
                ).register_initial_report(self._batch_registration_payload(f"batch-{status}"))

                self.assertTrue(result["created"])
                self.assertEqual(result["versionNo"], 2)

    def test_passed_batch_registration_stops_unless_debug_mode_is_enabled(self):
        from app.repositories.reports import MySqlReportRepository

        latest_version = {
            "id": 9,
            "version_no": 1,
            "source": "batch",
            "audit_status": "passed",
            "audit_id": 88,
        }
        stopped = MySqlReportRepository(
            RecordingDatabase(RecordingCursor(latest_report_version=latest_version))
        ).register_initial_report(self._batch_registration_payload("batch-stopped"))

        debug_payload = self._batch_registration_payload("batch-debug")
        debug_payload["debugReregistration"] = True
        continued = MySqlReportRepository(
            RecordingDatabase(RecordingCursor(latest_report_version=latest_version))
        ).register_initial_report(debug_payload)

        self.assertFalse(stopped["created"])
        self.assertEqual(stopped["code"], "INITIAL_AUDIT_PASSED")
        self.assertEqual(stopped["nextAction"], "stop")
        self.assertTrue(continued["created"])
        self.assertEqual(continued["versionNo"], 2)

    def test_uploaded_version_number_is_allocated_while_report_is_locked(self):
        from app.repositories.reports import MySqlReportRepository

        cursor = RecordingCursor(latest_version_no=4)

        result = MySqlReportRepository(RecordingDatabase(cursor)).create_uploaded_version(
            {
                "reportId": 1,
                "fileName": "revision.docx",
                "filePath": "/tmp/revision.docx",
                "fileSize": 200,
                "uploader": "张三",
            }
        )

        statements = [item[0] for item in cursor.executions]
        report_lock_index = next(
            index for index, sql in enumerate(statements) if sql.endswith("FOR UPDATE")
        )
        version_query_index = next(
            index
            for index, sql in enumerate(statements)
            if "SELECT COALESCE(MAX(version_no), 0) AS latest_version_no" in sql
        )
        version_insert = next(
            item
            for item in cursor.executions
            if item[0].startswith("INSERT INTO capability_report_version")
        )
        self.assertLess(report_lock_index, version_query_index)
        self.assertEqual(version_insert[1][1], 5)
        self.assertEqual(result["versionNo"], 5)

    def test_repository_rejects_uploaded_version_when_initial_audit_failed(self):
        from app.repositories.reports import MySqlReportRepository, ReportNotReadyError

        cursor = RecordingCursor(initial_audit_status="failed")

        with self.assertRaises(ReportNotReadyError) as raised:
            MySqlReportRepository(RecordingDatabase(cursor)).create_uploaded_version(
                {
                    "reportId": 1,
                    "fileName": "revision.docx",
                    "filePath": "/tmp/revision.docx",
                    "fileSize": 200,
                    "uploader": "张三",
                }
            )

        self.assertEqual(raised.exception.code, "INITIAL_AUDIT_NOT_PASSED")
        self.assertFalse(
            any(
                sql.startswith("INSERT INTO capability_report_version")
                for sql, _ in cursor.executions
            )
        )

    def test_repository_finalization_requires_passed_uploaded_version(self):
        from app.repositories.reports import MySqlReportRepository, ReportNotReadyError

        cases = [
            ("initial", "passed", "REVISION_REQUIRED"),
            ("uploaded", "failed", "REVISION_AUDIT_NOT_PASSED"),
        ]
        for version_type, audit_status, expected_code in cases:
            with self.subTest(version_type=version_type, audit_status=audit_status):
                cursor = RecordingCursor(
                    latest_version_type=version_type,
                    latest_version_audit_status=audit_status,
                )
                with self.assertRaises(ReportNotReadyError) as raised:
                    MySqlReportRepository(RecordingDatabase(cursor)).finalize_report(
                        1, "张三"
                    )
                self.assertEqual(raised.exception.code, expected_code)
                self.assertFalse(
                    any(
                        sql.startswith("UPDATE capability_report_log")
                        for sql, _ in cursor.executions
                    )
                )

    def test_report_repository_rejects_unknown_audit_type(self):
        from app.repositories.reports import MySqlReportRepository

        cursor = RecordingCursor()

        with self.assertRaisesRegex(ValueError, "不支持的审核类型"):
            MySqlReportRepository(None)._create_pending_audit(cursor, 1, 9, "other")

        self.assertEqual(cursor.executions, [])

    def test_retry_preserves_latest_audit_type(self):
        from app.repositories.audits import MySqlAuditRepository

        cursor = RecordingCursor(
            version_type="initial",
            latest_audit={"id": 90, "status": "failed", "audit_type": "revision"},
        )

        result = MySqlAuditRepository(RecordingDatabase(cursor)).retry_version_audit(1, 10)

        audit_insert = next(
            item for item in cursor.executions if item[0].startswith("INSERT INTO capability_report_audit ")
        )
        queued_event = next(
            item for item in cursor.executions if item[0].startswith("INSERT INTO capability_report_audit_event")
        )
        self.assertEqual(audit_insert[1], [1, 10, "revision"])
        self.assertEqual(result["auditType"], "revision")
        self.assertIn("修订审核", queued_event[1][-1])

    def test_retry_persists_legacy_null_type_on_active_audit(self):
        from app.repositories.audits import MySqlAuditRepository

        for status in ("pending", "running"):
            with self.subTest(status=status):
                cursor = RecordingCursor(
                    version_type="uploaded",
                    latest_audit={"id": 90, "status": status, "audit_type": None},
                )

                result = MySqlAuditRepository(RecordingDatabase(cursor)).retry_version_audit(1, 10)

                type_update = next(
                    item
                    for item in cursor.executions
                    if item[0].startswith("UPDATE capability_report_audit SET audit_type")
                )
                self.assertEqual(type_update[1], ["revision", 90])
                self.assertFalse(
                    any(
                        item[0].startswith("INSERT INTO capability_report_audit ")
                        for item in cursor.executions
                    )
                )
                self.assertEqual(result["auditType"], "revision")
                self.assertFalse(result["created"])

    def test_retry_falls_back_to_version_type_for_completed_legacy_audit(self):
        from app.repositories.audits import MySqlAuditRepository

        cursor = RecordingCursor(
            version_type="uploaded",
            latest_audit={"id": 90, "status": "failed", "audit_type": None},
        )

        result = MySqlAuditRepository(RecordingDatabase(cursor)).retry_version_audit(1, 10)

        audit_insert = next(
            item for item in cursor.executions if item[0].startswith("INSERT INTO capability_report_audit ")
        )
        self.assertEqual(audit_insert[1], [1, 10, "revision"])
        self.assertEqual(result["auditType"], "revision")

    def test_retry_does_not_overwrite_valid_type_on_active_audit(self):
        from app.repositories.audits import MySqlAuditRepository

        cursor = RecordingCursor(
            version_type="uploaded",
            latest_audit={"id": 90, "status": "pending", "audit_type": "initial"},
        )

        result = MySqlAuditRepository(RecordingDatabase(cursor)).retry_version_audit(1, 10)

        self.assertFalse(
            any(
                item[0].startswith("UPDATE capability_report_audit SET audit_type")
                for item in cursor.executions
            )
        )
        self.assertEqual(result["auditType"], "initial")

    def test_retry_version_audit_returns_404_for_missing_version(self):
        response = self.client.post("/api/report-management/audits/reports/1/versions/999/retry")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json, {"message": "未找到该报告版本"})

    def test_list_and_create_agent_messages(self):
        listed = self.client.get("/api/report-management/audits/reports/1/versions/10/messages")
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(listed.json["messages"][0]["role"], "user")
        self.assertFalse(listed.json["processing"])

        created = self.client.post(
            "/api/report-management/audits/reports/1/versions/10/messages",
            json={"content": "请给出具体修改建议"},
        )
        self.assertEqual(created.status_code, 202)
        self.assertEqual(created.json["assistantMessageId"], 3)
        self.assertEqual(self.repository.created_agent_exchange, (1, 10, "请给出具体修改建议"))

    def test_create_agent_message_validates_content_and_version(self):
        empty = self.client.post(
            "/api/report-management/audits/reports/1/versions/10/messages", json={"content": "  "}
        )
        self.assertEqual(empty.status_code, 400)
        self.assertEqual(empty.json, {"message": "对话内容不能为空"})

        missing = self.client.post(
            "/api/report-management/audits/reports/1/versions/999/messages", json={"content": "请分析"}
        )
        self.assertEqual(missing.status_code, 404)
        self.assertEqual(missing.json, {"message": "未找到该报告版本"})

    def test_manage_audit_checkpoints(self):
        listed = self.client.get("/api/report-management/audit-checkpoints")
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(listed.json["rows"][0]["name"], "章节完整性")

        created = self.client.post(
            "/api/report-management/audit-checkpoints",
            json={"name": "指标检查", "content": "检查指标是否异常", "sortOrder": 20, "enabled": True},
        )
        self.assertEqual(created.status_code, 201)
        self.assertEqual(created.json["id"], 2)

        updated = self.client.put(
            "/api/report-management/audit-checkpoints/1",
            json={"name": "章节检查", "content": "检查章节内容", "sortOrder": 5, "enabled": False},
        )
        self.assertEqual(updated.status_code, 200)
        self.assertFalse(updated.json["enabled"])

    def test_shared_ai_config_masks_key(self):
        response = self.client.get("/api/report-management/ai-config")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        self.assertEqual(
            set(response.json),
            {"id", "apiUrl", "modelName", "apiKeyMasked", "apiKeyConfigured"},
        )
        self.assertNotIn("apiKey", response.json)
        self.assertTrue(response.json["apiKeyConfigured"])

    def test_update_shared_ai_config_keeps_blank_key(self):
        response = self.client.put(
            "/api/report-management/ai-config",
            json={
                "apiUrl": "https://example.test/v1",
                "modelName": "new-model",
                "apiKey": None,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.repository.updated_ai_config_payload["apiKey"], "")
        self.assertNotIn("apiKey", response.json)
        self.assertTrue(response.json["apiKeyConfigured"])

    def test_ai_config_rejects_non_object_json_and_invalid_field_types(self):
        for payload in (
            [],
            1,
            {"apiUrl": 1, "modelName": "model", "apiKey": "key"},
            {"apiUrl": "https://example.test", "modelName": [], "apiKey": "key"},
            {"apiUrl": "https://example.test", "modelName": "model", "apiKey": []},
        ):
            with self.subTest(payload=payload):
                response = self.client.put("/api/report-management/ai-config", json=payload)

                self.assertEqual(response.status_code, 400)
                self.assertIn("message", response.json)

    def test_prompt_types_are_independent(self):
        initial = self.client.get("/api/report-management/audit-prompts/initial/active")
        revision = self.client.get("/api/report-management/audit-prompts/revision/active")

        self.assertEqual(initial.status_code, 200)
        self.assertEqual(revision.status_code, 200)
        self.assertEqual(initial.json["auditType"], "initial")
        self.assertEqual(revision.json["auditType"], "revision")

    def test_unknown_prompt_type_is_rejected(self):
        response = self.client.get("/api/report-management/audit-prompts/other/active")

        self.assertEqual(response.status_code, 404)

    def test_get_active_prompt(self):
        self.repository.active_prompts["revision"]["futureSecret"] = "must-not-leak"
        response = self.client.get("/api/report-management/audit-prompts/active")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        self.assertEqual(response.headers["Deprecation"], "true")
        self.assertEqual(
            set(response.json),
            {"id", "name", "auditType", "promptContent", "version", "enabled", "createTime", "updateTime"},
        )
        self.assertEqual(response.json["version"], 2)
        self.assertEqual(response.json["auditType"], "revision")
        self.assertTrue(response.json["enabled"])
        self.assertNotIn("apiKey", response.json)

    def test_get_active_prompt_returns_404_when_missing(self):
        self.repository.active_prompts["revision"] = None

        response = self.client.get("/api/report-management/audit-prompts/active")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json, {"message": "未配置启用的审核提示词"})

    def test_create_prompt_version(self):
        response = self.client.post(
            "/api/report-management/audit-prompts",
            json={
                "name": "默认审核提示词",
                "promptContent": "新的审核提示词",
            },
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.headers["Deprecation"], "true")
        self.assertEqual(response.json["version"], 3)
        self.assertEqual(response.json["auditType"], "revision")
        self.assertNotIn("apiKey", response.json)
        self.assertEqual(
            self.repository.created_prompt_payload,
            {
                "auditType": "revision",
                "name": "默认审核提示词",
                "promptContent": "新的审核提示词",
            },
        )

    def test_create_initial_prompt_version(self):
        response = self.client.post(
            "/api/report-management/audit-prompts/initial",
            json={"name": "初始审核提示词", "promptContent": "新的初始提示词"},
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json["auditType"], "initial")
        self.assertEqual(self.repository.created_prompt_payload["auditType"], "initial")

    def test_create_prompt_version_requires_content(self):
        response = self.client.post("/api/report-management/audit-prompts", json={"promptContent": " "})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.headers["Deprecation"], "true")
        self.assertEqual(response.json, {"message": "提示词内容不能为空"})

    def test_prompt_creation_repository_error_is_structured_and_only_legacy_is_deprecated(self):
        self.app.config["PROPAGATE_EXCEPTIONS"] = False
        self.repository.prompt_error = RuntimeError("SELECT api_key FROM internal_table")

        legacy = self.client.post(
            "/api/report-management/audit-prompts",
            json={"name": "修订审核提示词", "promptContent": "内容"},
        )
        typed = self.client.post(
            "/api/report-management/audit-prompts/initial",
            json={"name": "初始审核提示词", "promptContent": "内容"},
        )

        self.assertEqual(legacy.status_code, 500)
        self.assertEqual(legacy.headers["Deprecation"], "true")
        self.assertEqual(legacy.json, {"message": "保存审核提示词失败"})
        self.assertNotIn("api_key", legacy.get_data(as_text=True))
        self.assertNotIn("internal_table", legacy.get_data(as_text=True))
        self.assertEqual(typed.status_code, 500)
        self.assertNotIn("Deprecation", typed.headers)
        self.assertEqual(typed.json, {"message": "保存审核提示词失败"})

    def test_prompt_posts_reject_non_object_json_and_invalid_field_types(self):
        for url, payload, deprecated in (
            ("/api/report-management/audit-prompts/initial", [], False),
            ("/api/report-management/audit-prompts/initial", 1, False),
            ("/api/report-management/audit-prompts/initial", {"promptContent": 1}, False),
            ("/api/report-management/audit-prompts/initial", {"name": 1, "promptContent": "内容"}, False),
            ("/api/report-management/audit-prompts", [], True),
        ):
            with self.subTest(url=url, payload=payload):
                response = self.client.post(url, json=payload)

                self.assertEqual(response.status_code, 400)
                self.assertIn("message", response.json)
                if deprecated:
                    self.assertEqual(response.headers["Deprecation"], "true")


if __name__ == "__main__":
    unittest.main()
