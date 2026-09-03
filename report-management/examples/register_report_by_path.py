#!/usr/bin/env python3
"""批次服务与报告中心同机时，通过本地文件路径登记初始报告。"""

from pathlib import Path
from time import monotonic, sleep

import requests


API_URL = "http://127.0.0.1:8045/api/report-management/reports/register"


def parse_registration_response(response: requests.Response) -> dict:
    try:
        result = response.json()
    except ValueError:
        result = {"message": response.text.strip() or "服务未返回JSON"}
    if response.status_code >= 400:
        raise RuntimeError(
            f"登记失败 HTTP {response.status_code}: "
            f"{result.get('code', 'UNKNOWN')} - {result.get('message', '未知错误')}"
        )
    return result


def wait_for_audit(audit_id: int, timeout_seconds: int = 900) -> dict:
    audit_url = API_URL.split("/reports/", 1)[0] + f"/audits/{audit_id}"
    deadline = monotonic() + timeout_seconds
    while True:
        response = requests.get(audit_url, timeout=(10, 30))
        response.raise_for_status()
        audit = response.json()
        if audit.get("status") not in {"pending", "running"}:
            return audit
        if monotonic() >= deadline:
            raise TimeoutError(f"等待AI初审超时，auditId={audit_id}")
        sleep(5)


def register_report(
    file_path: str,
    system_id: str,
    title: str,
    report_month: str,
    generation_id: str,
) -> dict:
    report_file = Path(file_path).expanduser().resolve()
    if not report_file.is_file():
        raise FileNotFoundError(f"报告文件不存在：{report_file}")
    if report_file.suffix.lower() != ".docx":
        raise ValueError("仅支持 DOCX 文件")

    response = requests.post(
        API_URL,
        json={
            "systemId": system_id,
            "title": title,
            "reportMonth": report_month,
            "generationId": generation_id,
            "filePath": str(report_file),
            "source": "batch",
        },
        timeout=(10, 60),
    )
    return parse_registration_response(response)


if __name__ == "__main__":
    result = register_report(
        file_path="/appdata/batch/output/性能容量报告.docx",
        system_id="credit-card-center",
        title="中信银行信用卡中心授权交易资源分析报告",
        report_month="2026年08月",
        generation_id="batch-202608-credit-card-center-001",
    )
    print("报告登记结果：", result)
    if result.get("auditStatus") in {"pending", "running"}:
        print("AI初审结果：", wait_for_audit(result["auditId"]))
    elif result.get("nextAction") == "stop":
        print("初审已通过，正式流程中不再继续登记。")
