from __future__ import annotations

from typing import Any


class JiraWorker:
    def __init__(self, repository: Any, client: Any):
        self.repository = repository
        self.client = client

    def run_once(self) -> dict[str, Any]:
        if not self.client.configured:
            return {"processed": False, "reason": "jira_not_configured"}
        with self.repository.processing_lock() as acquired:
            if not acquired:
                return {"processed": False, "reason": "jira_worker_busy"}
            self.repository.recover_interrupted_jobs()
            job = self.repository.next_pending_job()
            if job is None:
                return {"processed": False, "reason": "no_pending_jira"}
            try:
                jira_id = self.client.create_issue(job)
                self.repository.mark_created(job["reportId"], jira_id)
                return {
                    "processed": True,
                    "reportId": job["reportId"],
                    "jiraId": jira_id,
                    "status": "created",
                }
            except Exception as error:
                message = str(error) or error.__class__.__name__
                self.repository.mark_error(job["reportId"], message)
                return {
                    "processed": True,
                    "reportId": job["reportId"],
                    "status": "error",
                }
