from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from ..config import Settings


class DeepSeekNotConfigured(RuntimeError):
    pass


class DeepSeekClient:
    def __init__(self, settings: Settings):
        self.settings = settings

    def audit_report(self, prompt: dict[str, Any], audit_input: dict[str, Any]) -> dict[str, Any]:
        api_url = prompt.get("apiUrl") or self.settings.deepseek_url
        api_key = prompt.get("apiKey") or self.settings.deepseek_key
        model_name = prompt.get("modelName") or self.settings.deepseek_model
        if not api_url or not api_key:
            raise DeepSeekNotConfigured("DeepSeek API URL 或 Key 未配置")

        request_payload = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": prompt["promptContent"]},
                {
                    "role": "user",
                    "content": "请审核以下报告内容并只输出 JSON：\n"
                    + json.dumps(audit_input, ensure_ascii=False),
                },
            ],
            "temperature": 0.1,
        }
        request = urllib.request.Request(
            chat_completions_url(api_url),
            data=json.dumps(request_payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                raw_response = json.loads(response.read().decode("utf-8"))
        except urllib.error.URLError as error:
            raise RuntimeError(f"DeepSeek API 调用失败：{error}") from error

        content = raw_response["choices"][0]["message"]["content"]
        return parse_model_json(content)


def chat_completions_url(base_url: str) -> str:
    normalized = base_url.rstrip("/")
    if normalized.endswith("/chat/completions"):
        return normalized
    return f"{normalized}/chat/completions"


def parse_model_json(content: str) -> dict[str, Any]:
    cleaned = content.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`").strip()
        if cleaned.startswith("json"):
            cleaned = cleaned[4:].strip()
    parsed = json.loads(cleaned)
    validate_audit_result(parsed)
    return parsed


def validate_audit_result(result: dict[str, Any]) -> None:
    if not isinstance(result, dict):
        raise ValueError("模型输出不是 JSON 对象")
    summary = result.get("summary")
    data = result.get("data")
    if not isinstance(summary, dict):
        raise ValueError("模型输出缺少 summary 对象")
    if summary.get("结论") not in {"通过", "不通过"}:
        raise ValueError("summary.结论 必须是 通过 或 不通过")
    if not isinstance(data, list):
        raise ValueError("模型输出缺少 data 数组")
    for item in data:
        if not isinstance(item, dict) or "检查点" not in item or "分析结果" not in item:
            raise ValueError("data 数组元素必须包含 检查点 和 分析结果")
