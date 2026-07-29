"""HTTP API for OCR upload, validation, and export (IV.5 / IV.8)."""

from __future__ import annotations

import json
from typing import Any, Mapping

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.views.decorators.http import require_http_methods

from auth.decorators import require_permissions
from auth.roles import PERM_OCR_USE
from ocr.export import build_export, export_filename, normalize_export_format
from ocr.models import OcrJob
from ocr.pipeline import (
    OcrPipelineError,
    create_job_from_upload,
    job_to_dict,
    load_result,
)
from ocr.validation import (
    ValidationRequestError,
    list_document_types,
    validate_document,
)


def _validation_error(exc: Exception) -> JsonResponse:
    return JsonResponse(
        {
            "error": "validation_error",
            "details": {"request": [str(exc)]},
        },
        status=400,
    )


def _parse_json_body(request: HttpRequest) -> dict[str, Any]:
    try:
        body = json.loads(request.body or b"{}")
    except json.JSONDecodeError as exc:
        raise ValidationRequestError("Request body must be valid JSON") from exc
    if not isinstance(body, Mapping):
        raise ValidationRequestError("Request body must be a JSON object")
    return dict(body)


@require_http_methods(["POST"])
@require_permissions(PERM_OCR_USE, api=True)
def ocr_upload(request: HttpRequest) -> JsonResponse:
    """POST /api/v1/ocr/documents/ — multipart upload, returns job_id."""
    upload = request.FILES.get("file") or request.FILES.get("document")
    if upload is None:
        return _validation_error(
            OcrPipelineError("multipart field 'file' (or 'document') is required")
        )
    try:
        username = getattr(request.user, "username", "") or ""
        job = create_job_from_upload(
            upload,
            filename=getattr(upload, "name", "") or "upload.bin",
            content_type=getattr(upload, "content_type", "") or "",
            created_by=username,
        )
    except OcrPipelineError as exc:
        return _validation_error(exc)

    payload = job_to_dict(job)
    payload["message"] = "OCR job queued"
    return JsonResponse(payload, status=202)


@require_http_methods(["GET"])
@require_permissions(PERM_OCR_USE, api=True)
def ocr_job_detail(request: HttpRequest, job_id: str) -> JsonResponse:
    """GET /api/v1/ocr/jobs/<job_id>/ — job status metadata."""
    try:
        job = OcrJob.objects.get(pk=job_id)
    except OcrJob.DoesNotExist:
        return JsonResponse({"error": "not_found", "job_id": job_id}, status=404)
    return JsonResponse(job_to_dict(job))


@require_http_methods(["GET"])
@require_permissions(PERM_OCR_USE, api=True)
def ocr_job_result(request: HttpRequest, job_id: str) -> JsonResponse:
    """GET /api/v1/ocr/jobs/<job_id>/result/ — OCR JSON from object storage."""
    try:
        job = OcrJob.objects.get(pk=job_id)
    except OcrJob.DoesNotExist:
        return JsonResponse({"error": "not_found", "job_id": job_id}, status=404)

    if job.status == OcrJob.STATUS_ERROR:
        return JsonResponse(
            {
                "error": "processing_error",
                "job_id": job.job_id,
                "message": job.error_message,
            },
            status=422,
        )
    if job.status != OcrJob.STATUS_COMPLETED:
        return JsonResponse(
            {
                "error": "not_ready",
                "job_id": job.job_id,
                "status": job.status,
            },
            status=409,
        )

    try:
        result = load_result(job)
    except OcrPipelineError as exc:
        return _validation_error(exc)
    return JsonResponse(result)


@require_http_methods(["GET"])
@require_permissions(PERM_OCR_USE, api=True)
def ocr_doc_types(request: HttpRequest) -> JsonResponse:
    """GET /api/v1/ocr/doc-types/ — configurable validation templates."""
    return JsonResponse(
        {
            "section": "IV.8",
            "acceptance": ["DOC-T-04", "FR-OCR-14"],
            "items": list_document_types(),
        }
    )


@require_http_methods(["POST"])
@require_permissions(PERM_OCR_USE, api=True)
def ocr_validate(request: HttpRequest) -> JsonResponse:
    """POST /api/v1/ocr/validate/ — run rules for a doc_type (DOC-T-04)."""
    try:
        body = _parse_json_body(request)
        document_type = str(body.get("document_type") or "").strip()
        fields = body.get("fields")
        if not isinstance(fields, Mapping):
            raise ValidationRequestError("fields must be an object")
        result = validate_document(
            document_type,
            fields,
            job_id=body.get("job_id"),
            document_id=body.get("document_id"),
            document_sha256=body.get("document_sha256"),
        )
    except (ValidationRequestError, OcrPipelineError) as exc:
        return _validation_error(exc)

    status_code = 200 if result.is_valid else 422
    return JsonResponse(result.as_dict(), status=status_code)


@require_http_methods(["POST"])
@require_permissions(PERM_OCR_USE, api=True)
def ocr_export(request: HttpRequest) -> HttpResponse:
    """POST /api/v1/ocr/export/?format=json|csv — validated downstream payload."""
    try:
        body = _parse_json_body(request)
        export_format = normalize_export_format(
            request.GET.get("format") or body.get("format")
        )
        document_type = str(body.get("document_type") or "").strip()
        fields = body.get("fields")
        if not isinstance(fields, Mapping):
            raise ValidationRequestError("fields must be an object")
        result = validate_document(
            document_type,
            fields,
            job_id=body.get("job_id"),
            document_id=body.get("document_id"),
            document_sha256=body.get("document_sha256"),
        )
        require_valid = body.get("require_valid", True)
        if not isinstance(require_valid, bool):
            require_valid = True
        payload, content_type = build_export(
            result,
            export_format,
            require_valid=require_valid,
        )
        filename = export_filename(result, export_format)
    except ValidationRequestError as exc:
        return _validation_error(exc)

    response = HttpResponse(payload, content_type=content_type)
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response["X-OCR-Status"] = result.status
    response["X-DOC-T"] = "DOC-T-08"
    return response


@require_http_methods(["GET", "POST"])
@require_permissions(PERM_OCR_USE, api=True)
def ocr_job_export(request: HttpRequest, job_id: str) -> HttpResponse:
    """GET|POST /api/v1/ocr/jobs/<id>/export/ — validate job fields and export."""
    try:
        job = OcrJob.objects.get(pk=job_id)
    except OcrJob.DoesNotExist:
        return JsonResponse({"error": "not_found", "job_id": job_id}, status=404)

    try:
        if request.method == "POST":
            body = _parse_json_body(request)
        else:
            body = {}
        export_format = normalize_export_format(
            request.GET.get("format") or body.get("format")
        )
        document_type = str(
            body.get("document_type")
            or request.GET.get("document_type")
            or ""
        ).strip()
        fields = body.get("fields")
        if not isinstance(fields, Mapping):
            raise ValidationRequestError(
                "fields object is required (POST JSON or use /api/v1/ocr/export/)"
            )
        if not document_type:
            raise ValidationRequestError("document_type is required")
        result = validate_document(
            document_type,
            fields,
            job_id=job.job_id,
            document_id=job.document_id,
            document_sha256=job.sha256,
        )
        require_valid = body.get("require_valid", True)
        if not isinstance(require_valid, bool):
            require_valid = True
        payload, content_type = build_export(
            result,
            export_format,
            require_valid=require_valid,
        )
        filename = export_filename(result, export_format)
    except ValidationRequestError as exc:
        return _validation_error(exc)

    response = HttpResponse(payload, content_type=content_type)
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response["X-OCR-Status"] = result.status
    response["X-DOC-T"] = "DOC-T-08"
    return response
