"""Mock Telegram / Viber channel webhooks (FR-CC-09 / UC-A5)."""

from __future__ import annotations

import json
import uuid
from typing import Any, Mapping

from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

# In-memory inbox for local demos / CHAT-T-12 style checks.
_INBOX: list[dict[str, Any]] = []


class ChannelWebhookError(ValueError):
    """Invalid messenger webhook payload."""


def reset_inbox() -> None:
    _INBOX.clear()


def list_inbox() -> list[dict[str, Any]]:
    return list(_INBOX)


def _json_body(request: HttpRequest) -> Mapping[str, Any]:
    try:
        payload = json.loads(request.body or b"{}")
    except json.JSONDecodeError as exc:
        raise ChannelWebhookError("Request body must be valid JSON") from exc
    if not isinstance(payload, Mapping):
        raise ChannelWebhookError("Request body must be a JSON object")
    return payload


def _store(
    *,
    channel: str,
    external_user_id: str,
    text: str,
    raw: Mapping[str, Any],
) -> dict[str, Any]:
    event = {
        "id": str(uuid.uuid4()),
        "channel": channel,
        "external_user_id": external_user_id,
        "text": text,
        "routed_to": "arm_queue",
        "raw": dict(raw),
    }
    _INBOX.append(event)
    return event


def handle_telegram_update(payload: Mapping[str, Any]) -> dict[str, Any]:
    message = payload.get("message") or payload.get("edited_message") or {}
    if not isinstance(message, Mapping):
        raise ChannelWebhookError("telegram payload requires message object")
    text = message.get("text") or message.get("caption") or ""
    if not isinstance(text, str) or not text.strip():
        raise ChannelWebhookError("telegram message text is required")
    chat = message.get("chat") or {}
    user = message.get("from") or {}
    external_id = str(
        (chat.get("id") if isinstance(chat, Mapping) else None)
        or (user.get("id") if isinstance(user, Mapping) else None)
        or "unknown"
    )
    event = _store(
        channel="telegram",
        external_user_id=external_id,
        text=text.strip(),
        raw=payload,
    )
    return {
        "ok": True,
        "channel": "telegram",
        "event_id": event["id"],
        "routed_to": "arm_queue",
        "reply": {
            "method": "sendMessage",
            "chat_id": external_id,
            "text": "Сообщение принято (mock Telegram). Оператор ответит в АРМ.",
        },
    }


def handle_viber_event(payload: Mapping[str, Any]) -> dict[str, Any]:
    event_type = str(payload.get("event") or "message")
    if event_type in {"webhook", "subscribed", "unsubscribed", "conversation_started"}:
        return {"ok": True, "channel": "viber", "event": event_type, "status": 0}
    message = payload.get("message") or {}
    if not isinstance(message, Mapping):
        raise ChannelWebhookError("viber payload requires message object")
    text = message.get("text") or ""
    if not isinstance(text, str) or not text.strip():
        raise ChannelWebhookError("viber message text is required")
    sender = payload.get("sender") or {}
    external_id = str(
        (sender.get("id") if isinstance(sender, Mapping) else None) or "unknown"
    )
    event = _store(
        channel="viber",
        external_user_id=external_id,
        text=text.strip(),
        raw=payload,
    )
    return {
        "ok": True,
        "channel": "viber",
        "event_id": event["id"],
        "routed_to": "arm_queue",
        "status": 0,
        "reply": {
            "type": "text",
            "text": "Сообщение принято (mock Viber). Оператор ответит в АРМ.",
        },
    }


def handle_widget_message(
    widget_id: str,
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    text = payload.get("text") or ""
    if not isinstance(text, str) or not text.strip():
        raise ChannelWebhookError("text must be a non-empty string")
    if not widget_id.strip():
        raise ChannelWebhookError("widget_id is required")
    placement = str(payload.get("placement") or "website")
    event = _store(
        channel="widget",
        external_user_id=widget_id,
        text=text.strip(),
        raw={**dict(payload), "widget_id": widget_id, "placement": placement},
    )
    return {
        "ok": True,
        "channel": "widget",
        "widget_id": widget_id,
        "placement": placement,
        "event_id": event["id"],
        "routed_to": "arm_queue",
        "reply": (
            "Спасибо! Ваше сообщение принято виджетом "
            f"«{widget_id}». Оператор ответит в ближайшее время."
        ),
    }


def _error(exc: ChannelWebhookError) -> JsonResponse:
    return JsonResponse(
        {"ok": False, "error": "validation_error", "detail": str(exc)},
        status=400,
    )


@csrf_exempt
@require_http_methods(["POST"])
def telegram_webhook(request: HttpRequest) -> JsonResponse:
    try:
        return JsonResponse(handle_telegram_update(_json_body(request)))
    except ChannelWebhookError as exc:
        return _error(exc)


@csrf_exempt
@require_http_methods(["POST"])
def viber_webhook(request: HttpRequest) -> JsonResponse:
    try:
        return JsonResponse(handle_viber_event(_json_body(request)))
    except ChannelWebhookError as exc:
        return _error(exc)


@csrf_exempt
@require_http_methods(["POST"])
def widget_message(request: HttpRequest, widget_id: str) -> JsonResponse:
    try:
        return JsonResponse(handle_widget_message(widget_id, _json_body(request)))
    except ChannelWebhookError as exc:
        return _error(exc)


@require_http_methods(["GET"])
def channel_inbox(request: HttpRequest) -> JsonResponse:
    return JsonResponse({"items": list_inbox(), "count": len(_INBOX)})
