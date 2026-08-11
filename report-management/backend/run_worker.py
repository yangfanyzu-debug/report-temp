from __future__ import annotations

import argparse
import time

from app.config import load_settings
from app.database import Database
from app.repositories.audits import MySqlAuditRepository
from app.services.audit_worker import AuditWorker
from app.services.deepseek_client import DeepSeekClient


def main() -> None:
    parser = argparse.ArgumentParser(description="Run report AI audit worker")
    parser.add_argument("--once", action="store_true", help="process one pending audit and exit")
    args = parser.parse_args()

    settings = load_settings()
    repository = MySqlAuditRepository(Database(settings))
    worker = AuditWorker(repository, DeepSeekClient(settings))
    if args.once:
        print(worker.run_once())
        return

    while True:
        print(worker.run_once(), flush=True)
        time.sleep(settings.worker_interval_seconds)


if __name__ == "__main__":
    main()
