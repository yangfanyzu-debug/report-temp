from __future__ import annotations

from flask import Blueprint, jsonify


health = Blueprint("health", __name__)


@health.get("/health")
def health_check():
    return jsonify({"status": "ok", "service": "report-management"})
