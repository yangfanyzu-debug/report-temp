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


def _config_payload(payload: object) -> tuple[dict | None, str | None]:
    if not isinstance(payload, dict):
        return None, "请求体必须是JSON对象"
    for field_name, message in (("apiUrl", "大模型URL必须是字符串"), ("modelName", "模型名称必须是字符串")):
        if field_name in payload and not isinstance(payload[field_name], str):
            return None, message
    api_key_value = payload.get("apiKey")
    if api_key_value is not None and not isinstance(api_key_value, str):
        return None, "API Key必须是字符串"
    api_url = payload.get("apiUrl", "").strip()
    model_name = payload.get("modelName", "").strip()
    api_key = (api_key_value or "").strip()
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
    payload, error = _config_payload(request.get_json(silent=True))
    if error:
        return jsonify({"message": error}), 400
    response = jsonify(_public_config(_repository().update_ai_config(payload)))
    response.headers["Cache-Control"] = "no-store"
    return response
