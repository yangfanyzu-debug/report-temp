from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_UPLOAD_DIR = PROJECT_ROOT / "storage" / "uploaded_reports"
DEFAULT_INITIAL_REPORT_DIR = PROJECT_ROOT / "storage" / "initial_reports"


@dataclass(frozen=True)
class Settings:
    upload_dir: Path
    initial_report_dir: Path
    public_api_prefix: str
    mysql_host: str
    mysql_port: int
    mysql_user: str
    mysql_password: str
    mysql_database: str
    deepseek_url: str
    deepseek_key: str
    deepseek_model: str
    log_level: str
    worker_interval_seconds: int
    jira_create_url: str
    jira_timeout_seconds: int
    batch_debug_reregistration: bool
    mock_jira_enabled: bool


def _env_flag(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def load_settings() -> Settings:
    api_url = os.environ.get(
        "ARK_API_URL",
        os.environ.get("DEEPSEEK_API_URL", "https://ark.cn-beijing.volces.com/api/coding/v3"),
    )
    api_key = os.environ.get("ARK_API_KEY", os.environ.get("DEEPSEEK_API_KEY", ""))
    model = os.environ.get("ARK_MODEL", os.environ.get("DEEPSEEK_MODEL", "ark-code-latest"))
    return Settings(
        upload_dir=Path(os.environ.get("REPORT_UPLOAD_DIR", str(DEFAULT_UPLOAD_DIR))),
        initial_report_dir=Path(
            os.environ.get("REPORT_INITIAL_REPORT_DIR", str(DEFAULT_INITIAL_REPORT_DIR))
        ),
        public_api_prefix=os.environ.get("REPORT_PUBLIC_API_PREFIX", "/api/report-management"),
        mysql_host=os.environ.get("REPORT_MYSQL_HOST", "127.0.0.1"),
        mysql_port=int(os.environ.get("REPORT_MYSQL_PORT", "3306")),
        mysql_user=os.environ.get("REPORT_MYSQL_USER", "root"),
        mysql_password=os.environ.get("REPORT_MYSQL_PASSWORD", ""),
        mysql_database=os.environ.get("REPORT_MYSQL_DATABASE", "ry-cloud"),
        deepseek_url=api_url,
        deepseek_key=api_key,
        deepseek_model=model,
        log_level=os.environ.get("REPORT_LOG_LEVEL", "INFO").strip().upper(),
        worker_interval_seconds=int(os.environ.get("REPORT_WORKER_INTERVAL_SECONDS", "15")),
        jira_create_url=os.environ.get("REPORT_JIRA_CREATE_URL", "").strip(),
        jira_timeout_seconds=int(os.environ.get("REPORT_JIRA_TIMEOUT_SECONDS", "30")),
        batch_debug_reregistration=_env_flag("REPORT_BATCH_DEBUG_REREGISTRATION"),
        mock_jira_enabled=_env_flag("REPORT_MOCK_JIRA_ENABLED"),
    )
