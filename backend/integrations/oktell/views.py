"""HTTP API for vendor pickup POST and operator call list."""

from __future__ import annotations

import json
import hmac
from typing import Any, Mapping

from django.conf import settings
from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_http_methods

from auth.decorators import require_permissions
from auth.roles import PERM_SUFLER_CHAT, PERM_SUFLER_TELEPHONY
from integrations.oktell.call_hub import hub
from integrations.oktell.sip_pool import as_settings_snapshot
from integrations.oktell.webhook import OktellWebhookError, parse_pickup_payload


def _json_body(request: HttpRequest) -> Mapping[str, Any]:
    try:
        payload = json.loads(request.body or b"{}")
    except json.JSONDecodeError as exc:
        raise OktellWebhookError("body must be valid JSON") from exc
    if not isinstance(payload, Mapping):
        raise OktellWebhookError("body must be a JSON object")
    return payload


def _webhook_authorized(request: HttpRequest) -> bool:
    secret = str(getattr(settings, "OKTELL_WEBHOOK_SECRET", "") or "")
    if not secret:
        return True
    offered = (
        request.headers.get("X-Oktell-Token")
        or request.headers.get("X-Sufler-Oktell-Token")
        or ""
    )
    return hmac.compare_digest(offered, secret)


@csrf_exempt
@require_http_methods(["POST"])
def oktell_call_started(request: HttpRequest) -> JsonResponse:
    """Vendor POST after the operator answers (CallerID / CalledID / Idchain)."""
    if not _webhook_authorized(request):
        return JsonResponse({"error": "auth"}, status=401)
    try:
        pickup = parse_pickup_payload(_json_body(request))
        call, created = hub.start(pickup)
    except OktellWebhookError as exc:
        return JsonResponse({"error": "validation", "detail": str(exc)}, status=400)
    except RuntimeError as exc:
        return JsonResponse({"error": "misconfigured", "detail": str(exc)}, status=503)
    return JsonResponse({"created": created, "call": call.as_dict()}, status=201 if created else 200)


@csrf_exempt
@require_http_methods(["POST"])
def oktell_call_stopped(request: HttpRequest) -> JsonResponse:
    if not _webhook_authorized(request):
        return JsonResponse({"error": "auth"}, status=401)
    try:
        pickup = parse_pickup_payload(_json_body(request))
    except OktellWebhookError as exc:
        return JsonResponse({"error": "validation", "detail": str(exc)}, status=400)
    call = hub.stop(pickup.idchain)
    if call is None:
        return JsonResponse({"error": "not_found", "Idchain": pickup.idchain}, status=404)
    return JsonResponse({"call": call.as_dict()})


@require_GET
@require_permissions(PERM_SUFLER_TELEPHONY, PERM_SUFLER_CHAT, require_all=False, api=True)
def oktell_calls(request: HttpRequest) -> JsonResponse:
    calls = [call.as_dict() for call in hub.list_calls() if call.state != "stopped"]
    return JsonResponse({"calls": calls, "listen": as_settings_snapshot()})


@require_GET
@require_permissions(PERM_SUFLER_TELEPHONY, PERM_SUFLER_CHAT, require_all=False, api=True)
def oktell_call_detail(request: HttpRequest, idchain: str) -> JsonResponse:
    call = hub.get(idchain)
    if call is None:
        return JsonResponse({"error": "not_found"}, status=404)
    return JsonResponse({"call": call.as_dict()})
