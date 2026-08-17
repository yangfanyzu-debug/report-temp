#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${REPORT_MANAGEMENT_HOME:-/opt/report-management/backend}"
RUN_DIR="$APP_DIR/run"
LOG_DIR="$APP_DIR/logs"
API_PID_FILE="$RUN_DIR/api.pid"
WORKER_PID_FILE="$RUN_DIR/worker.pid"

mkdir -p "$RUN_DIR" "$LOG_DIR"

load_env() {
  set -a
  # shellcheck disable=SC1091
  source "$APP_DIR/.env"
  set +a
}

is_running() {
  local pid_file="$1"
  [ -f "$pid_file" ] && kill -0 "$(cat "$pid_file")" 2>/dev/null
}

start_process() {
  local name="$1"
  local pid_file="$2"
  shift 2

  if is_running "$pid_file"; then
    echo "$name already running: $(cat "$pid_file")"
    return
  fi

  rm -f "$pid_file"
  nohup "$@" >> "$LOG_DIR/$name.log" 2>&1 &
  echo $! > "$pid_file"
  echo "$name started: $(cat "$pid_file")"
}

stop_process() {
  local name="$1"
  local pid_file="$2"

  if ! is_running "$pid_file"; then
    rm -f "$pid_file"
    echo "$name already stopped"
    return
  fi

  local pid
  pid="$(cat "$pid_file")"
  kill "$pid"

  for _ in $(seq 1 20); do
    if ! kill -0 "$pid" 2>/dev/null; then
      rm -f "$pid_file"
      echo "$name stopped"
      return
    fi
    sleep 1
  done

  kill -9 "$pid" 2>/dev/null || true
  rm -f "$pid_file"
  echo "$name force stopped"
}

start_all() {
  load_env
  cd "$APP_DIR"

  start_process api "$API_PID_FILE" \
    "$APP_DIR/.venv/bin/gunicorn" \
    -w 2 -b 0.0.0.0:5010 run:app

  start_process worker "$WORKER_PID_FILE" \
    "$APP_DIR/.venv/bin/python" run_worker.py
}

stop_all() {
  stop_process worker "$WORKER_PID_FILE"
  stop_process api "$API_PID_FILE"
}

status_process() {
  local name="$1"
  local pid_file="$2"

  if is_running "$pid_file"; then
    echo "$name running: $(cat "$pid_file")"
  else
    echo "$name stopped"
  fi
}

status_all() {
  status_process api "$API_PID_FILE"
  status_process worker "$WORKER_PID_FILE"
}

case "${1:-status}" in
  start)
    start_all
    sleep 2
    status_all
    ;;
  stop)
    stop_all
    ;;
  restart)
    stop_all
    start_all
    sleep 2
    status_all
    ;;
  status)
    status_all
    ;;
  logs)
    touch "$LOG_DIR/api.log" "$LOG_DIR/worker.log"
    tail -n 200 -f "$LOG_DIR/api.log" "$LOG_DIR/worker.log"
    ;;
  *)
    echo "Usage: $0 {start|stop|restart|status|logs}" >&2
    exit 2
    ;;
esac
