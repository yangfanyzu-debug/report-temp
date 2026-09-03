from __future__ import annotations

import logging
from time import monotonic
from typing import Any


logger = logging.getLogger(__name__)


class JiraWorker:
    def __init__(self, repository: Any, client: Any, enabled: bool = True):
        self.repository = repository
        self.client = client
        self.enabled = enabled

    def run_once(self) -> dict[str, Any]:
        if not self.enabled:
            return {"processed": False, "reason": "jira_disabled_in_batch_debug_mode"}
        if not self.client.configured:
            return {"processed": False, "reason": "jira_not_configured"}
        with self.repository.processing_lock() as acquired:
            if not acquired:
                logger.debug("jira_worker_busy")
                return {"processed": False, "reason": "jira_worker_busy"}
            recovered = self.repository.recover_interrupted_jobs()
            if recovered:
                logger.warning("jira_jobs_recovered count=%s", recovered)
            job = self.repository.next_pending_job()
            if job is None:
                return {"processed": False, "reason": "no_pending_jira"}
            started_at = monotonic()
            logger.info(
                "jira_create_started reportId=%s versionId=%s auditId=%s systemId=%s attempt=%s",
                job.get("reportId"),
                job.get("versionId"),
                job.get("auditId"),
                job.get("systemId"),
                job.get("jiraAttempts"),
            )
            try:
                jira_id = self.client.create_issue(job)
                self.repository.mark_created(job["reportId"], jira_id)
                logger.info(
                    "jira_create_completed reportId=%s versionId=%s auditId=%s jiraId=%s durationMs=%s",
                    job["reportId"],
                    job.get("versionId"),
                    job.get("auditId"),
                    jira_id,
                    int((monotonic() - started_at) * 1000),
                )
                return {
                    "processed": True,
                    "reportId": job["reportId"],
                    "jiraId": jira_id,
                    "status": "created",
                }
            except Exception as error:
                message = str(error) or error.__class__.__name__
                logger.exception(
                    "jira_create_failed reportId=%s versionId=%s auditId=%s durationMs=%s error=%s",
                    job.get("reportId"),
                    job.get("versionId"),
                    job.get("auditId"),
                    int((monotonic() - started_at) * 1000),
                    message,
                )
                self.repository.mark_error(job["reportId"], message)
                return {
                    "processed": True,
                    "reportId": job["reportId"],
                    "status": "error",
                }
