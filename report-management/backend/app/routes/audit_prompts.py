from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request


audit_prompts = Blueprint("audit_prompts", __name__, url_prefix="/api/report-management/audit-prompts")


def _repository():
    return current_app.config["AUDIT_REPOSITORY"]


@audit_prompts.get("/active")
def get_active_prompt():
    prompt = _repository().get_active_prompt()
    if prompt is None:
        return jsonify({"message": "未配置启用的审核提示词"}), 404
    response = jsonify(prompt)
    response.headers["Cache-Control"] = "no-store"
    return response


@audit_prompts.post("")
def create_prompt_version():
    payload = request.get_json(silent=True) or {}
    name = str(payload.get("name", "默认审核提示词")).strip() or "默认审核提示词"
    prompt_content = str(payload.get("promptContent", "")).strip()
    model_name = str(payload.get("modelName", "deepseek-chat")).strip() or "deepseek-chat"
    if not prompt_content:
        return jsonify({"message": "提示词内容不能为空"}), 400

    prompt = _repository().create_prompt_version(
        {
            "name": name,
            "promptContent": prompt_content,
            "modelName": model_name,
        }
    )
    return jsonify(prompt), 201
