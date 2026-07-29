"""HTTP API for ASR QA catalogue (FR-ASR-10) and CC reports (FR-RPT-CC / II.6)."""

from __future__ import annotations

import json
from typing import Mapping

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.views.decorators.http import require_http_methods

from auth.decorators import require_permissions
from auth.roles import PERM_CC_REPORTS
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
from reports.models import AsrDialogueSession


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
@require_permissions(PERM_CC_REPORTS, api=True)
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
@require_permissions(PERM_CC_REPORTS, api=True)
def asr_session_detail(request: HttpRequest, session_id: int) -> JsonResponse:
    try:
        return JsonResponse(get_session(session_id))
    except AsrDialogueSession.DoesNotExist:
        return JsonResponse({"error": "not_found"}, status=404)


@require_http_methods(["GET"])
@require_permissions(PERM_CC_REPORTS, api=True)
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
@require_permissions(PERM_CC_REPORTS, api=True)
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
            username=request.user.get_username(),
        )
    except json.JSONDecodeError:
        return _validation_error(AsrQaError("Request body must be valid JSON"))
    except AsrQaError as exc:
        return _validation_error(exc)
    except AsrDialogueSession.DoesNotExist:
        return JsonResponse({"error": "not_found"}, status=404)
    return JsonResponse(result)


@require_http_methods(["POST"])
@require_permissions(PERM_CC_REPORTS, api=True)
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
@require_permissions(PERM_CC_REPORTS, api=True)
def cc_analytics(request: HttpRequest) -> JsonResponse:
    """FR-RPT-CC stub dashboard: tables + ASR quality series."""
    try:
        filters = parse_analytics_filters(request.GET)
        payload = build_analytics(filters)
    except CcAnalyticsError as exc:
        return _cc_validation_error(exc)
    return JsonResponse(payload)


@require_http_methods(["GET"])
@require_permissions(PERM_CC_REPORTS, api=True)
def cc_export(request: HttpRequest) -> HttpResponse:
    """CSV / XLSX export for CC analytics (FR-RPT-CC / FR-ASR-19)."""
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
        else:
            payload = build_csv_export(analytics)
            content_type = "text/csv; charset=utf-8"
        filename = export_filename(filters, export_format)
    except CcAnalyticsError as exc:
        return _cc_validation_error(exc)

    response = HttpResponse(payload, content_type=content_type)
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response
