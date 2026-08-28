from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from typing import Any, Callable, Iterable

from ..config import Settings


class DeepSeekNotConfigured(RuntimeError):
    pass


class DeepSeekClient:
    def __init__(self, settings: Settings):
        self.settings = settings

    def audit_report(
        self,
        model_config: dict[str, Any],
        prompt: dict[str, Any],
        audit_input: dict[str, Any],
        on_delta: Callable[[str], None] | None = None,
    ) -> dict[str, str]:
        api_url = str(model_config.get("apiUrl") or "").strip()
        api_key = str(model_config.get("apiKey") or "").strip()
        model_name = str(model_config.get("modelName") or "").strip()
        if not api_url or not api_key or not model_name:
            raise DeepSeekNotConfigured("共用模型连接配置不完整")

        request_payload = {
            "model": model_name,
            "messages": [
                {
                    "role": "system",
                    "content": prompt["promptContent"]
                    + "\n\n【本次输出协议】首行必须为“审核结论：通过”或“审核结论：不通过”；"
                    "后续使用中文 Markdown 输出审核总结、发现的问题和修改建议；不要输出 JSON。"
                    "此协议优先于上文中的旧输出格式要求。",
                },
                {
                    "role": "user",
                    "content": "请审核以下报告，并严格遵循系统消息中的输出协议。\n"
                    + json.dumps(audit_input, ensure_ascii=False),
                },
            ],
            "temperature": 0.1,
            "stream": True,
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
                content = parse_chat_stream(response, on_delta)
        except urllib.error.URLError as error:
            raise RuntimeError(f"DeepSeek API 调用失败：{error}") from error

        if not content:
            raise RuntimeError("大模型未返回审核内容")
        return parse_model_result(content)

    def chat_report_agent(
        self,
        model_config: dict[str, Any],
        prompt: dict[str, Any],
        report_context: dict[str, Any],
        history: list[dict[str, str]],
        question: str,
        on_delta: Callable[[str], None] | None = None,
    ) -> str:
        api_url = str(model_config.get("apiUrl") or "").strip()
        api_key = str(model_config.get("apiKey") or "").strip()
        model_name = str(model_config.get("modelName") or "").strip()
        if not api_url or not api_key or not model_name:
            raise DeepSeekNotConfigured("共用模型连接配置不完整")

        system_content = (
            "你是性能容量报告AI助手。必须基于给定报告文字、表格、标题结构和最新审核结果回答，"
            "不得声称看到了未解析的图片或图表语义。使用中文 Markdown，结论具体、简洁；"
            "用户要求修改时，只提供可执行的修改建议或替换文本，不声称已经修改DOCX。\n\n"
            "【当前审核配置】\n" + prompt["promptContent"] + "\n\n"
            "【当前报告上下文】\n" + json.dumps(report_context, ensure_ascii=False)
        )
        messages = [{"role": "system", "content": system_content}]
        messages.extend(
            {"role": item["role"], "content": item["content"]}
            for item in history
            if item.get("role") in {"user", "assistant"} and item.get("content")
        )
        messages.append({"role": "user", "content": question})
        request_payload = {
            "model": model_name,
            "messages": messages,
            "temperature": 0.2,
            "stream": True,
        }
        request = urllib.request.Request(
            chat_completions_url(api_url),
            data=json.dumps(request_payload, ensure_ascii=False).encode("utf-8"),
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                content = parse_chat_stream(response, on_delta)
        except urllib.error.URLError as error:
            raise RuntimeError(f"DeepSeek API 调用失败：{error}") from error
        if not content:
            raise RuntimeError("大模型未返回对话内容")
        return content


def chat_completions_url(base_url: str) -> str:
    normalized = base_url.rstrip("/")
    if normalized.endswith("/chat/completions"):
        return normalized
    return f"{normalized}/chat/completions"


def parse_chat_stream(
    lines: Iterable[bytes], on_delta: Callable[[str], None] | None = None
) -> str:
    content_parts: list[str] = []
    for raw_line in lines:
        line = raw_line.decode("utf-8").strip()
        if not line.startswith("data:"):
            continue
        payload = line[5:].strip()
        if payload == "[DONE]":
            break
        if not payload:
            continue
        chunk = json.loads(payload)
        delta = chunk.get("choices", [{}])[0].get("delta", {}).get("content") or ""
        if delta:
            content_parts.append(delta)
            if on_delta:
                on_delta(delta)
    return "".join(content_parts)


def parse_model_result(content: str) -> dict[str, str]:
    cleaned = content.strip()
    if not cleaned:
        raise ValueError("模型输出为空")
    match = re.search(r"审核结论\s*[：:]\s*(不通过|通过)", cleaned[:300])
    conclusion = {"通过": "passed", "不通过": "failed"}.get(match.group(1), "completed") if match else "completed"
    return {"resultText": cleaned, "conclusion": conclusion}
