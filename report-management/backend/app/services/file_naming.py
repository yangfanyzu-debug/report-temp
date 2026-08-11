from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path


SAFE_NAME_PATTERN = re.compile(r"[^0-9A-Za-z\u4e00-\u9fff._-]+")


def sanitize_filename_part(value: str, fallback: str = "report") -> str:
    cleaned = SAFE_NAME_PATTERN.sub("_", value.strip())
    cleaned = cleaned.strip("._-")
    return cleaned or fallback


def build_versioned_filename(
    system_id: str,
    report_month: str,
    version_no: int,
    original_filename: str,
    now: datetime | None = None,
) -> str:
    timestamp = (now or datetime.now()).strftime("%Y%m%d%H%M%S%f")
    suffix = Path(original_filename).suffix.lower() or ".docx"
    stem = sanitize_filename_part(Path(original_filename).stem)
    system = sanitize_filename_part(system_id, "system")
    month = sanitize_filename_part(report_month, "month")
    return f"{system}_{month}_v{version_no}_{timestamp}_{stem}{suffix}"
