from __future__ import annotations

from pathlib import Path

from flask import Blueprint, current_app, jsonify, send_file


versions = Blueprint("versions", __name__, url_prefix="/api/report-management/versions")


DOCX_MIMETYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def _repository():
    return current_app.config["REPORT_REPOSITORY"]


def _version_file_or_response(version_id: int):
    version_file = _repository().get_version_file(version_id)
    if version_file is None:
        return None, (jsonify({"message": "未找到该报告版本"}), 404)
    path = Path(version_file["filePath"])
    if not path.is_file():
        return None, (jsonify({"message": "报告文件不存在"}), 404)
    return (version_file, path), None


@versions.get("/<int:version_id>/preview")
def preview_version(version_id: int):
    resolved, error = _version_file_or_response(version_id)
    if error:
        return error
    version_file, path = resolved
    return send_file(path, mimetype=DOCX_MIMETYPE, as_attachment=False, download_name=version_file["fileName"])


@versions.get("/<int:version_id>/download")
def download_version(version_id: int):
    resolved, error = _version_file_or_response(version_id)
    if error:
        return error
    version_file, path = resolved
    return send_file(path, mimetype=DOCX_MIMETYPE, as_attachment=True, download_name=version_file["fileName"])
