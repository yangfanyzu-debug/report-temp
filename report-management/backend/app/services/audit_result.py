from __future__ import annotations

import re
from typing import Any


def extract_jira_title(result_text: Any) -> str:
    matches = re.findall(
        r"(?m)^\s*JIRA标题\s*[：:]\s*([^\r\n]+)\s*$",
        str(result_text or ""),
        re.IGNORECASE,
    )
    if not matches:
        return ""
    title = re.sub(r"^[`*_#\s]+|[`*_#\s]+$", "", matches[-1]).strip()
    return title.strip("，。；;：:")[:15]
