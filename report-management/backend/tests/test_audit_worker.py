from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.services.audit_input import build_audit_input  # noqa: E402
from app.services.audit_worker import AuditWorker  # noqa: E402
from app.services.deepseek_client import (  # noqa: E402
    chat_completions_url,
    parse_chat_stream,
    parse_model_json,
    validate_audit_result,
)


def write_docx(path: Path) -> None:
    from docx import Document

    document = Document()
    document.add_heading("性能容量报告", level=1)
    document.add_paragraph("应用指标统计与分析内容完整。")
    table = document.add_table(rows=2, cols=2)
    table.cell(0, 0).text = "组件"
    table.cell(0, 1).text = "数量"
    table.cell(1, 0).text = "ES"
    table.cell(1, 1).text = "14"
    document.save(path)


class FakeAuditRepository:
    def __init__(self, job=None, prompt=None):
        self.job = job
        self.prompt = prompt
        self.running = []
        self.completed = []
        self.errors = []
        self.events = []

    def next_pending_audit(self):
        return self.job

    def get_active_prompt(self):
        return self.prompt

    def mark_audit_running(self, audit_id, prompt):
        self.running.append((audit_id, prompt["version"]))

    def mark_audit_complete(self, audit_id, version_id, result):
        self.completed.append((audit_id, version_id, result))

    def mark_audit_error(self, audit_id, version_id, message):
        self.errors.append((audit_id, version_id, message))

    def append_audit_event(self, audit_id, event_type, phase, content):
        self.events.append((audit_id, event_type, phase, content))
        return len(self.events)


class FakeModelClient:
    def __init__(self, result=None):
        self.result = result or {
            "summary": {"结论": "通过", "问题数量": 0, "建议": "无明显问题"},
            "data": [{"检查点": "章节完整性", "分析结果": "内容完整"}],
        }
        self.calls = []

    def audit_report(self, prompt, audit_input, on_delta=None):
        self.calls.append((prompt, audit_input))
        if on_delta:
            on_delta('{"summary":{"结论":"通过"},')
            on_delta('"data":[]}')
        return self.result


class AuditWorkerTest(unittest.TestCase):
    def test_build_audit_input_from_docx(self):
        with tempfile.TemporaryDirectory() as temporary_dir:
            path = Path(temporary_dir) / "报告.docx"
            write_docx(path)
            audit_input = build_audit_input(
                {
                    "systemId": "credit-card-center",
                    "title": "报告",
                    "reportMonth": "2025年08月",
                    "fileName": "报告.docx",
                    "filePath": str(path),
                }
            )

        self.assertEqual(audit_input["report"]["reportMonth"], "2025年08月")
        self.assertFalse(audit_input["scope"]["imagesAndChartsSemantic"])
        self.assertIn("性能容量报告", audit_input["document"]["paragraphs"])
        self.assertEqual(audit_input["document"]["tables"][0][1], ["ES", "14"])

    def test_parse_model_json_accepts_plain_and_fenced_json(self):
        plain = '{"summary":{"结论":"通过","问题数量":0,"建议":"无明显问题"},"data":[{"检查点":"A","分析结果":"B"}]}'
        fenced = f"```json\n{plain}\n```"

        self.assertEqual(parse_model_json(plain)["summary"]["结论"], "通过")
        self.assertEqual(parse_model_json(fenced)["data"][0]["检查点"], "A")

    def test_validate_audit_result_rejects_invalid_shape(self):
        with self.assertRaises(ValueError):
            validate_audit_result({"summary": {"结论": "未知"}, "data": []})
        with self.assertRaises(ValueError):
            validate_audit_result({"summary": {"结论": "通过"}, "data": [{"检查点": "A"}]})

    def test_chat_completions_url_accepts_base_or_full_url(self):
        self.assertEqual(
            chat_completions_url("https://ark.cn-beijing.volces.com/api/coding/v3"),
            "https://ark.cn-beijing.volces.com/api/coding/v3/chat/completions",
        )

    def test_parse_chat_stream_collects_content_deltas(self):
        deltas = []
        lines = [
            b'data: {"choices":[{"delta":{"role":"assistant"}}]}\n',
            b'data: {"choices":[{"delta":{"content":"{\\"summary\\":"}}]}\n',
            b'data: {"choices":[{"delta":{"content":"{}}"}}]}\n',
            b'data: [DONE]\n',
        ]

        content = parse_chat_stream(lines, deltas.append)

        self.assertEqual(content, '{"summary":{}}')
        self.assertEqual(deltas, ['{"summary":', '{}}'])
        self.assertEqual(
            chat_completions_url("https://ark.cn-beijing.volces.com/api/coding/v3/chat/completions"),
            "https://ark.cn-beijing.volces.com/api/coding/v3/chat/completions",
        )

    def test_worker_completes_pending_audit(self):
        with tempfile.TemporaryDirectory() as temporary_dir:
            path = Path(temporary_dir) / "报告.docx"
            write_docx(path)
            job = {
                "auditId": 99,
                "reportId": 1,
                "versionId": 10,
                "filePath": str(path),
                "fileName": "报告.docx",
                "systemId": "credit-card-center",
                "title": "报告",
                "reportMonth": "2025年08月",
            }
            prompt = {"id": 1, "version": 2, "modelName": "deepseek-chat", "promptContent": "请审核"}
            repository = FakeAuditRepository(job, prompt)
            model_client = FakeModelClient()

            result = AuditWorker(repository, model_client).run_once()

        self.assertEqual(result, {"processed": True, "auditId": 99, "status": "completed"})
        self.assertEqual(repository.running, [(99, 2)])
        self.assertEqual(repository.completed[0][0:2], (99, 10))
        self.assertEqual(model_client.calls[0][1]["report"]["systemId"], "credit-card-center")
        self.assertEqual(repository.events[0][2], "started")
        self.assertTrue(any(event[1] == "model" for event in repository.events))
        self.assertEqual(repository.events[-1][2], "completed")

    def test_worker_handles_no_pending_audit(self):
        result = AuditWorker(FakeAuditRepository(), FakeModelClient()).run_once()

        self.assertEqual(result, {"processed": False, "reason": "no_pending_audit"})

    def test_worker_marks_error_when_prompt_missing(self):
        repository = FakeAuditRepository({"auditId": 99, "versionId": 10})

        result = AuditWorker(repository, FakeModelClient()).run_once()

        self.assertEqual(result, {"processed": True, "auditId": 99, "status": "error"})
        self.assertEqual(repository.errors, [(99, 10, "未配置启用的审核提示词")])
        self.assertEqual(repository.events[-1][2], "configuration")

    def test_worker_marks_error_when_file_missing(self):
        job = {
            "auditId": 99,
            "versionId": 10,
            "filePath": "/not/exist.docx",
            "fileName": "报告.docx",
            "systemId": "credit-card-center",
            "title": "报告",
            "reportMonth": "2025年08月",
        }
        prompt = {"id": 1, "version": 2, "modelName": "deepseek-chat", "promptContent": "请审核"}
        repository = FakeAuditRepository(job, prompt)

        result = AuditWorker(repository, FakeModelClient()).run_once()

        self.assertEqual(result, {"processed": True, "auditId": 99, "status": "error"})
        self.assertEqual(repository.errors, [(99, 10, "报告文件不存在")])
        self.assertEqual(repository.events[-1][2], "failed")


if __name__ == "__main__":
    unittest.main()
