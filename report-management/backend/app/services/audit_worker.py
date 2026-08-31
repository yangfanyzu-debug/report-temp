from __future__ import annotations

import logging
from pathlib import Path
from time import monotonic
from typing import Any

from .audit_input import build_audit_input


logger = logging.getLogger(__name__)


class AuditConfigurationError(RuntimeError):
    pass


class AuditWorker:
    def __init__(self, repository: Any, model_client: Any):
        self.repository = repository
        self.model_client = model_client

    def run_once(self) -> dict[str, Any]:
        job = self.repository.next_pending_audit()
        if job is None:
            return {"processed": False, "reason": "no_pending_audit"}

        try:
            model_config = self.repository.get_ai_config()
            required_config_fields = ("apiUrl", "modelName", "apiKey")
            if not model_config or not all(
                str(model_config.get(field) or "").strip() for field in required_config_fields
            ):
                raise AuditConfigurationError("未配置共用模型连接")

            audit_type_labels = {"initial": "初始", "revision": "修订"}
            audit_type = job.get("auditType")
            if audit_type not in audit_type_labels:
                raise AuditConfigurationError("不支持的审核类型")

            prompt = self.repository.get_active_prompt(audit_type)
            if prompt is None:
                raise AuditConfigurationError(
                    f"未配置启用的{audit_type_labels[audit_type]}审核提示词"
                )

            self.repository.set_audit_execution_context(
                job["auditId"], prompt, model_config
            )
            self.repository.append_audit_event(
                job["auditId"], "system", "started", "AI审核任务已开始"
            )
            if not Path(job["filePath"]).is_file():
                raise FileNotFoundError("报告文件不存在")
            self.repository.append_audit_event(job["auditId"], "system", "extracting", "正在解析DOCX中的章节、正文和表格")
            audit_input = build_audit_input(job)
            audit_input.pop("checkpoints", None)
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
                f"正在调用模型 {model_config['modelName']} 进行审核",
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

            runtime_prompt = {**prompt, "auditType": audit_type}
            result = self.model_client.audit_report(
                model_config, runtime_prompt, audit_input, on_delta=handle_delta
            )
            if pending_chunks:
                self.repository.append_audit_event(
                    job["auditId"], "model", "streaming", "".join(pending_chunks)
                )
            if (
                audit_type == "initial"
                and result["conclusion"] == "passed"
                and not result.get("jiraTitle")
            ):
                raise RuntimeError("AI初审通过但未生成JIRA标题")
            self.repository.append_audit_event(job["auditId"], "system", "saving", "模型输出完成，正在保存审核结果")
            self.repository.mark_audit_complete(job["auditId"], job["versionId"], result)
            if audit_type == "initial" and result["conclusion"] == "passed":
                self.repository.queue_jira_creation(
                    job["reportId"], job["versionId"], job["auditId"]
                )
            conclusion = {"passed": "通过", "failed": "不通过", "completed": "已完成"}.get(result["conclusion"], "已完成")
            self.repository.append_audit_event(job["auditId"], "result", "completed", f"AI审核完成：{conclusion}")
            return {"processed": True, "auditId": job["auditId"], "status": "completed"}
        except Exception as error:
            return self._handle_error(job, error)

    def _handle_error(self, job: dict[str, Any], error: Exception) -> dict[str, Any]:
        message = str(error) or error.__class__.__name__
        phase = "configuration" if isinstance(error, AuditConfigurationError) else "failed"

        try:
            self.repository.mark_audit_error(job["auditId"], job["versionId"], message)
        except Exception:
            logger.exception(
                "记录审核错误状态失败 auditId=%s，原始错误：%s",
                job["auditId"],
                message,
            )
        try:
            self.repository.append_audit_event(
                job["auditId"], "error", phase, message
            )
        except Exception:
            logger.exception(
                "记录审核错误事件失败 auditId=%s，原始错误：%s",
                job["auditId"],
                message,
            )
        return {"processed": True, "auditId": job["auditId"], "status": "error"}
