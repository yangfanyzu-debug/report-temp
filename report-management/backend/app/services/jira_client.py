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
        payload = {
            "externalId": f"capability-report-{job['reportId']}",
            "reportId": job["reportId"],
            "versionId": job["versionId"],
            "auditId": job["auditId"],
            "systemId": job["systemId"],
            "title": job["title"],
            "reportMonth": job["reportMonth"],
            "auditResult": job.get("auditResult") or "",
        }
        headers = {
            "Content-Type": "application/json",
            "Idempotency-Key": payload["externalId"],
        }
        if self.settings.jira_api_token:
            headers["Authorization"] = f"Bearer {self.settings.jira_api_token}"
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
    return _extract_jira_id(payload.get("data"))
