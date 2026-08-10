"""HTTP API for AI Assistant chat and FR-RPT-ASS reports (III.7 / III.10)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping

from django.http import HttpRequest, HttpResponse, JsonResponse, StreamingHttpResponse
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
from hub.assistant_admin import list_chat_knowledge_bases
from hub.kb_admin import KnowledgeBaseError, extract_document_text

CHAT_ATTACHMENT_EXTENSIONS = frozenset(
    {".pdf", ".doc", ".docx", ".txt", ".rtf"}
)
CHAT_ATTACHMENT_MAX_BYTES = 10 * 1024 * 1024


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
    if extension not in CHAT_ATTACHMENT_EXTENSIONS:
        allowed = ", ".join(sorted(CHAT_ATTACHMENT_EXTENSIONS))
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
