"""HTTP API for ASR QA catalogue (FR-ASR-10) and CC reports (FR-RPT-CC / II.6)."""

from __future__ import annotations

import json
from functools import wraps
from typing import Any, Callable, Mapping

from django.conf import settings
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.views.decorators.http import require_http_methods

from auth.decorators import permission_denied_response
from auth.roles import PERM_CC_REPORTS, has_permission
from reports.asr_qa import (
    AsrQaError,
    build_silence_wav,
    catalogue_stats,
    get_session,
    list_sessions,
    parse_filters,
    seed_demo_sessions,
    set_training_candidate,
)
from reports.cc_analytics import (
    CcAnalyticsError,
    build_analytics,
    build_csv_export,
    build_xlsx_export,
    export_filename,
    parse_analytics_filters,
)
from reports.cc_catalog import (
    build_report_payload,
    list_builder_templates,
    preview_builder,
)
from reports.cc_live import build_live_dashboard
from reports.cc_pdf import build_pdf_export
from reports.models import AsrDialogueSession

View = Callable[..., HttpResponse]


def require_cc_reports(view: View) -> View:
    """PERM_CC_REPORTS; in DEBUG open the module for local SPA without RBAC friction."""

    @wraps(view)
    def wrapped(request: HttpRequest, *args: Any, **kwargs: Any) -> Any:
        if has_permission(request.user, PERM_CC_REPORTS):
            return view(request, *args, **kwargs)
        if settings.DEBUG:
            return view(request, *args, **kwargs)
        return permission_denied_response(
            request,
            required=(PERM_CC_REPORTS,),
            force_json=True,
        )

    return wrapped


def _cc_validation_error(exc: CcAnalyticsError) -> JsonResponse:
    return JsonResponse(
        {
            "error": "validation_error",
            "details": {"request": [str(exc)]},
        },
        status=400,
    )


def _validation_error(exc: AsrQaError) -> JsonResponse:
    return JsonResponse(
        {
            "error": "validation_error",
            "details": {"request": [str(exc)]},
        },
        status=400,
    )


@require_http_methods(["GET"])
@require_cc_reports
def asr_sessions(request: HttpRequest) -> JsonResponse:
    try:
        filters = parse_filters(request.GET)
        items = list_sessions(**filters)
    except AsrQaError as exc:
        return _validation_error(exc)
    return JsonResponse(
        {
            "items": items,
            "stats": catalogue_stats(),
            "filters": filters,
        }
    )


@require_http_methods(["GET"])
@require_cc_reports
def asr_session_detail(request: HttpRequest, session_id: int) -> JsonResponse:
    try:
        return JsonResponse(get_session(session_id))
    except AsrDialogueSession.DoesNotExist:
        return JsonResponse({"error": "not_found"}, status=404)


@require_http_methods(["GET"])
@require_cc_reports
def asr_session_audio(request: HttpRequest, session_id: int) -> HttpResponse:
    try:
        session = AsrDialogueSession.objects.get(pk=session_id)
    except AsrDialogueSession.DoesNotExist:
        return JsonResponse({"error": "not_found"}, status=404)
    if session.channel != AsrDialogueSession.CHANNEL_TELEPHONY:
        return JsonResponse(
            {
                "error": "audio_unavailable",
                "detail": "chat sessions have no audio",
            },
            status=404,
        )
    payload = build_silence_wav(
        duration_sec=max(1.0, float(session.duration_sec or 1))
    )
    response = HttpResponse(payload, content_type="audio/wav")
    response["Content-Disposition"] = (
        f'inline; filename="{session.session_id}.wav"'
    )
    return response


@require_http_methods(["POST"])
@require_cc_reports
def asr_utterance_annotation(
    request: HttpRequest,
    session_id: int,
    utterance_id: int,
) -> JsonResponse:
    try:
        body = json.loads(request.body or b"{}")
        if not isinstance(body, Mapping):
            raise AsrQaError("Request body must be a JSON object")
        if "training_candidate" not in body:
            raise AsrQaError("training_candidate is required")
        result = set_training_candidate(
            session_id,
            utterance_id,
            training_candidate=bool(body.get("training_candidate")),
            username=request.user.get_username()
            if getattr(request.user, "is_authenticated", False)
            else "demo",
        )
    except json.JSONDecodeError:
        return _validation_error(AsrQaError("Request body must be valid JSON"))
    except AsrQaError as exc:
        return _validation_error(exc)
    except AsrDialogueSession.DoesNotExist:
        return JsonResponse({"error": "not_found"}, status=404)
    return JsonResponse(result)


@require_http_methods(["POST"])
@require_cc_reports
def asr_seed_demo(request: HttpRequest) -> JsonResponse:
    """Seed deterministic demo catalogue (local/acceptance)."""
    force = False
    try:
        body = json.loads(request.body or b"{}")
        if isinstance(body, Mapping):
            force = bool(body.get("force"))
    except json.JSONDecodeError:
        pass
    items = seed_demo_sessions(force=force)
    return JsonResponse({"items": items, "stats": catalogue_stats()})


@require_http_methods(["GET"])
@require_cc_reports
def cc_analytics(request: HttpRequest) -> JsonResponse:
    """FR-RPT-CC dashboard: tables + ASR quality series."""
    try:
        filters = parse_analytics_filters(request.GET)
        payload = build_analytics(filters)
    except CcAnalyticsError as exc:
        return _cc_validation_error(exc)
    return JsonResponse(payload)


@require_http_methods(["GET"])
@require_cc_reports
def cc_export(request: HttpRequest) -> HttpResponse:
    """CSV / XLSX / PDF export for CC analytics."""
    try:
        filters = parse_analytics_filters(request.GET)
        analytics = build_analytics(filters)
        export_format = filters["format"]
        if export_format == "xlsx":
            payload = build_xlsx_export(analytics)
            content_type = (
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            )
        elif export_format == "pdf":
            payload = build_pdf_export(analytics)
            content_type = "application/pdf"
        else:
            payload = build_csv_export(analytics)
            content_type = "text/csv; charset=utf-8"
        filename = export_filename(filters, export_format)
    except CcAnalyticsError as exc:
        return _cc_validation_error(exc)

    response = HttpResponse(payload, content_type=content_type)
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


@require_http_methods(["GET"])
@require_cc_reports
def cc_live(request: HttpRequest) -> JsonResponse:
    return JsonResponse(build_live_dashboard())


@require_http_methods(["GET"])
@require_cc_reports
def cc_report_catalog(request: HttpRequest) -> JsonResponse:
    try:
        return JsonResponse(build_report_payload(request.GET))
    except CcAnalyticsError as exc:
        return _cc_validation_error(exc)


@require_http_methods(["GET"])
@require_cc_reports
def cc_builder_templates(request: HttpRequest) -> JsonResponse:
    return JsonResponse(list_builder_templates())


@require_http_methods(["POST"])
@require_cc_reports
def cc_builder_preview(request: HttpRequest) -> JsonResponse:
    try:
        body = json.loads(request.body or b"{}")
        if not isinstance(body, Mapping):
            raise CcAnalyticsError("Request body must be a JSON object")
    except (json.JSONDecodeError, CcAnalyticsError) as exc:
        return JsonResponse(
            {"error": "validation_error", "details": {"request": [str(exc)]}},
            status=400,
        )
    return JsonResponse(preview_builder(dict(body)))


