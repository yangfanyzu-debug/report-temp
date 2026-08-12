from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request


audit_checkpoints = Blueprint(
    "audit_checkpoints", __name__, url_prefix="/api/report-management/audit-checkpoints"
)


def _repository():
    return current_app.config["AUDIT_REPOSITORY"]


def _checkpoint_payload(payload: dict) -> tuple[dict | None, str | None]:
    name = str(payload.get("name", "")).strip()
    content = str(payload.get("content", "")).strip()
    if not name:
        return None, "检查点名称不能为空"
    if not content:
        return None, "检查内容不能为空"
    try:
        sort_order = int(payload.get("sortOrder", 0))
    except (TypeError, ValueError):
        return None, "排序必须是整数"
    return {
        "name": name,
        "content": content,
        "sortOrder": sort_order,
        "enabled": bool(payload.get("enabled", True)),
    }, None


@audit_checkpoints.get("")
def list_checkpoints():
    response = jsonify({"rows": _repository().list_checkpoints()})
    response.headers["Cache-Control"] = "no-store"
    return response


@audit_checkpoints.post("")
def create_checkpoint():
    payload, error = _checkpoint_payload(request.get_json(silent=True) or {})
    if error:
        return jsonify({"message": error}), 400
    return jsonify(_repository().create_checkpoint(payload)), 201


@audit_checkpoints.put("/<int:checkpoint_id>")
def update_checkpoint(checkpoint_id: int):
    payload, error = _checkpoint_payload(request.get_json(silent=True) or {})
    if error:
        return jsonify({"message": error}), 400
    checkpoint = _repository().update_checkpoint(checkpoint_id, payload)
    if checkpoint is None:
        return jsonify({"message": "未找到该审核检查点"}), 404
    return jsonify(checkpoint)
