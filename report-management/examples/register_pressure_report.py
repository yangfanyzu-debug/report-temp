#!/usr/bin/env python3
"""上传压力与稳定性测试报告，并登记为批次生成的初始报告。"""

import os
from pathlib import Path

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

    response.raise_for_status()
    return response.json()


if __name__ == "__main__":
    print("报告上传并登记成功：", register_report())
