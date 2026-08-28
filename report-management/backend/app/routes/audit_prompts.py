from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request


audit_prompts = Blueprint("audit_prompts", __name__, url_prefix="/api/report-management/audit-prompts")
VALID_AUDIT_TYPES = {"initial", "revision"}


def _repository():
    return current_app.config["AUDIT_REPOSITORY"]


def _public_prompt(prompt: dict):
    public = dict(prompt)
    public.pop("apiKey", None)
    public.pop("apiUrl", None)
    public.pop("modelName", None)
    return public


def _deprecated(response):
    response.headers["Deprecation"] = "true"
    return response


def _get_active_prompt(audit_type: str, deprecated: bool = False):
    if audit_type not in VALID_AUDIT_TYPES:
        return jsonify({"message": "不支持的审核类型"}), 404
    prompt = _repository().get_active_prompt(audit_type)
    if prompt is None:
        response = jsonify({"message": "未配置启用的审核提示词"})
        return (_deprecated(response) if deprecated else response), 404
    response = jsonify(_public_prompt(prompt))
    response.headers["Cache-Control"] = "no-store"
    return _deprecated(response) if deprecated else response


def _create_prompt_version(audit_type: str, deprecated: bool = False):
    if audit_type not in VALID_AUDIT_TYPES:
        return jsonify({"message": "不支持的审核类型"}), 404
    request_payload = request.get_json(silent=True) or {}
    default_name = "初始审核提示词" if audit_type == "initial" else "修订审核提示词"
    name = str(request_payload.get("name", default_name)).strip() or default_name
    prompt_content = str(request_payload.get("promptContent", "")).strip()
    if not prompt_content:
        return jsonify({"message": "提示词内容不能为空"}), 400

    prompt = _repository().create_prompt_version(audit_type, {"name": name, "promptContent": prompt_content})
    response = jsonify(_public_prompt(prompt))
    return (_deprecated(response) if deprecated else response), 201


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
