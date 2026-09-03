#!/usr/bin/env python3
"""上传压力与稳定性测试报告，并登记为批次生成的初始报告。"""

import os
from pathlib import Path
from time import monotonic, sleep

import requests


API_URL = os.environ.get(
    "REPORT_CENTER_REGISTER_URL",
    "http://49.51.194.37/prod-api/report-management-api/reports/register-upload",
)
REPORT_FILE = Path(__file__).with_name("03_压力与稳定性测试报告.docx")
DOCX_MIME_TYPE = (
    "application/vnd.openxmlformats-officedocument."
    "wordprocessingml.document"
)


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


def register_report() -> dict:
    if not REPORT_FILE.is_file():
        raise FileNotFoundError(f"报告文件不存在：{REPORT_FILE}")

    form_data = {
        "systemId": "stress-stability",
        "title": "压力与稳定性测试报告",
        "reportMonth": "2026年08月",
        "generationId": "batch-20260804-stress-stability-001",
        "source": "batch",
    }
    with REPORT_FILE.open("rb") as report_stream:
        response = requests.post(
            API_URL,
            data=form_data,
            files={
                "file": (REPORT_FILE.name, report_stream, DOCX_MIME_TYPE),
            },
            timeout=(10, 300),
        )

    return parse_registration_response(response)


if __name__ == "__main__":
    result = register_report()
    print("报告登记结果：", result)
    if result.get("auditStatus") in {"pending", "running"}:
        print("AI初审结果：", wait_for_audit(result["auditId"]))
    elif result.get("nextAction") == "stop":
        print("初审已通过，正式流程中不再继续登记。")
