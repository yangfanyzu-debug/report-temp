from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from ..config import Settings


class JiraNotConfigured(RuntimeError):
    pass


class JiraClient:
    def __init__(self, settings: Settings):
        self.settings = settings

    @property
    def configured(self) -> bool:
        return bool(self.settings.jira_create_url)

    def create_issue(self, job: dict[str, Any]) -> str:
        if not self.configured:
            raise JiraNotConfigured("未配置JIRA创建接口")
        jira_title = str(job.get("jiraTitle") or "").strip()
        if len(jira_title) > 15:
            raise RuntimeError("AI生成的JIRA标题超过15个字符")
        payload = {"systemId": job["systemId"]}
        if jira_title:
            payload["title"] = jira_title
        headers = {
            "Content-Type": "application/json",
            "Idempotency-Key": f"capability-report-{job['reportId']}",
        }
        request = urllib.request.Request(
            self.settings.jira_create_url,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(
                request, timeout=self.settings.jira_timeout_seconds
            ) as response:
                result = json.load(response)
        except urllib.error.HTTPError as error:
            detail = error.read(500).decode("utf-8", "replace").strip()
            raise RuntimeError(f"JIRA创建接口返回HTTP {error.code}：{detail}") from error
        except (urllib.error.URLError, TimeoutError) as error:
            raise RuntimeError(f"JIRA创建接口调用失败：{error}") from error

        ret_code = result.get("retCode") if isinstance(result, dict) else None
        if ret_code is not None and str(ret_code) != "200":
            description = str(result.get("retDesc") or "未知错误").strip()
            raise RuntimeError(f"JIRA创建接口返回失败：{description}（retCode={ret_code}）")

        jira_id = _extract_jira_id(result)
        if not jira_id:
            raise RuntimeError("JIRA创建接口响应中缺少jiraId、issueKey或key")
        return jira_id


def _extract_jira_id(payload: Any) -> str:
    if not isinstance(payload, dict):
        return ""
    for key in ("jiraId", "issueKey", "key"):
        value = payload.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return _extract_jira_id(payload.get("retData")) or _extract_jira_id(
        payload.get("data")
    )
