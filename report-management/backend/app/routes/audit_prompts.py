from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request


audit_prompts = Blueprint("audit_prompts", __name__, url_prefix="/api/report-management/audit-prompts")
VALID_AUDIT_TYPES = {"initial", "revision"}


def _repository():
    return current_app.config["AUDIT_REPOSITORY"]


def _public_prompt(prompt: dict) -> dict:
    return {
        "id": prompt["id"],
        "name": prompt["name"],
        "auditType": prompt["auditType"],
        "promptContent": prompt["promptContent"],
        "version": prompt["version"],
        "enabled": prompt["enabled"],
        "createTime": prompt["createTime"],
        "updateTime": prompt["updateTime"],
    }


def _deprecated(response):
    response.headers["Deprecation"] = "true"
    return response


def _response(payload: dict, status: int, deprecated: bool = False):
    response = jsonify(payload)
    response.status_code = status
    return _deprecated(response) if deprecated else response


def _get_active_prompt(audit_type: str, deprecated: bool = False):
    if audit_type not in VALID_AUDIT_TYPES:
        return _response({"message": "不支持的审核类型"}, 404, deprecated)
    prompt = _repository().get_active_prompt(audit_type)
    if prompt is None:
        return _response({"message": "未配置启用的审核提示词"}, 404, deprecated)
    response = _response(_public_prompt(prompt), 200, deprecated)
    response.headers["Cache-Control"] = "no-store"
    return response


def _prompt_payload(payload: object, audit_type: str) -> tuple[dict | None, str | None]:
    if not isinstance(payload, dict):
        return None, "请求体必须是JSON对象"
    if "name" in payload and not isinstance(payload["name"], str):
        return None, "提示词名称必须是字符串"
    if "promptContent" in payload and not isinstance(payload["promptContent"], str):
        return None, "提示词内容必须是字符串"
    default_name = "初始审核提示词" if audit_type == "initial" else "修订审核提示词"
    name = payload.get("name", default_name).strip() or default_name
    prompt_content = payload.get("promptContent", "").strip()
    if not prompt_content:
        return None, "提示词内容不能为空"
    return {"name": name, "promptContent": prompt_content}, None


def _create_prompt_version(audit_type: str, deprecated: bool = False):
    if audit_type not in VALID_AUDIT_TYPES:
        return _response({"message": "不支持的审核类型"}, 404, deprecated)
    payload, error = _prompt_payload(request.get_json(silent=True), audit_type)
    if error:
        return _response({"message": error}, 400, deprecated)

    prompt = _repository().create_prompt_version(audit_type, payload)
    return _response(_public_prompt(prompt), 201, deprecated)


@audit_prompts.get("/<audit_type>/active")
def get_typed_active_prompt(audit_type: str):
    return _get_active_prompt(audit_type)


@audit_prompts.post("/<audit_type>")
def create_typed_prompt_version(audit_type: str):
    return _create_prompt_version(audit_type)


@audit_prompts.get("/active")
def get_active_prompt():
    return _get_active_prompt("revision", deprecated=True)


@audit_prompts.post("")
def create_prompt_version():
    return _create_prompt_version("revision", deprecated=True)
