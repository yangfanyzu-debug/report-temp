from __future__ import annotations

import argparse
import time

from app.config import load_settings
from app.database import Database
from app.repositories.audits import MySqlAuditRepository
from app.repositories.jira import MySqlJiraRepository
from app.services.agent_worker import AgentWorker
from app.services.audit_worker import AuditWorker
from app.services.deepseek_client import DeepSeekClient
from app.services.jira_client import JiraClient
from app.services.jira_worker import JiraWorker


def process_next(audit_worker, agent_worker, jira_worker):
    audit_result = audit_worker.run_once()
    if audit_result["processed"]:
        return audit_result
    agent_result = agent_worker.run_once()
    return agent_result if agent_result["processed"] else jira_worker.run_once()


def should_wait(result: dict) -> bool:
    return not result.get("processed", False)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run report AI audit worker")
    parser.add_argument("--once", action="store_true", help="process one pending audit and exit")
    args = parser.parse_args()

    settings = load_settings()
    database = Database(settings)
    repository = MySqlAuditRepository(database)
    model_client = DeepSeekClient(settings)
    agent_worker = AgentWorker(repository, model_client)
    audit_worker = AuditWorker(repository, model_client)
    jira_worker = JiraWorker(MySqlJiraRepository(database), JiraClient(settings))

    if args.once:
        print(process_next(audit_worker, agent_worker, jira_worker))
        return

    while True:
        result = process_next(audit_worker, agent_worker, jira_worker)
        print(result, flush=True)
        if should_wait(result):
            time.sleep(settings.worker_interval_seconds)


if __name__ == "__main__":
    main()
