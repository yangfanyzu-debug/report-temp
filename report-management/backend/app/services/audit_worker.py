from __future__ import annotations

from pathlib import Path
from time import monotonic
from typing import Any

from .audit_input import build_audit_input


class AuditWorker:
    def __init__(self, repository: Any, model_client: Any):
        self.repository = repository
        self.model_client = model_client

    def run_once(self) -> dict[str, Any]:
        job = self.repository.next_pending_audit()
        if job is None:
            return {"processed": False, "reason": "no_pending_audit"}

        prompt = self.repository.get_active_prompt()
        if prompt is None:
            self.repository.append_audit_event(job["auditId"], "error", "configuration", "未配置启用的审核提示词")
            self.repository.mark_audit_error(job["auditId"], job["versionId"], "未配置启用的审核提示词")
            return {"processed": True, "auditId": job["auditId"], "status": "error"}

        self.repository.mark_audit_running(job["auditId"], prompt)
        self.repository.append_audit_event(job["auditId"], "system", "started", "AI审核任务已开始")
        try:
            if not Path(job["filePath"]).is_file():
                raise FileNotFoundError("报告文件不存在")
            self.repository.append_audit_event(job["auditId"], "system", "extracting", "正在解析DOCX中的章节、正文和表格")
            checkpoints = self.repository.get_active_checkpoints()
            self.repository.save_checkpoint_snapshot(job["auditId"], checkpoints)
            audit_input = build_audit_input(job, checkpoints)
            paragraph_count = len(audit_input["document"].get("paragraphs", []))
            table_count = len(audit_input["document"].get("tables", []))
            self.repository.append_audit_event(
                job["auditId"],
                "system",
                "extracted",
                f"文档解析完成，共提取{paragraph_count}段正文、{table_count}个表格",
            )
            self.repository.append_audit_event(
                job["auditId"],
                "system",
                "model",
                f"正在调用模型 {prompt['modelName']} 进行审核",
            )
            pending_chunks: list[str] = []
            pending_length = 0
            last_flush_at = monotonic()

            def handle_delta(delta: str) -> None:
                nonlocal pending_length, last_flush_at
                pending_chunks.append(delta)
                pending_length += len(delta)
                now = monotonic()
                if pending_length >= 300 or now - last_flush_at >= 0.8:
                    self.repository.append_audit_event(
                        job["auditId"], "model", "streaming", "".join(pending_chunks)
                    )
                    pending_chunks.clear()
                    pending_length = 0
                    last_flush_at = now

            result = self.model_client.audit_report(prompt, audit_input, on_delta=handle_delta)
            if pending_chunks:
                self.repository.append_audit_event(
                    job["auditId"], "model", "streaming", "".join(pending_chunks)
                )
            self.repository.append_audit_event(job["auditId"], "system", "saving", "模型输出完成，正在保存审核结果")
            self.repository.mark_audit_complete(job["auditId"], job["versionId"], result)
            conclusion = {"passed": "通过", "failed": "不通过", "completed": "已完成"}.get(result["conclusion"], "已完成")
            self.repository.append_audit_event(job["auditId"], "result", "completed", f"AI审核完成：{conclusion}")
            return {"processed": True, "auditId": job["auditId"], "status": "completed"}
        except Exception as error:
            self.repository.append_audit_event(job["auditId"], "error", "failed", str(error))
            self.repository.mark_audit_error(job["auditId"], job["versionId"], str(error))
            return {"processed": True, "auditId": job["auditId"], "status": "error"}
