"""HTTP API for AI Assistant chat and FR-RPT-ASS reports (III.7 / III.10)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping

from django.http import (
    FileResponse,
    HttpRequest,
    HttpResponse,
    JsonResponse,
    StreamingHttpResponse,
)
from django.utils.encoding import iri_to_uri
from django.views.decorators.http import require_http_methods

from assistant.ass_reports import (
    AssReportsError,
    build_analytics,
    build_csv_export,
    build_xlsx_export,
    catalog,
    export_filename,
    parse_report_filters,
)
from assistant.chat import (
    AssistantChatError,
    iter_chat_sse,
    parse_chat_request,
)
from assistant.local_llm import get_models_status, select_model
from assistant.openapi import build_openapi_document
from auth.decorators import require_permissions
from auth.roles import PERM_ASSISTANT_REPORTS, PERM_ASSISTANT_USE
from hub.assistant_admin import (
    list_chat_knowledge_bases,
    resolve_assistant_original_path,
)
from hub.kb_admin import KnowledgeBaseError, extract_document_text
from hub.models import AssistantKnowledgeBaseDocument

CHAT_ATTACHMENT_EXTENSIONS = frozenset(
    {".pdf", ".doc", ".docx", ".txt", ".rtf"}
)
CHAT_OCR_EXTENSIONS = frozenset(
    {".pdf", ".jpg", ".jpeg", ".png", ".tiff", ".tif"}
)
CHAT_ATTACHMENT_MAX_BYTES = 10 * 1024 * 1024
FIELD_LABELS_RU = {
    "full_name": "ФИО",
    "surname": "Фамилия",
    "given_name": "Имя",
    "patronymic": "Отчество",
    "series": "Серия",
    "number": "Номер",
    "issue_date": "Дата выдачи",
    "document_number": "Номер документа",
    "date": "Дата",
    "payer": "Плательщик",
    "beneficiary": "Получатель",
    "amount": "Сумма",
    "purpose": "Назначение",
    "currency": "Валюта",
}


def _validation_error(exc: AssistantChatError) -> JsonResponse:
    return JsonResponse(
        {
            "error": "validation_error",
            "details": {"request": [str(exc)]},
        },
        status=400,
    )


def _reports_validation_error(exc: AssReportsError) -> JsonResponse:
    return JsonResponse(
        {
            "error": "validation_error",
            "details": {"request": [str(exc)]},
        },
        status=400,
    )


@require_http_methods(["GET"])
@require_permissions(PERM_ASSISTANT_USE, api=True)
def assistant_knowledge_bases(request: HttpRequest) -> JsonResponse:
    """GET /api/v1/assistant/kbs/ — chat catalog synced with settings «Базы знаний»."""
    return JsonResponse(
        {
            "items": list_chat_knowledge_bases(seed=False),
            "namespace": "chat",
            "includes": ["assistant_*", "cc_production", "suz-bitrix"],
        }
    )


@require_http_methods(["GET", "PUT"])
@require_permissions(PERM_ASSISTANT_USE, api=True)
def assistant_models(request: HttpRequest) -> JsonResponse:
    """GET/PUT /api/v1/assistant/models/ — local LLM catalog and active model."""
    if request.method == "GET":
        return JsonResponse(get_models_status())
    try:
        body = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return JsonResponse(
            {"error": "validation_error", "details": {"request": ["Invalid JSON"]}},
            status=400,
        )
    if not isinstance(body, Mapping):
        return JsonResponse(
            {
                "error": "validation_error",
                "details": {"request": ["Body must be a JSON object"]},
            },
            status=400,
        )
    model_id = body.get("model_id") or body.get("id")
    if not isinstance(model_id, str) or not model_id.strip():
        return JsonResponse(
            {
                "error": "validation_error",
                "details": {"model_id": ["Required"]},
            },
            status=400,
        )
    try:
        return JsonResponse(select_model(model_id))
    except RuntimeError as exc:
        return JsonResponse(
            {"error": "switch_failed", "details": str(exc)},
            status=502,
        )
    except ValueError as exc:
        return JsonResponse(
            {
                "error": "validation_error",
                "details": {"model_id": [str(exc)]},
            },
            status=400,
        )


def _format_ocr_chat_text(result: Mapping) -> str:
    doc_type = str(result.get("document_type") or "unknown")
    fields = result.get("fields") or {}
    lines = [f"Распознан документ: {doc_type}"]
    if isinstance(fields, Mapping):
        for key, payload in fields.items():
            label = FIELD_LABELS_RU.get(str(key), str(key))
            if isinstance(payload, Mapping) and "value" in payload:
                value = payload.get("value")
                conf = payload.get("confidence")
                if conf is not None:
                    pct = int(round(float(conf) * 100))
                    lines.append(f"— {label}: {value} ({pct}%)")
                else:
                    lines.append(f"— {label}: {value}")
            else:
                lines.append(f"— {label}: {payload}")
    status = result.get("validation_status") or (
        (result.get("validation") or {}).get("status")
        if isinstance(result.get("validation"), Mapping)
        else ""
    )
    if status:
        lines.append(f"Статус проверки: {status}")
    return "\n".join(lines)


@require_http_methods(["POST"])
@require_permissions(PERM_ASSISTANT_USE, api=True)
def assistant_attachment_extract(request: HttpRequest) -> JsonResponse:
    """POST /api/v1/assistant/attachments/extract — text for chat attachments."""
    uploaded = request.FILES.get("file")
    if uploaded is None:
        return JsonResponse(
            {
                "error": "validation_error",
                "details": {"file": ["file is required"]},
            },
            status=400,
        )
    filename = Path(getattr(uploaded, "name", "") or "file").name
    extension = Path(filename).suffix.lower()
    # Images / scan PDFs → OCR pipeline; office docs → text extract.
    if extension in CHAT_OCR_EXTENSIONS and extension not in {
        ".doc",
        ".docx",
        ".txt",
        ".rtf",
    }:
        # Prefer OCR for image scans; PDF may be either path.
        want_ocr = extension != ".pdf" or str(
            request.POST.get("mode") or request.GET.get("mode") or "auto"
        ).lower() in {"ocr", "auto"}
        if want_ocr and extension != ".pdf":
            return assistant_attachment_ocr(request)

    if extension not in CHAT_ATTACHMENT_EXTENSIONS | CHAT_OCR_EXTENSIONS:
        allowed = ", ".join(
            sorted(CHAT_ATTACHMENT_EXTENSIONS | CHAT_OCR_EXTENSIONS)
        )
        return JsonResponse(
            {
                "error": "validation_error",
                "details": {
                    "file": [f"unsupported type; allowed: {allowed}"],
                },
            },
            status=400,
        )
    data = uploaded.read()
    if len(data) > CHAT_ATTACHMENT_MAX_BYTES:
        return JsonResponse(
            {
                "error": "validation_error",
                "details": {
                    "file": [
                        f"file too large; max {CHAT_ATTACHMENT_MAX_BYTES} bytes"
                    ],
                },
            },
            status=400,
        )
    # PDF with scan intent or image-like content: OCR.
    if extension in CHAT_OCR_EXTENSIONS:
        mode = str(
            request.POST.get("mode") or request.GET.get("mode") or "auto"
        ).lower()
        if mode == "ocr" or extension != ".pdf":
            from ocr.pipeline import OcrPipelineError, recognize_bytes_inline

            try:
                recognized = recognize_bytes_inline(
                    data,
                    filename=filename,
                    content_type=getattr(uploaded, "content_type", "") or "",
                    created_by=getattr(request.user, "username", "") or "",
                    document_type_hint=str(
                        request.POST.get("document_type") or ""
                    ),
                )
            except OcrPipelineError as exc:
                return JsonResponse(
                    {
                        "error": "validation_error",
                        "details": {"file": [str(exc)]},
                    },
                    status=400,
                )
            result = recognized["result"]
            content_type = getattr(uploaded, "content_type", "") or ""
            return JsonResponse(
                {
                    "name": filename,
                    "type": extension.lstrip(".") or "ocr",
                    "content_type": content_type,
                    "size_bytes": len(data),
                    "text": _format_ocr_chat_text(result),
                    "ocr": {
                        "job_id": recognized["job"]["job_id"],
                        "document_id": recognized["job"]["document_id"],
                        "document_type": result.get("document_type"),
                        "fields": result.get("fields") or {},
                        "validation_status": result.get("validation_status"),
                        "pages": result.get("pages") or [],
                    },
                }
            )

    try:
        text = extract_document_text(filename, data)
    except KnowledgeBaseError as exc:
        return JsonResponse(
            {
                "error": "validation_error",
                "details": {"file": [str(exc)]},
            },
            status=400,
        )
    content_type = getattr(uploaded, "content_type", "") or ""
    kind = extension.lstrip(".") or content_type
    return JsonResponse(
        {
            "name": filename,
            "type": kind,
            "content_type": content_type,
            "size_bytes": len(data),
            "text": text,
        }
    )


@require_http_methods(["POST"])
@require_permissions(PERM_ASSISTANT_USE, api=True)
def assistant_attachment_ocr(request: HttpRequest) -> JsonResponse:
    """POST /api/v1/assistant/attachments/ocr — sync OCR + field extraction."""
    uploaded = request.FILES.get("file")
    if uploaded is None:
        return JsonResponse(
            {
                "error": "validation_error",
                "details": {"file": ["file is required"]},
            },
            status=400,
        )
    filename = Path(getattr(uploaded, "name", "") or "file").name
    extension = Path(filename).suffix.lower()
    if extension not in CHAT_OCR_EXTENSIONS:
        allowed = ", ".join(sorted(CHAT_OCR_EXTENSIONS))
        return JsonResponse(
            {
                "error": "validation_error",
                "details": {
                    "file": [f"unsupported type; allowed: {allowed}"],
                },
            },
            status=400,
        )
    data = uploaded.read()
    if len(data) > CHAT_ATTACHMENT_MAX_BYTES:
        return JsonResponse(
            {
                "error": "validation_error",
                "details": {
                    "file": [
                        f"file too large; max {CHAT_ATTACHMENT_MAX_BYTES} bytes"
                    ],
                },
            },
            status=400,
        )
    from ocr.pipeline import OcrPipelineError, recognize_bytes_inline

    try:
        recognized = recognize_bytes_inline(
            data,
            filename=filename,
            content_type=getattr(uploaded, "content_type", "") or "",
            created_by=getattr(request.user, "username", "") or "",
            document_type_hint=str(request.POST.get("document_type") or ""),
        )
    except OcrPipelineError as exc:
        return JsonResponse(
            {
                "error": "validation_error",
                "details": {"file": [str(exc)]},
            },
            status=400,
        )
    result = recognized["result"]
    content_type = getattr(uploaded, "content_type", "") or ""
    return JsonResponse(
        {
            "name": filename,
            "type": extension.lstrip(".") or "ocr",
            "content_type": content_type,
            "size_bytes": len(data),
            "text": _format_ocr_chat_text(result),
            "ocr": {
                "job_id": recognized["job"]["job_id"],
                "document_id": recognized["job"]["document_id"],
                "document_type": result.get("document_type"),
                "fields": result.get("fields") or {},
                "validation_status": result.get("validation_status"),
                "pages": result.get("pages") or [],
            },
        }
    )


@require_http_methods(["GET"])
@require_permissions(PERM_ASSISTANT_USE, api=True)
def assistant_source_download(request: HttpRequest) -> HttpResponse:
    """GET /api/v1/assistant/sources/download — open cited KB file from chat."""
    kb_slug = str(request.GET.get("kb_slug") or "").strip()
    article_raw = str(request.GET.get("article_id") or "").strip()
    if not kb_slug or not article_raw:
        return JsonResponse(
            {
                "error": "validation_error",
                "details": {
                    "request": ["kb_slug and article_id are required"],
                },
            },
            status=400,
        )
    try:
        article_id = int(article_raw)
    except ValueError:
        return JsonResponse(
            {
                "error": "validation_error",
                "details": {"article_id": ["must be an integer"]},
            },
            status=400,
        )
    try:
        document = AssistantKnowledgeBaseDocument.objects.select_related(
            "knowledge_base"
        ).get(
            article_id=article_id,
            knowledge_base__slug=kb_slug,
        )
    except AssistantKnowledgeBaseDocument.DoesNotExist:
        return JsonResponse({"error": "not_found"}, status=404)

    filename = Path(document.filename).name or "document.bin"
    original = resolve_assistant_original_path(document)
    if original is not None:
        content_type = document.content_type or "application/octet-stream"
        response = FileResponse(
            original.open("rb"),
            as_attachment=True,
            filename=filename,
            content_type=content_type,
        )
        response["X-Source-Filename"] = iri_to_uri(filename)
        return response

    # Legacy docs without stored original: serve extracted text for open/view.
    text = (document.extracted_text or "").strip()
    if not text:
        return JsonResponse(
            {
                "error": "not_found",
                "details": {
                    "file": [
                        "Original file is not stored; re-upload the document "
                        "to enable download from chat sources."
                    ],
                },
            },
            status=404,
        )
    stem = Path(filename).stem or "document"
    fallback_name = f"{stem}.txt"
    response = HttpResponse(
        text.encode("utf-8"),
        content_type="text/plain; charset=utf-8",
    )
    response["Content-Disposition"] = (
        f'attachment; filename="{fallback_name}"'
    )
    response["X-Source-Filename"] = iri_to_uri(fallback_name)
    response["X-Source-Fallback"] = "extracted_text"
    return response


@require_http_methods(["POST"])
@require_permissions(PERM_ASSISTANT_USE, api=True)
def assistant_chat(request: HttpRequest) -> StreamingHttpResponse | JsonResponse:
    """POST /api/v1/assistant/chat — SSE stream via ModelGateway assistant_bank."""
    try:
        body = json.loads(request.body or b"{}")
        if not isinstance(body, Mapping):
            raise AssistantChatError("Request body must be a JSON object")
        parsed = parse_chat_request(body)
    except json.JSONDecodeError:
        return _validation_error(
            AssistantChatError("Request body must be valid JSON")
        )
    except AssistantChatError as exc:
        return _validation_error(exc)

    request_id = getattr(request, "audit_request_id", None) or parsed[
        "session_id"
    ]

    def event_stream():
        yield from iter_chat_sse(
            parsed["messages"],
            kb_slugs=parsed.get("kb_slugs") or [],
            request_id=str(request_id),
        )

    response = StreamingHttpResponse(
        event_stream(),
        content_type="text/event-stream; charset=utf-8",
    )
    response["Cache-Control"] = "no-cache, no-transform"
    response["X-Accel-Buffering"] = "no"
    response["X-Request-ID"] = str(request_id)
    response["X-Assistant-Profile"] = "assistant_bank"
    response["X-Session-ID"] = parsed["session_id"]
    return response


@require_http_methods(["GET"])
def assistant_openapi(request: HttpRequest) -> JsonResponse:
    """GET /api/v1/assistant/openapi.json — generated OpenAPI 3 schema."""
    return JsonResponse(build_openapi_document())


@require_http_methods(["GET"])
@require_permissions(PERM_ASSISTANT_REPORTS, api=True)
def assistant_reports_catalog(request: HttpRequest) -> JsonResponse:
    """GET /api/v1/assistant/reports/ — FR-RPT-ASS catalog (III.10.2)."""
    return JsonResponse(catalog())


@require_http_methods(["GET"])
@require_permissions(PERM_ASSISTANT_REPORTS, api=True)
def assistant_reports_analytics(request: HttpRequest) -> JsonResponse:
    """GET /api/v1/assistant/reports/analytics/ — usage, feedback, tools."""
    try:
        filters = parse_report_filters(request.GET)
        return JsonResponse(build_analytics(filters))
    except AssReportsError as exc:
        return _reports_validation_error(exc)


@require_http_methods(["GET"])
@require_permissions(PERM_ASSISTANT_REPORTS, api=True)
def assistant_report_detail(request: HttpRequest, report_id: str) -> JsonResponse:
    """GET /api/v1/assistant/reports/<FR-RPT-ASS-XX>/ — single FR section."""
    try:
        filters = parse_report_filters(request.GET)
        filters["report_id"] = report_id
        if report_id not in {
            item["id"] for item in catalog()["items"]
        }:
            raise AssReportsError(f"Unknown report_id: {report_id}")
        payload = build_analytics(filters)
        payload["report_id"] = report_id
        return JsonResponse(payload)
    except AssReportsError as exc:
        return _reports_validation_error(exc)


@require_http_methods(["GET"])
@require_permissions(PERM_ASSISTANT_REPORTS, api=True)
def assistant_reports_export(request: HttpRequest) -> HttpResponse:
    """GET /api/v1/assistant/reports/export/ — CSV/XLSX (FR-RPT-ASS-07)."""
    try:
        filters = parse_report_filters(request.GET)
        analytics = build_analytics(filters)
        export_format = filters["format"]
        if export_format == "xlsx":
            payload = build_xlsx_export(analytics)
            content_type = (
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            )
        else:
            payload = build_csv_export(analytics)
            content_type = "text/csv; charset=utf-8"
        filename = export_filename(filters, export_format)
    except AssReportsError as exc:
        return _reports_validation_error(exc)

    response = HttpResponse(payload, content_type=content_type)
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response["X-FR-Catalog"] = "FR-RPT-ASS"
    return response
