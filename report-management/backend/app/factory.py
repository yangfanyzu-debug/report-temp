from __future__ import annotations

from flask import Flask, jsonify

from .config import load_settings
from .database import Database
from .repositories.audits import MySqlAuditRepository
from .repositories.reports import MySqlReportRepository
from .routes.audit_prompts import audit_prompts
from .routes.audit_checkpoints import audit_checkpoints
from .routes.audits import audits
from .routes.health import health
from .routes.reports import reports
from .routes.versions import versions


def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(__name__, static_folder=None)
    settings = load_settings()
    app.config.from_mapping(
        SETTINGS=settings,
        UPLOAD_DIR=str(settings.upload_dir),
        PUBLIC_API_PREFIX=settings.public_api_prefix,
        MAX_CONTENT_LENGTH=50 * 1024 * 1024,
    )
    if test_config:
        app.config.update(test_config)
    if "REPORT_REPOSITORY" not in app.config:
        database = Database(settings)
        app.config["REPORT_REPOSITORY"] = MySqlReportRepository(database)
        app.config["AUDIT_REPOSITORY"] = MySqlAuditRepository(database)
    elif "AUDIT_REPOSITORY" not in app.config:
        app.config["AUDIT_REPOSITORY"] = app.config["REPORT_REPOSITORY"]

    app.register_blueprint(health)
    app.register_blueprint(reports)
    app.register_blueprint(versions)
    app.register_blueprint(audits)
    app.register_blueprint(audit_prompts)
    app.register_blueprint(audit_checkpoints)

    @app.errorhandler(413)
    def file_too_large(_error):
        return jsonify({"message": "文件不能超过 50 MB"}), 413

    return app
