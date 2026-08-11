from __future__ import annotations

from flask import Blueprint, current_app, jsonify


audits = Blueprint("audits", __name__, url_prefix="/api/report-management/audits")


def _repository():
    return current_app.config["AUDIT_REPOSITORY"]


@audits.get("/<int:audit_id>")
def get_audit(audit_id: int):
    audit = _repository().get_audit_detail(audit_id)
    if audit is None:
        return jsonify({"message": "未找到该审核记录"}), 404
    response = jsonify(audit)
    response.headers["Cache-Control"] = "no-store"
    return response
