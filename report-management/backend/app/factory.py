from __future__ import annotations

import os

from flask import Flask, jsonify

from .config import load_settings
from .database import Database
from .logging_config import configure_logging
from .repositories.audits import MySqlAuditRepository
from .repositories.reports import MySqlReportRepository
from .routes.ai_config import ai_config
from .routes.audit_prompts import audit_prompts
from .routes.audit_checkpoints import audit_checkpoints
from .routes.audits import audits
from .routes.health import health
from .routes.mock_jira import mock_jira
from .routes.reports import reports
from .routes.versions import versions


def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(__name__, static_folder=None)
    settings = load_settings()
    if not (test_config or {}).get("TESTING"):
        configure_logging(settings.log_level)
    app.config.from_mapping(
        SETTINGS=settings,
        UPLOAD_DIR=str(settings.upload_dir),
        INITIAL_REPORT_DIR=str(settings.initial_report_dir),
        PUBLIC_API_PREFIX=settings.public_api_prefix,
        BATCH_DEBUG_REREGISTRATION=settings.batch_debug_reregistration,
        MOCK_JIRA_ENABLED=settings.mock_jira_enabled,
        MAX_CONTENT_LENGTH=50 * 1024 * 1024,
    )
    if test_config:
        app.config.update(test_config)
    if not app.testing:
        app.logger.info(
            "api_started port=%s logLevel=%s",
            os.environ.get("REPORT_PORT", "8045"),
            settings.log_level,
        )
    if "REPORT_REPOSITORY" not in app.config:
        database = Database(settings)
        app.config["REPORT_REPOSITORY"] = MySqlReportRepository(database)
        app.config["AUDIT_REPOSITORY"] = MySqlAuditRepository(database)
    elif "AUDIT_REPOSITORY" not in app.config:
        app.config["AUDIT_REPOSITORY"] = app.config["REPORT_REPOSITORY"]

    app.register_blueprint(health)
    if app.testing or app.config["MOCK_JIRA_ENABLED"]:
        app.register_blueprint(mock_jira)
    app.register_blueprint(reports)
    app.register_blueprint(versions)
    app.register_blueprint(audits)
    app.register_blueprint(ai_config)
    app.register_blueprint(audit_prompts)
    app.register_blueprint(audit_checkpoints)

    @app.errorhandler(413)
    def file_too_large(_error):
        return jsonify({"message": "文件不能超过 50 MB"}), 413

    return app
