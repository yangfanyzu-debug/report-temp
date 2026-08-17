#!/usr/bin/env python3
"""批次服务与报告中心同机时，通过本地文件路径登记初始报告。"""

from pathlib import Path

import requests


API_URL = "http://127.0.0.1:8045/api/report-management/reports/register"


def register_report(
    file_path: str,
    system_id: str,
    title: str,
    report_month: str,
    jira_id: str = "",
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
            "jiraId": jira_id,
            "filePath": str(report_file),
            "source": "batch",
        },
        timeout=(10, 60),
    )
    response.raise_for_status()
    return response.json()


if __name__ == "__main__":
    result = register_report(
        file_path="/appdata/batch/output/性能容量报告.docx",
        system_id="credit-card-center",
        title="中信银行信用卡中心授权交易资源分析报告",
        report_month="2026年08月",
        jira_id="CAPACITY-001",
    )
    print("报告登记成功：", result)
