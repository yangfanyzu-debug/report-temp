#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-precheck}"
REMOTE_HOST="${REMOTE_HOST:-root@49.51.194.37}"
REMOTE_STACK_DIR="${REMOTE_STACK_DIR:-/opt/middleware-stack}"
DATABASE="${DATABASE:-ry-cloud}"

case "$MODE" in
  precheck)
    SQL_FILE="report-management/db/migrations/001_precheck_report_management.sql"
    ;;
  apply)
    SQL_FILE="report-management/db/migrations/001_apply_report_management.sql"
    ;;
  *)
    echo "Usage: $0 [precheck|apply]" >&2
    exit 2
    ;;
esac

if [[ ! -f "$SQL_FILE" ]]; then
  echo "SQL file not found: $SQL_FILE" >&2
  exit 1
fi

ssh "$REMOTE_HOST" "cd '$REMOTE_STACK_DIR' && source .env && docker exec -i mysql57 mysql -uroot -p\"\$MYSQL_ROOT_PASSWORD\" --default-character-set=utf8mb4 --database='$DATABASE'" < "$SQL_FILE"
