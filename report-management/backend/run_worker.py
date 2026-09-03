from __future__ import annotations

import argparse
import logging
import time

from app.config import load_settings
from app.database import Database
from app.logging_config import configure_logging
from app.repositories.audits import MySqlAuditRepository
from app.repositories.jira import MySqlJiraRepository
from app.services.agent_worker import AgentWorker
from app.services.audit_worker import AuditWorker
from app.services.deepseek_client import DeepSeekClient
from app.services.jira_client import JiraClient
from app.services.jira_worker import JiraWorker


logger = logging.getLogger("report_management.worker")


def process_next(audit_worker, agent_worker, jira_worker):
    results = {
        "audit": audit_worker.run_once(),
        "agent": agent_worker.run_once(),
        "jira": jira_worker.run_once(),
    }
    return {
        "processed": any(result.get("processed", False) for result in results.values()),
        "results": results,
    }


def should_wait(result: dict) -> bool:
    return not result.get("processed", False)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run report AI audit worker")
    parser.add_argument("--once", action="store_true", help="process one worker cycle and exit")
    args = parser.parse_args()

    settings = load_settings()
    configure_logging(settings.log_level)
    database = Database(settings)
    repository = MySqlAuditRepository(database)
    model_client = DeepSeekClient(settings)
    agent_worker = AgentWorker(repository, model_client)
    jira_creation_enabled = not settings.batch_debug_reregistration
    audit_worker = AuditWorker(
        repository, model_client, jira_creation_enabled=jira_creation_enabled
    )
    jira_worker = JiraWorker(
        MySqlJiraRepository(database),
        JiraClient(settings),
        enabled=jira_creation_enabled,
    )
    logger.info(
        "worker_started intervalSeconds=%s jiraConfigured=%s jiraEnabled=%s logLevel=%s",
        settings.worker_interval_seconds,
        jira_worker.client.configured,
        jira_creation_enabled,
        settings.log_level,
    )

    if args.once:
        try:
            result = process_next(audit_worker, agent_worker, jira_worker)
            logger.info("worker_once_result result=%s", result)
        except Exception:
            logger.exception("worker_once_failed")
            raise
        return

    while True:
        try:
            result = process_next(audit_worker, agent_worker, jira_worker)
        except Exception:
            logger.exception("worker_cycle_failed")
            time.sleep(settings.worker_interval_seconds)
            continue
        if result.get("processed"):
            logger.info("worker_cycle_processed result=%s", result)
        else:
            logger.debug("worker_idle reason=%s", result.get("reason", "unknown"))
        if should_wait(result):
            time.sleep(settings.worker_interval_seconds)


if __name__ == "__main__":
    main()
