from __future__ import annotations

import io
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


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
        self.active_prompt = {
            "id": 1,
            "name": "默认审核提示词",
            "promptContent": "请审核报告",
            "version": 2,
            "enabled": True,
            "modelName": "deepseek-chat",
            "createTime": "2026-08-11 10:00:00",
            "updateTime": "2026-08-11 11:00:00",
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
                    "latestVersionId": 10,
                    "latestVersionNo": 2,
                    "latestVersionType": "uploaded",
                    "latestAuditId": 99,
                    "latestAuditStatus": "failed",
                    "latestAuditConclusion": "不通过",
                    "latestAuditSuggestion": "请修正ES服务器数量",
                    "createTime": "2026-08-11 10:30:00",
                }
            ],
            "total": 1,
        }

    def get_report_detail(self, report_id):
        return self.detail if report_id == 1 else None

    def register_initial_report(self, payload):
        self.registered_payload = payload
        return {"reportId": 1, "versionId": 9, "auditId": 88, "auditStatus": "pending"}

    def prepare_uploaded_version(self, report_id):
        if report_id != 1:
            return None
        return {
            "reportId": 1,
            "systemId": "credit-card-center",
            "title": "中信银行信用卡中心授权交易资源分析报告",
            "reportMonth": "2025年08月",
            "nextVersionNo": 3,
        }

    def create_uploaded_version(self, payload):
        self.created_upload_payload = payload
        return {"reportId": 1, "versionId": 11, "versionNo": 3, "auditId": 100, "auditStatus": "pending"}

    def get_version_file(self, version_id):
        if version_id != 10:
            return None
        return self.version_file

    def get_audit_detail(self, audit_id):
        return self.audit_detail if audit_id == 99 else None

    def get_active_prompt(self):
        return self.active_prompt

    def create_prompt_version(self, payload):
        self.created_prompt_payload = payload
        return {
            "id": 2,
            "name": payload["name"],
            "promptContent": payload["promptContent"],
            "version": 3,
            "enabled": True,
            "modelName": payload["modelName"],
            "createTime": "2026-08-11 12:00:00",
            "updateTime": "2026-08-11 12:00:00",
        }


class ReportRoutesTest(unittest.TestCase):
    def setUp(self):
        self.storage = tempfile.TemporaryDirectory()
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
            }
        )
        self.client = self.app.test_client()

    def tearDown(self):
        self.storage.cleanup()

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
        self.assertEqual(response.json["rows"][0]["latestAuditConclusion"], "不通过")
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
            },
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json, {"reportId": 1, "versionId": 9, "auditId": 88, "auditStatus": "pending"})
        self.assertEqual(self.repository.registered_payload["source"], "batch")

    def test_register_initial_report_requires_fields(self):
        response = self.client.post("/api/report-management/reports/register", json={"systemId": "x"})

        self.assertEqual(response.status_code, 400)
        self.assertIn("缺少必要参数", response.json["message"])

    def test_upload_report_version_creates_versioned_file(self):
        response = self.client.post(
            "/api/report-management/reports/1/versions",
            data={"file": (make_docx(), "报告 修订版.docx"), "uploader": "张三"},
            content_type="multipart/form-data",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json["versionNo"], 3)
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

    def test_get_active_prompt(self):
        response = self.client.get("/api/report-management/audit-prompts/active")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        self.assertEqual(response.json["version"], 2)
        self.assertTrue(response.json["enabled"])

    def test_get_active_prompt_returns_404_when_missing(self):
        self.repository.active_prompt = None

        response = self.client.get("/api/report-management/audit-prompts/active")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json, {"message": "未配置启用的审核提示词"})

    def test_create_prompt_version(self):
        response = self.client.post(
            "/api/report-management/audit-prompts",
            json={
                "name": "默认审核提示词",
                "promptContent": "新的审核提示词",
                "modelName": "deepseek-reasoner",
            },
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json["version"], 3)
        self.assertEqual(response.json["modelName"], "deepseek-reasoner")
        self.assertEqual(
            self.repository.created_prompt_payload,
            {
                "name": "默认审核提示词",
                "promptContent": "新的审核提示词",
                "modelName": "deepseek-reasoner",
            },
        )

    def test_create_prompt_version_requires_content(self):
        response = self.client.post("/api/report-management/audit-prompts", json={"promptContent": " "})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json, {"message": "提示词内容不能为空"})


if __name__ == "__main__":
    unittest.main()
