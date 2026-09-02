from __future__ import annotations

import logging
from pathlib import Path

from flask import Blueprint, current_app, jsonify, request

from ..repositories.reports import ReportWorkflowConflict
from ..services.file_naming import build_versioned_filename
from ..services.file_storage import save_uploaded_docx, validate_docx_filename


reports = Blueprint("reports", __name__, url_prefix="/api/report-management/reports")
logger = logging.getLogger(__name__)


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
    required_fields = ["systemId", "title", "reportMonth", "filePath", "generationId"]
    missing = [field for field in required_fields if not str(payload.get(field, "")).strip()]
    if missing:
        return jsonify({"message": f"缺少必要参数：{', '.join(missing)}"}), 400

    result = _repository().register_initial_report(
        {
            "systemId": payload["systemId"].strip(),
            "title": payload["title"].strip(),
            "reportMonth": payload["reportMonth"].strip(),
            "filePath": payload["filePath"].strip(),
            "generationId": payload["generationId"].strip(),
            "source": payload.get("source", "batch"),
        }
    )
    logger.info(
        "report_registered transport=path generationId=%s systemId=%s reportId=%s versionId=%s auditId=%s created=%s",
        payload["generationId"].strip(),
        payload["systemId"].strip(),
        result.get("reportId"),
        result.get("versionId"),
        result.get("auditId"),
        result.get("created", True),
    )
    return jsonify(result), 201 if result.get("created", True) else 200


@reports.post("/register-upload")
def upload_and_register_initial_report():
    uploaded = request.files.get("file")
    if uploaded is None or not uploaded.filename:
        return jsonify({"message": "请选择要上传的 DOCX 文件"}), 400

    required_fields = ["systemId", "title", "reportMonth", "generationId"]
    missing = [field for field in required_fields if not request.form.get(field, "").strip()]
    if missing:
        return jsonify({"message": f"缺少必要参数：{', '.join(missing)}"}), 400

    system_id = request.form["systemId"].strip()
    title = request.form["title"].strip()
    report_month = request.form["reportMonth"].strip()
    try:
        original_filename = validate_docx_filename(uploaded.filename)
    except ValueError as error:
        return jsonify({"message": str(error)}), 400

    stored_filename = build_versioned_filename(
        system_id,
        report_month,
        1,
        original_filename,
    )
    try:
        saved_path = save_uploaded_docx(
            uploaded,
            Path(current_app.config["INITIAL_REPORT_DIR"]),
            stored_filename,
        )
    except ValueError as error:
        return jsonify({"message": str(error)}), 400
    uploaded_file_size = saved_path.stat().st_size

    try:
        result = _repository().register_initial_report(
            {
                "systemId": system_id,
                "title": title,
                "reportMonth": report_month,
                "filePath": str(saved_path),
                "fileName": original_filename,
                "fileSize": uploaded_file_size,
                "generationId": request.form["generationId"].strip(),
                "source": request.form.get("source", "batch").strip() or "batch",
            }
        )
    except Exception:
        logger.exception(
            "report_registration_failed transport=upload generationId=%s systemId=%s fileName=%s",
            request.form["generationId"].strip(),
            system_id,
            original_filename,
        )
        saved_path.unlink(missing_ok=True)
        raise
    if not result.get("created", True):
        saved_path.unlink(missing_ok=True)
    logger.info(
        "report_registered transport=upload generationId=%s systemId=%s reportId=%s versionId=%s auditId=%s created=%s fileSize=%s",
        request.form["generationId"].strip(),
        system_id,
        result.get("reportId"),
        result.get("versionId"),
        result.get("auditId"),
        result.get("created", True),
        uploaded_file_size,
    )
    return jsonify(result), 201 if result.get("created", True) else 200


@reports.post("/<int:report_id>/versions")
def upload_report_version(report_id: int):
    uploaded = request.files.get("file")
    if uploaded is None or not uploaded.filename:
        return jsonify({"message": "请选择要上传的 DOCX 文件"}), 400

    context = _repository().prepare_uploaded_version(report_id)
    if context is None:
        return jsonify({"message": "未找到该报告"}), 404
    if context.get("isFinalized"):
        return jsonify(
            {"message": "报告已定稿，不能继续新增版本", "code": "REPORT_FINALIZED"}
        ), 409
    if context.get("initialAuditStatus") != "passed":
        return jsonify(
            {
                "message": "初审通过后才能上传修订版本",
                "code": "INITIAL_AUDIT_NOT_PASSED",
            }
        ), 409

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
    try:
        result = _repository().create_uploaded_version(
            {
                "reportId": report_id,
                "fileName": original_filename,
                "filePath": str(saved_path),
                "fileSize": saved_path.stat().st_size,
                "uploader": uploader,
            }
        )
    except Exception:
        logger.exception(
            "report_version_upload_failed reportId=%s fileName=%s",
            report_id,
            original_filename,
        )
        saved_path.unlink(missing_ok=True)
        raise
    logger.info(
        "report_version_uploaded reportId=%s versionId=%s versionNo=%s auditId=%s fileSize=%s",
        report_id,
        result.get("versionId"),
        result.get("versionNo"),
        result.get("auditId"),
        saved_path.stat().st_size,
    )
    return jsonify(result), 201


@reports.post("/<int:report_id>/finalize")
def finalize_report(report_id: int):
    payload = request.get_json(silent=True) or {}
    operator = str(payload.get("operator", "")).strip() or "未知用户"
    result = _repository().finalize_report(report_id, operator)
    if result is None:
        return jsonify({"message": "未找到该报告"}), 404
    logger.info(
        "report_finalized reportId=%s finalVersionId=%s created=%s",
        report_id,
        result.get("finalVersionId"),
        result.get("created"),
    )
    return jsonify(result), 201 if result.get("created") else 200


@reports.errorhandler(ReportWorkflowConflict)
def handle_report_workflow_conflict(error: ReportWorkflowConflict):
    logger.warning(
        "report_workflow_conflict method=%s path=%s code=%s error=%s",
        request.method,
        request.path,
        error.code,
        str(error),
    )
    return jsonify({"message": str(error), "code": error.code}), 409
