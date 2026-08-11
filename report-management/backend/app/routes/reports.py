from __future__ import annotations

from pathlib import Path

from flask import Blueprint, current_app, jsonify, request

from ..services.file_naming import build_versioned_filename
from ..services.file_storage import save_uploaded_docx, validate_docx_filename


reports = Blueprint("reports", __name__, url_prefix="/api/report-management/reports")


def _positive_integer(value: str | None, default: int, maximum: int | None = None) -> int:
    try:
        parsed = int(value or default)
    except ValueError:
        parsed = default
    parsed = max(parsed, 1)
    return min(parsed, maximum) if maximum else parsed


def _repository():
    return current_app.config["REPORT_REPOSITORY"]


@reports.get("")
def list_reports():
    filters = {
        "systemId": request.args.get("systemId", "").strip(),
        "title": request.args.get("title", "").strip(),
        "reportMonth": request.args.get("reportMonth", "").strip(),
        "auditStatus": request.args.get("auditStatus", "").strip(),
    }
    page_num = _positive_integer(request.args.get("pageNum"), 1)
    page_size = _positive_integer(request.args.get("pageSize"), 10, maximum=100)
    response = jsonify(_repository().list_reports(filters, page_num, page_size))
    response.headers["Cache-Control"] = "no-store"
    return response


@reports.get("/<int:report_id>")
def get_report(report_id: int):
    report = _repository().get_report_detail(report_id)
    if report is None:
        return jsonify({"message": "未找到该报告"}), 404
    response = jsonify(report)
    response.headers["Cache-Control"] = "no-store"
    return response


@reports.post("/register")
def register_initial_report():
    payload = request.get_json(silent=True) or {}
    required_fields = ["systemId", "title", "reportMonth", "filePath"]
    missing = [field for field in required_fields if not str(payload.get(field, "")).strip()]
    if missing:
        return jsonify({"message": f"缺少必要参数：{', '.join(missing)}"}), 400

    result = _repository().register_initial_report(
        {
            "systemId": payload["systemId"].strip(),
            "title": payload["title"].strip(),
            "reportMonth": payload["reportMonth"].strip(),
            "filePath": payload["filePath"].strip(),
            "jiraId": str(payload.get("jiraId", "")).strip(),
            "source": payload.get("source", "batch"),
        }
    )
    return jsonify(result), 201


@reports.post("/<int:report_id>/versions")
def upload_report_version(report_id: int):
    uploaded = request.files.get("file")
    if uploaded is None or not uploaded.filename:
        return jsonify({"message": "请选择要上传的 DOCX 文件"}), 400

    context = _repository().prepare_uploaded_version(report_id)
    if context is None:
        return jsonify({"message": "未找到该报告"}), 404

    try:
        original_filename = validate_docx_filename(uploaded.filename)
    except ValueError as error:
        return jsonify({"message": str(error)}), 400

    version_no = context["nextVersionNo"]
    stored_filename = build_versioned_filename(
        context["systemId"],
        context["reportMonth"],
        version_no,
        original_filename,
    )
    try:
        saved_path = save_uploaded_docx(uploaded, Path(current_app.config["UPLOAD_DIR"]), stored_filename)
    except ValueError as error:
        return jsonify({"message": str(error)}), 400

    uploader = request.form.get("uploader", "").strip() or "未知用户"
    result = _repository().create_uploaded_version(
        {
            "reportId": report_id,
            "versionNo": version_no,
            "fileName": original_filename,
            "filePath": str(saved_path),
            "fileSize": saved_path.stat().st_size,
            "uploader": uploader,
        }
    )
    return jsonify(result), 201
