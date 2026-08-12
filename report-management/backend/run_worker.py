from __future__ import annotations

import argparse
import time

from app.config import load_settings
from app.database import Database
from app.repositories.audits import MySqlAuditRepository
from app.services.agent_worker import AgentWorker
from app.services.audit_worker import AuditWorker
from app.services.deepseek_client import DeepSeekClient


def main() -> None:
    parser = argparse.ArgumentParser(description="Run report AI audit worker")
    parser.add_argument("--once", action="store_true", help="process one pending audit and exit")
    args = parser.parse_args()

    settings = load_settings()
    repository = MySqlAuditRepository(Database(settings))
    model_client = DeepSeekClient(settings)
    agent_worker = AgentWorker(repository, model_client)
    audit_worker = AuditWorker(repository, model_client)

    def run_once():
        agent_result = agent_worker.run_once()
        return agent_result if agent_result["processed"] else audit_worker.run_once()

    if args.once:
        print(run_once())
        return

    while True:
        print(run_once(), flush=True)
        time.sleep(settings.worker_interval_seconds)


if __name__ == "__main__":
    main()
