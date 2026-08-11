from __future__ import annotations

import os
import tempfile
from pathlib import Path

from werkzeug.datastructures import FileStorage

from .docx_tools import is_docx


def validate_docx_filename(filename: str) -> str:
    normalized = Path(filename.strip()).name
    if not normalized:
        raise ValueError("请选择要上传的 DOCX 文件")
    if normalized != filename.strip():
        raise ValueError("文件名无效")
    if Path(normalized).suffix.lower() != ".docx":
        raise ValueError("仅支持 DOCX 文件")
    return normalized


def save_uploaded_docx(uploaded: FileStorage, upload_dir: Path, destination_name: str) -> Path:
    upload_dir.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=".upload-", suffix=".docx", dir=upload_dir)
    os.close(descriptor)
    temporary_path = Path(temporary_name)
    try:
        uploaded.save(temporary_path)
        if not is_docx(temporary_path):
            raise ValueError("文件内容不是有效的 DOCX 文档")
        destination = upload_dir / destination_name
        os.replace(temporary_path, destination)
        return destination
    finally:
        temporary_path.unlink(missing_ok=True)
