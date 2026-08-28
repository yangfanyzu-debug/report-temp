from __future__ import annotations

from pathlib import Path
from time import monotonic
from typing import Any

from .audit_input import build_audit_input


class AgentWorker:
    def __init__(self, repository: Any, model_client: Any):
        self.repository = repository
        self.model_client = model_client

    def run_once(self) -> dict[str, Any]:
        job = self.repository.next_pending_agent_message()
        if job is None:
            return {"processed": False, "reason": "no_pending_agent_message"}

        try:
            model_config = self.repository.get_ai_config()
            if not model_config or not all(
                str(model_config.get(field) or "").strip()
                for field in ("apiUrl", "modelName", "apiKey")
            ):
                raise RuntimeError("未配置共用模型连接")

            audit_type = job.get("auditType")
            if audit_type not in {"initial", "revision"}:
                raise RuntimeError("不支持的审核类型")
            prompt = (
                self.repository.get_prompt_by_id(job["promptId"])
                if job.get("promptId")
                else None
            )
            if prompt is None:
                prompt = self.repository.get_active_prompt(audit_type)
            if prompt is None:
                label = "初始" if audit_type == "initial" else "修订"
                raise RuntimeError(f"未配置启用的{label}审核提示词")

            self.repository.mark_agent_message_running(
                job["messageId"], model_config["modelName"]
            )
            if not Path(job["filePath"]).is_file():
                raise FileNotFoundError("报告文件不存在")
            context = build_audit_input(job)
            context["latestAuditResult"] = job.get("auditResult") or "暂无审核结果"
            pending_chunks: list[str] = []
            pending_length = 0
            last_flush_at = monotonic()

            def handle_delta(delta: str) -> None:
                nonlocal pending_length, last_flush_at
                pending_chunks.append(delta)
                pending_length += len(delta)
                now = monotonic()
                if pending_length >= 200 or now - last_flush_at >= 0.6:
                    self.repository.append_agent_message_content(job["messageId"], "".join(pending_chunks))
                    pending_chunks.clear()
                    pending_length = 0
                    last_flush_at = now

            self.model_client.chat_report_agent(
                model_config,
                prompt,
                context,
                job.get("history", []),
                job["question"],
                on_delta=handle_delta,
            )
            if pending_chunks:
                self.repository.append_agent_message_content(job["messageId"], "".join(pending_chunks))
            self.repository.mark_agent_message_complete(job["messageId"])
            return {"processed": True, "messageId": job["messageId"], "status": "completed"}
        except Exception as error:
            self.repository.mark_agent_message_error(job["messageId"], str(error))
            return {"processed": True, "messageId": job["messageId"], "status": "error"}
