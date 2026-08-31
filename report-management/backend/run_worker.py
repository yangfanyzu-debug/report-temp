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

    def run_once():
        agent_result = agent_worker.run_once()
        if agent_result["processed"]:
            return agent_result
        audit_result = audit_worker.run_once()
        return audit_result if audit_result["processed"] else jira_worker.run_once()

    if args.once:
        print(run_once())
        return

    while True:
        print(run_once(), flush=True)
        time.sleep(settings.worker_interval_seconds)


if __name__ == "__main__":
    main()
