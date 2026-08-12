from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request


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


@audits.get("/<int:audit_id>/events")
def get_audit_events(audit_id: int):
    audit = _repository().get_audit_detail(audit_id)
    if audit is None:
        return jsonify({"message": "未找到该审核记录"}), 404
    try:
        after_id = max(int(request.args.get("afterId", 0)), 0)
    except ValueError:
        return jsonify({"message": "afterId 必须是整数"}), 400
    events = _repository().get_audit_events(audit_id, after_id)
    response = jsonify(
        {
            "auditId": audit_id,
            "status": audit["status"],
            "events": events,
            "lastEventId": events[-1]["id"] if events else after_id,
            "finishedAt": audit["finishedAt"],
            "errorMessage": audit["errorMessage"],
        }
    )
    response.headers["Cache-Control"] = "no-store"
    return response


@audits.get("/reports/<int:report_id>/conversation")
def get_report_conversation(report_id: int):
    conversation = _repository().get_report_conversation(report_id)
    if conversation is None:
        return jsonify({"message": "未找到该报告"}), 404
    response = jsonify(conversation)
    response.headers["Cache-Control"] = "no-store"
    return response
