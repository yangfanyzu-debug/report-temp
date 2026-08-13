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


@audits.post("/reports/<int:report_id>/versions/<int:version_id>/retry")
def retry_version_audit(report_id: int, version_id: int):
    result = _repository().retry_version_audit(report_id, version_id)
    if result is None:
        return jsonify({"message": "未找到该报告版本"}), 404
    return jsonify(result), 202


@audits.get("/reports/<int:report_id>/versions/<int:version_id>/messages")
def list_agent_messages(report_id: int, version_id: int):
    messages = _repository().list_agent_messages(report_id, version_id)
    if messages is None:
        return jsonify({"message": "未找到该报告版本"}), 404
    response = jsonify(
        {
            "reportId": report_id,
            "versionId": version_id,
            "messages": messages,
            "processing": any(item["status"] in {"pending", "running"} for item in messages),
        }
    )
    response.headers["Cache-Control"] = "no-store"
    return response


@audits.post("/reports/<int:report_id>/versions/<int:version_id>/messages")
def create_agent_message(report_id: int, version_id: int):
    payload = request.get_json(silent=True) or {}
    content = str(payload.get("content") or "").strip()
    if not content:
        return jsonify({"message": "对话内容不能为空"}), 400
    if len(content) > 2000:
        return jsonify({"message": "单次对话内容不能超过2000字"}), 400
    result = _repository().create_agent_exchange(report_id, version_id, content)
    if result is None:
        return jsonify({"message": "未找到该报告版本"}), 404
    return jsonify(result), 202
