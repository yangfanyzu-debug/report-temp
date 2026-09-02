from __future__ import annotations

import hashlib
import logging

from flask import Blueprint, jsonify, request


mock_jira = Blueprint(
    "mock_jira", __name__, url_prefix="/api/report-management/mock/jira"
)
logger = logging.getLogger(__name__)


def _mock_issue_key(idempotency_key: str, system_id: str, title: str) -> str:
    source = idempotency_key.strip() or f"{system_id}:{title}"
    digest = hashlib.sha256(source.encode("utf-8")).hexdigest()
    issue_number = int(digest[:12], 16) % 1_000_000_000
    return f"MOCK-{issue_number:09d}"


@mock_jira.post("")
def create_mock_issue():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"retCode": 400, "retDesc": "请求体必须是JSON对象"}), 400

    system_id = str(payload.get("systemId") or "").strip()
    title = str(payload.get("title") or "").strip()
    issue_key = _mock_issue_key(
        request.headers.get("Idempotency-Key", ""), system_id, title
    )
    logger.info("mock_jira_created systemId=%s jiraId=%s", system_id, issue_key)
    return jsonify(
        {
            "retCode": 200,
            "retData": {
                "id": issue_key.removeprefix("MOCK-"),
                "key": issue_key,
                "self": request.base_url,
            },
            "retDesc": "success",
        }
    )
