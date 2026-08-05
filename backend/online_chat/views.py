from __future__ import annotations

import json
from typing import Any, Mapping

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from online_chat.models import Dialog, DialogMessage
from online_chat.services import (
    accept_dialog,
    append_message,
    block_dialog,
    close_dialog,
    create_dialog_with_message,
    serialize_dialog,
    serialize_message,
)


class OnlineChatApiError(ValueError):
    """Invalid online-chat API payload."""


def _json_body(request: HttpRequest) -> Mapping[str, Any]:
    try:
        payload = json.loads(request.body or b"{}")
    except json.JSONDecodeError as exc:
        raise OnlineChatApiError("Request body must be valid JSON") from exc
    if not isinstance(payload, Mapping):
        raise OnlineChatApiError("Request body must be a JSON object")
    return payload


def _error(exc: OnlineChatApiError, status: int = 400) -> JsonResponse:
    return JsonResponse(
        {"ok": False, "error": "validation_error", "detail": str(exc)},
        status=status,
    )


def _str_field(payload: Mapping[str, Any], key: str, default: str = "") -> str:
    value = payload.get(key, default)
    if value is None:
        return default
    if not isinstance(value, str):
        raise OnlineChatApiError(f"{key} must be a string")
    return value.strip()


@csrf_exempt
@require_http_methods(["GET", "POST"])
def dialogs_collection(request: HttpRequest) -> HttpResponse:
    if request.method == "GET":
        status = (request.GET.get("status") or "").strip()
        qs = Dialog.objects.all()
        if status:
            qs = qs.filter(status=status)
        items = [serialize_dialog(dialog) for dialog in qs[:200]]
        return JsonResponse({"ok": True, "items": items, "count": len(items)})

    try:
        payload = _json_body(request)
        text = _str_field(payload, "text")
        if not text:
            raise OnlineChatApiError("text must be a non-empty string")
        dialog, message = create_dialog_with_message(
            text=text,
            widget_id=_str_field(payload, "widget_id", "site-belarusbank")
            or "site-belarusbank",
            placement=_str_field(payload, "placement", "website") or "website",
            client_first_name=_str_field(payload, "first_name")
            or _str_field(payload, "name"),
            client_last_name=_str_field(payload, "last_name"),
            client_phone=_str_field(payload, "phone"),
            channel=_str_field(payload, "channel", "widget") or "widget",
        )
        return JsonResponse(
            {
                "ok": True,
                "dialog": serialize_dialog(dialog, include_messages=True),
                "message": serialize_message(message),
            },
            status=201,
        )
    except OnlineChatApiError as exc:
        return _error(exc)


@csrf_exempt
@require_http_methods(["GET"])
def dialog_detail(request: HttpRequest, dialog_id: str) -> HttpResponse:
    dialog = get_object_or_404(Dialog, pk=dialog_id)
    return JsonResponse(
        {"ok": True, "dialog": serialize_dialog(dialog, include_messages=True)},
    )


@csrf_exempt
@require_http_methods(["GET", "POST"])
def dialog_messages(request: HttpRequest, dialog_id: str) -> HttpResponse:
    dialog = get_object_or_404(Dialog, pk=dialog_id)
    if request.method == "GET":
        items = [serialize_message(item) for item in dialog.messages.all()]
        return JsonResponse({"ok": True, "items": items, "count": len(items)})

    try:
        payload = _json_body(request)
        text = _str_field(payload, "text")
        if not text:
            raise OnlineChatApiError("text must be a non-empty string")
        speaker = _str_field(payload, "speaker", DialogMessage.Speaker.CLIENT)
        if speaker not in {
            DialogMessage.Speaker.CLIENT,
            DialogMessage.Speaker.OPERATOR,
            DialogMessage.Speaker.SYSTEM,
        }:
            raise OnlineChatApiError("speaker must be client, operator, or system")
        if dialog.status in {Dialog.Status.CLOSED, Dialog.Status.BLOCKED}:
            raise OnlineChatApiError("dialog is closed")
        message = append_message(dialog, speaker=speaker, text=text)
        return JsonResponse(
            {"ok": True, "message": serialize_message(message)},
            status=201,
        )
    except OnlineChatApiError as exc:
        return _error(exc)


@csrf_exempt
@require_http_methods(["POST"])
def dialog_accept(request: HttpRequest, dialog_id: str) -> HttpResponse:
    dialog = get_object_or_404(Dialog, pk=dialog_id)
    try:
        payload = _json_body(request)
        operator_name = _str_field(payload, "operator_name", "Иванов И.И.") or "Иванов И.И."
        if dialog.status == Dialog.Status.CLOSED:
            raise OnlineChatApiError("dialog is closed")
        accept_dialog(dialog, operator_name)
        return JsonResponse(
            {"ok": True, "dialog": serialize_dialog(dialog, include_messages=True)},
        )
    except OnlineChatApiError as exc:
        return _error(exc)


@csrf_exempt
@require_http_methods(["POST"])
def dialog_close(request: HttpRequest, dialog_id: str) -> HttpResponse:
    dialog = get_object_or_404(Dialog, pk=dialog_id)
    close_dialog(dialog)
    return JsonResponse({"ok": True, "dialog": serialize_dialog(dialog)})


@csrf_exempt
@require_http_methods(["POST"])
def dialog_block(request: HttpRequest, dialog_id: str) -> HttpResponse:
    dialog = get_object_or_404(Dialog, pk=dialog_id)
    block_dialog(dialog)
    return JsonResponse({"ok": True, "dialog": serialize_dialog(dialog)})
