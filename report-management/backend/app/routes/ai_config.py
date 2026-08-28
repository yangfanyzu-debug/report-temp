from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request


ai_config = Blueprint("ai_config", __name__, url_prefix="/api/report-management/ai-config")


def _repository():
    return current_app.config["AUDIT_REPOSITORY"]


def _public_config(config: dict) -> dict:
    return {
        "id": config["id"],
        "apiUrl": config["apiUrl"],
        "modelName": config["modelName"],
        "apiKeyMasked": config["apiKeyMasked"],
        "apiKeyConfigured": config["apiKeyConfigured"],
    }


def _config_payload(payload: dict) -> tuple[dict | None, str | None]:
    api_url = str(payload.get("apiUrl", "")).strip()
    model_name = str(payload.get("modelName", "")).strip()
    api_key = str(payload.get("apiKey", "")).strip()
    if not api_url:
        return None, "大模型URL不能为空"
    if not model_name:
        return None, "模型名称不能为空"
    return {"apiUrl": api_url, "modelName": model_name, "apiKey": api_key}, None


@ai_config.get("")
def get_ai_config():
    config = _repository().get_ai_config()
    if config is None:
        return jsonify({"message": "未配置共用模型连接"}), 404
    response = jsonify(_public_config(config))
    response.headers["Cache-Control"] = "no-store"
    return response


@ai_config.put("")
def update_ai_config():
    payload, error = _config_payload(request.get_json(silent=True) or {})
    if error:
        return jsonify({"message": error}), 400
    response = jsonify(_public_config(_repository().update_ai_config(payload)))
    response.headers["Cache-Control"] = "no-store"
    return response
