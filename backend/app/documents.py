from __future__ import annotations

import os
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

from flask import Blueprint, current_app, jsonify, request, send_from_directory

from .metadata import load_metadata, save_document_metadata


documents = Blueprint("documents", __name__, url_prefix="/api/files")
DOCX_MARKERS = {"[Content_Types].xml", "word/document.xml"}


def _storage_dir() -> Path:
    return Path(current_app.config["STORAGE_DIR"])


def _validate_filename(filename: str) -> str:
    normalized = filename.strip()
    if not normalized or Path(normalized).name != normalized:
        raise ValueError("文件名无效")
    if Path(normalized).suffix.lower() != ".docx":
        raise ValueError("仅支持 DOCX 文件")
    return normalized


def _is_docx(path: Path) -> bool:
    try:
        with zipfile.ZipFile(path) as archive:
            return DOCX_MARKERS.issubset(archive.namelist())
    except (OSError, zipfile.BadZipFile):
        return False


def _human_size(size: int) -> str:
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    return f"{size / (1024 * 1024):.1f} MB"


def _file_info(path: Path, metadata: dict[str, str] | None = None) -> dict[str, object]:
    stat = path.stat()
    metadata = metadata or {}
    api_prefix = current_app.config["PUBLIC_API_PREFIX"].rstrip("/")
    encoded_name = quote(path.name, safe="")
    return {
        "name": path.name,
        "size": stat.st_size,
        "sizeDisplay": _human_size(stat.st_size),
        "updatedAt": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
        "uploadedAt": metadata.get("uploadedAt"),
        "uploader": metadata.get("uploader", "未知用户"),
        "downloadUrl": f"{api_prefix}/files/{encoded_name}/download",
        "previewUrl": f"{api_prefix}/files/{encoded_name}/preview",
    }


def _positive_integer(value: str | None, default: int, maximum: int | None = None) -> int:
    try:
        parsed = int(value or default)
    except ValueError:
        parsed = default
    parsed = max(parsed, 1)
    return min(parsed, maximum) if maximum else parsed


@documents.post("/upload")
def upload_file():
    uploaded = request.files.get("file")
    if uploaded is None or not uploaded.filename:
        return jsonify({"message": "请选择要上传的 DOCX 文件"}), 400

    try:
        filename = _validate_filename(uploaded.filename)
    except ValueError as error:
        return jsonify({"message": str(error)}), 400

    storage_dir = _storage_dir()
    storage_dir.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=".upload-", suffix=".docx", dir=storage_dir)
    os.close(descriptor)
    temporary_path = Path(temporary_name)

    try:
        uploaded.save(temporary_path)
        if not _is_docx(temporary_path):
            return jsonify({"message": "文件内容不是有效的 DOCX 文档"}), 400

        uploader = request.form.get("uploader", "").strip() or "未知用户"
        destination = storage_dir / filename
        replaced = destination.exists()
        os.replace(temporary_path, destination)
        uploaded_at = datetime.now(timezone.utc).isoformat()
        save_document_metadata(storage_dir, filename, uploader, uploaded_at)
        return jsonify(
            {
                "message": "同名文档已替换" if replaced else "文档上传成功",
                "replaced": replaced,
                "file": _file_info(destination, {"uploader": uploader, "uploadedAt": uploaded_at}),
            }
        ), 200 if replaced else 201
    finally:
        temporary_path.unlink(missing_ok=True)


@documents.get("")
def list_files():
    filename_keyword = request.args.get("filename", "").strip().casefold()
    uploader_keyword = request.args.get("uploader", "").strip().casefold()
    page_num = _positive_integer(request.args.get("pageNum"), 1)
    page_size = _positive_integer(request.args.get("pageSize"), 10, maximum=100)

    storage_dir = _storage_dir()
    metadata = load_metadata(storage_dir)
    rows = []
    for path in storage_dir.iterdir():
        if not path.is_file() or path.suffix.lower() != ".docx":
            continue
        document_metadata = metadata.get(path.name, {})
        uploader = document_metadata.get("uploader", "未知用户")
        if filename_keyword and filename_keyword not in path.name.casefold():
            continue
        if uploader_keyword and uploader_keyword not in uploader.casefold():
            continue
        rows.append(_file_info(path, document_metadata))

    rows.sort(key=lambda item: item["updatedAt"], reverse=True)
    total = len(rows)
    start = (page_num - 1) * page_size
    return jsonify({"rows": rows[start : start + page_size], "total": total})


@documents.get("/<path:filename>/download")
def download_file(filename: str):
    try:
        safe_filename = _validate_filename(filename)
    except ValueError as error:
        return jsonify({"message": str(error)}), 400

    path = _storage_dir() / safe_filename
    if not path.is_file():
        return jsonify({"message": "未找到该文档"}), 404
    return send_from_directory(_storage_dir(), safe_filename, as_attachment=True)


@documents.get("/<path:filename>/preview")
def preview_file(filename: str):
    try:
        safe_filename = _validate_filename(filename)
    except ValueError as error:
        return jsonify({"message": str(error)}), 400

    path = _storage_dir() / safe_filename
    if not path.is_file():
        return jsonify({"message": "未找到该文档"}), 404
    return send_from_directory(
        _storage_dir(),
        safe_filename,
        as_attachment=False,
        mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
