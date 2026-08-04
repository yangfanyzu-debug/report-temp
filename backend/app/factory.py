from __future__ import annotations

import os
from pathlib import Path

from flask import Flask, jsonify

from .documents import documents


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_STORAGE_DIR = PROJECT_ROOT / "backend" / "storage" / "documents"


def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(__name__, static_folder=None)
    app.config.from_mapping(
        STORAGE_DIR=os.environ.get("DOCX_STORAGE_DIR", str(DEFAULT_STORAGE_DIR)),
        PUBLIC_API_PREFIX=os.environ.get("DOCX_PUBLIC_API_PREFIX", "/api"),
        MAX_CONTENT_LENGTH=50 * 1024 * 1024,
    )
    if test_config:
        app.config.update(test_config)

    Path(app.config["STORAGE_DIR"]).mkdir(parents=True, exist_ok=True)
    app.register_blueprint(documents)

    @app.errorhandler(413)
    def file_too_large(_error):
        return jsonify({"message": "文件不能超过 50 MB"}), 413

    @app.get("/health")
    def health():
        return jsonify({"status": "ok"})

    return app
