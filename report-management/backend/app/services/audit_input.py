from __future__ import annotations

from pathlib import Path
from typing import Any

from .docx_tools import extract_text_and_tables


def build_audit_input(job: dict[str, Any], checkpoints: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    extracted = extract_text_and_tables(Path(job["filePath"]))
    return {
        "report": {
            "systemId": job["systemId"],
            "title": job["title"],
            "reportMonth": job["reportMonth"],
            "fileName": job["fileName"],
        },
        "document": extracted,
        "scope": {
            "text": True,
            "tables": True,
            "structure": True,
            "imagesAndChartsSemantic": False,
        },
        "checkpoints": checkpoints or [],
    }
