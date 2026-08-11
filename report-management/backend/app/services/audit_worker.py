from __future__ import annotations

from pathlib import Path
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
            self.repository.mark_audit_error(job["auditId"], job["versionId"], "未配置启用的审核提示词")
            return {"processed": True, "auditId": job["auditId"], "status": "error"}

        self.repository.mark_audit_running(job["auditId"], prompt)
        try:
            if not Path(job["filePath"]).is_file():
                raise FileNotFoundError("报告文件不存在")
            audit_input = build_audit_input(job)
            result = self.model_client.audit_report(prompt, audit_input)
            self.repository.mark_audit_complete(job["auditId"], job["versionId"], result)
            return {"processed": True, "auditId": job["auditId"], "status": "completed"}
        except Exception as error:
            self.repository.mark_audit_error(job["auditId"], job["versionId"], str(error))
            return {"processed": True, "auditId": job["auditId"], "status": "error"}
