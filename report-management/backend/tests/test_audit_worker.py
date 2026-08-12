from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.services.audit_input import build_audit_input  # noqa: E402
from app.services.agent_worker import AgentWorker  # noqa: E402
from app.services.audit_worker import AuditWorker  # noqa: E402
from app.services.deepseek_client import (  # noqa: E402
    chat_completions_url,
    parse_chat_stream,
    parse_model_result,
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
        self.checkpoints = [{"id": 1, "name": "章节完整性", "content": "检查章节", "sortOrder": 10, "enabled": True}]
        self.snapshots = []

    def next_pending_audit(self):
        return self.job

    def get_active_prompt(self):
        return self.prompt

    def mark_audit_running(self, audit_id, prompt):
        self.running.append((audit_id, prompt["version"]))

    def get_active_checkpoints(self):
        return self.checkpoints

    def save_checkpoint_snapshot(self, audit_id, checkpoints):
        self.snapshots.append((audit_id, checkpoints))

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
            "resultText": "审核结论：通过\n\n## 审核总结\n未发现明显问题。",
            "conclusion": "passed",
        }
        self.calls = []

    def audit_report(self, prompt, audit_input, on_delta=None):
        self.calls.append((prompt, audit_input))
        if on_delta:
            on_delta("审核结论：通过\n")
            on_delta("未发现明显问题。")
        return self.result

    def chat_report_agent(self, prompt, report_context, history, question, on_delta=None):
        self.calls.append((prompt, report_context, history, question))
        if on_delta:
            on_delta("建议将ES服务器数量")
            on_delta("统一为14台。")
        return "建议将ES服务器数量统一为14台。"


class FakeAgentRepository:
    def __init__(self, job=None, prompt=None):
        self.job = job
        self.prompt = prompt
        self.running = []
        self.chunks = []
        self.completed = []
        self.errors = []

    def next_pending_agent_message(self):
        return self.job

    def get_active_prompt(self):
        return self.prompt

    def mark_agent_message_running(self, message_id, model_name):
        self.running.append((message_id, model_name))

    def append_agent_message_content(self, message_id, content):
        self.chunks.append((message_id, content))

    def mark_agent_message_complete(self, message_id):
        self.completed.append(message_id)

    def mark_agent_message_error(self, message_id, message):
        self.errors.append((message_id, message))


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

    def test_parse_model_result_extracts_optional_conclusion(self):
        self.assertEqual(parse_model_result("审核结论：通过\n内容完整")["conclusion"], "passed")
        self.assertEqual(parse_model_result("审核结论：不通过\n存在问题")["conclusion"], "failed")
        self.assertEqual(parse_model_result("审核工作已经完成")["conclusion"], "completed")

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
        self.assertEqual(repository.snapshots[0][1][0]["name"], "章节完整性")
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

    def test_agent_worker_streams_and_completes_reply(self):
        with tempfile.TemporaryDirectory() as temporary_dir:
            path = Path(temporary_dir) / "报告.docx"
            write_docx(path)
            job = {
                "messageId": 21,
                "filePath": str(path),
                "fileName": "报告.docx",
                "systemId": "capacity",
                "title": "容量报告",
                "reportMonth": "2026年08月",
                "question": "ES服务器数量应该怎么改？",
                "auditResult": "审核结论：不通过",
                "checkpoints": [],
                "history": [{"role": "user", "content": "报告有什么问题？"}],
            }
            prompt = {"modelName": "deepseek-chat", "promptContent": "请审核"}
            repository = FakeAgentRepository(job, prompt)
            model_client = FakeModelClient()

            result = AgentWorker(repository, model_client).run_once()

        self.assertEqual(result, {"processed": True, "messageId": 21, "status": "completed"})
        self.assertEqual(repository.running, [(21, "deepseek-chat")])
        self.assertEqual("".join(chunk for _, chunk in repository.chunks), "建议将ES服务器数量统一为14台。")
        self.assertEqual(repository.completed, [21])
        self.assertEqual(model_client.calls[0][3], "ES服务器数量应该怎么改？")

    def test_agent_worker_marks_error_when_model_is_missing(self):
        repository = FakeAgentRepository({"messageId": 22})

        result = AgentWorker(repository, FakeModelClient()).run_once()

        self.assertEqual(result, {"processed": True, "messageId": 22, "status": "error"})
        self.assertEqual(repository.errors, [(22, "未配置启用的AI模型")])


if __name__ == "__main__":
    unittest.main()
