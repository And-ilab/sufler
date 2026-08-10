from __future__ import annotations

import json
import re
import uuid
from collections.abc import Mapping
from functools import wraps
from typing import Any
from urllib.parse import quote, urlparse

from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import validate_email
from django.db.models import Avg, Count, Q
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from auth.roles import (
    PERM_CC_ADMIN,
    PERM_CC_REPORTS,
    PERM_SUFLER_CHAT,
    has_permission,
)
from online_chat.models import (
    BotConfiguration,
    ChannelConnection,
    ClientBlock,
    Department,
    Dialog,
    DialogFeedback,
    DialogMessage,
    InternalMessage,
    OperatorProfile,
    RoutingRule,
    WidgetPlacement,
    normalize_phone,
)
from online_chat.storage import get_chat_object_store
from online_chat.routing_services import (
    accept_waiting_dialog,
    run_assignments,
    transfer_to_operator,
    update_operator_presence,
)
from online_chat.services import (
    accept_dialog,
    append_message,
    block_dialog,
    close_dialog,
    create_dialog_with_message,
    delete_message,
    edit_message,
    mark_dialog_messages_read,
    request_transcript_email,
    save_feedback,
    serialize_client_block,
    serialize_dialog,
    serialize_feedback,
    serialize_message,
    serialize_transcript_email,
    set_client_presence,
    transfer_dialog,
    unblock_client,
)

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class OnlineChatApiError(ValueError):
    """Invalid online-chat API payload."""


def _chat_permissions(*permissions: str):
    """Require one permission in non-DEBUG environments."""

    def decorator(view):
        @wraps(view)
        def wrapped(request: HttpRequest, *args: Any, **kwargs: Any):
            if settings.DEBUG or any(
                has_permission(request.user, permission)
                for permission in permissions
            ):
                return view(request, *args, **kwargs)
            return JsonResponse(
                {
                    "ok": False,
                    "error": "forbidden",
                    "required_permissions": list(permissions),
                },
                status=403,
            )

        return wrapped

    return decorator


def _operator_write_denied(
    request: HttpRequest,
    dialog: Dialog,
    *,
    claimed_name: str = "",
) -> JsonResponse | None:
    is_admin = has_permission(request.user, PERM_CC_ADMIN)
    can_chat = has_permission(request.user, PERM_SUFLER_CHAT)
    if not settings.DEBUG and not (is_admin or can_chat):
        return JsonResponse(
            {"ok": False, "error": "forbidden"},
            status=403,
        )
    profile = None
    if getattr(request.user, "is_authenticated", False):
        profile = OperatorProfile.objects.filter(
            external_id=request.user.get_username(),
            is_active=True,
        ).first()
    actor_name = profile.display_name if profile else claimed_name.strip()
    # Never write to another operator's dialog (including module admin / spoofed name).
    if (
        dialog.operator_name
        and actor_name
        and actor_name != dialog.operator_name
    ):
        return JsonResponse(
            {
                "ok": False,
                "error": "colleague_dialog_read_only",
                "detail": "Диалог коллеги доступен только для чтения",
            },
            status=403,
        )
    return None


def _strip_suz_links(text: str) -> str:
    without_markdown_urls = re.sub(
        r"\[([^\]]+)\]\(https?://[^)\s]+\)",
        r"\1",
        text,
        flags=re.IGNORECASE,
    )
    without_urls = re.sub(
        r"(?:https?://|www\.)\S+",
        "",
        without_markdown_urls,
        flags=re.IGNORECASE,
    )
    return re.sub(r"[ \t]{2,}", " ", without_urls).strip()


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


def _int_field(payload: Mapping[str, Any], key: str) -> int:
    value = payload.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise OnlineChatApiError(f"{key} must be an integer")
    return value


@csrf_exempt
@require_http_methods(["GET", "POST"])
def dialogs_collection(request: HttpRequest) -> HttpResponse:
    if request.method == "GET":
        status = (request.GET.get("status") or "").strip()
        qs = Dialog.objects.all()
        if status:
            qs = qs.filter(status=status)
        online = (request.GET.get("client_online") or "").strip().lower()
        if online in {"1", "true", "yes"}:
            qs = qs.filter(client_online=True)
        elif online in {"0", "false", "no"}:
            qs = qs.filter(client_online=False)
        initiated_by = (request.GET.get("initiated_by") or "").strip()
        if initiated_by:
            qs = qs.filter(initiated_by=initiated_by)
        external_id = (request.GET.get("client_external_id") or "").strip()
        if external_id:
            qs = qs.filter(client_external_id=external_id)
        if request.GET.get("operator_id"):
            qs = qs.filter(operator_id=request.GET["operator_id"])
        if request.GET.get("operator_name"):
            qs = qs.filter(operator_name=request.GET["operator_name"])
        if request.GET.get("department_id"):
            qs = qs.filter(department_id=request.GET["department_id"])
        if request.GET.get("channel"):
            qs = qs.filter(channel=request.GET["channel"])
        items = [serialize_dialog(dialog) for dialog in qs[:200]]
        return JsonResponse({"ok": True, "items": items, "count": len(items)})

    try:
        payload = _json_body(request)
        text = _str_field(payload, "text")
        attachment_name = _str_field(payload, "attachment_name")
        if not text and not attachment_name:
            raise OnlineChatApiError("text must be a non-empty string")
        initiated_by = (
            _str_field(payload, "initiated_by", Dialog.InitiatedBy.CLIENT)
            or Dialog.InitiatedBy.CLIENT
        )
        if initiated_by not in {
            Dialog.InitiatedBy.CLIENT,
            Dialog.InitiatedBy.OPERATOR,
        }:
            raise OnlineChatApiError("initiated_by must be client or operator")
        try:
            dialog, message = create_dialog_with_message(
                text=text or f"Файл: {attachment_name}",
                widget_id=_str_field(payload, "widget_id", "site-belarusbank")
                or "site-belarusbank",
                placement=_str_field(payload, "placement", "website") or "website",
                client_first_name=_str_field(payload, "first_name")
                or _str_field(payload, "name"),
                client_last_name=_str_field(payload, "last_name"),
                client_phone=_str_field(payload, "phone"),
                client_external_id=_str_field(payload, "client_external_id"),
                entry_url=_str_field(payload, "entry_url")
                or _str_field(payload, "page_url"),
                locale=_str_field(payload, "locale", "ru") or "ru",
                channel=_str_field(payload, "channel", "widget") or "widget",
                initiated_by=initiated_by,
                operator_name=_str_field(payload, "operator_name"),
            )
        except PermissionError as exc:
            return JsonResponse(
                {
                    "ok": False,
                    "error": "client_blocked",
                    "detail": str(exc),
                },
                status=403,
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
        attachment_name = _str_field(payload, "attachment_name")
        if not text and not attachment_name:
            raise OnlineChatApiError("text or attachment_name is required")
        speaker = _str_field(payload, "speaker", DialogMessage.Speaker.CLIENT)
        if speaker not in {
            DialogMessage.Speaker.CLIENT,
            DialogMessage.Speaker.OPERATOR,
            DialogMessage.Speaker.SYSTEM,
        }:
            raise OnlineChatApiError("speaker must be client, operator, or system")
        if speaker == DialogMessage.Speaker.OPERATOR:
            denied = _operator_write_denied(
                request,
                dialog,
                claimed_name=_str_field(payload, "operator_name"),
            )
            if denied:
                return denied
        response_origin = _str_field(payload, "response_origin")
        suggestion_text = _str_field(payload, "sufler_suggestion_text")
        if response_origin == "sufler":
            text = _strip_suz_links(text)
            if not text and not attachment_name:
                raise OnlineChatApiError("answer is empty after link removal")
        if dialog.status in {Dialog.Status.CLOSED, Dialog.Status.BLOCKED}:
            raise OnlineChatApiError("dialog is closed")
        reply_to = None
        reply_to_id = _str_field(payload, "reply_to_id")
        if reply_to_id:
            reply_to = dialog.messages.filter(pk=reply_to_id).first()
            if reply_to is None:
                raise OnlineChatApiError("reply_to_id not found in dialog")
        message = append_message(
            dialog,
            speaker=speaker,
            text=text,
            reply_to=reply_to,
            attachment_name=attachment_name,
            response_origin=response_origin,
            sufler_suggestion_text=suggestion_text,
        )
        return JsonResponse(
            {"ok": True, "message": serialize_message(message)},
            status=201,
        )
    except OnlineChatApiError as exc:
        return _error(exc)


@csrf_exempt
@require_http_methods(["POST"])
def dialog_attachment_upload(request: HttpRequest, dialog_id: str) -> HttpResponse:
    dialog = get_object_or_404(Dialog, pk=dialog_id)
    if dialog.status in {Dialog.Status.CLOSED, Dialog.Status.BLOCKED}:
        return _error(OnlineChatApiError("dialog is closed"))
    uploaded = request.FILES.get("file")
    if uploaded is None:
        return _error(OnlineChatApiError("file is required"))
    if uploaded.size > settings.ONLINE_CHAT_MAX_UPLOAD_BYTES:
        return _error(OnlineChatApiError("file is too large"), status=413)
    content_type = uploaded.content_type or "application/octet-stream"
    if content_type not in settings.ONLINE_CHAT_ALLOWED_UPLOAD_TYPES:
        return _error(OnlineChatApiError("file type is not allowed"), status=415)
    speaker = (request.POST.get("speaker") or DialogMessage.Speaker.CLIENT).strip()
    if speaker not in {
        DialogMessage.Speaker.CLIENT,
        DialogMessage.Speaker.OPERATOR,
    }:
        return _error(OnlineChatApiError("speaker must be client or operator"))
    if speaker == DialogMessage.Speaker.OPERATOR:
        denied = _operator_write_denied(
            request,
            dialog,
            claimed_name=(request.POST.get("operator_name") or ""),
        )
        if denied:
            return denied
    safe_name = re.sub(r"[^A-Za-zА-Яа-я0-9._-]+", "_", uploaded.name)[:180]
    key = f"dialogs/{dialog.id}/{uuid.uuid4().hex}/{safe_name}"
    get_chat_object_store().put_bytes(
        key,
        uploaded.read(),
        content_type=content_type,
    )
    message = append_message(
        dialog,
        speaker=speaker,
        text=(request.POST.get("text") or "").strip(),
        attachment_name=uploaded.name,
        attachment_key=key,
        attachment_content_type=content_type,
        attachment_size=uploaded.size,
        # The hook is ready for an external antivirus scanner. Local files are
        # marked clean after strict type/size validation.
        attachment_scan_status="clean" if settings.DEBUG else "pending",
    )
    return JsonResponse(
        {"ok": True, "message": serialize_message(message)},
        status=201,
    )


@require_http_methods(["GET"])
def dialog_attachment_download(
    request: HttpRequest,
    dialog_id: str,
    message_id: str,
) -> HttpResponse:
    message = get_object_or_404(
        DialogMessage,
        pk=message_id,
        dialog_id=dialog_id,
    )
    if not message.attachment_key:
        return JsonResponse({"detail": "Not found"}, status=404)
    if message.attachment_scan_status not in {"clean", "not_required"}:
        return JsonResponse(
            {"detail": "Attachment is not cleared by security scan"},
            status=423,
        )
    payload = get_chat_object_store().get_bytes(message.attachment_key)
    response = HttpResponse(
        payload,
        content_type=message.attachment_content_type or "application/octet-stream",
    )
    response["Content-Disposition"] = (
        f"attachment; filename*=UTF-8''{quote(message.attachment_name)}"
    )
    response["X-Content-Type-Options"] = "nosniff"
    return response


@csrf_exempt
@require_http_methods(["PATCH", "DELETE"])
def dialog_message_detail(
    request: HttpRequest,
    dialog_id: str,
    message_id: str,
) -> HttpResponse:
    dialog = get_object_or_404(Dialog, pk=dialog_id)
    message = get_object_or_404(DialogMessage, pk=message_id, dialog=dialog)
    try:
        if request.method == "DELETE":
            delete_message(message)
            return JsonResponse({"ok": True, "message": serialize_message(message)})
        payload = _json_body(request)
        text = _str_field(payload, "text")
        if not text:
            raise OnlineChatApiError("text is required")
        edit_message(message, text=text)
        return JsonResponse({"ok": True, "message": serialize_message(message)})
    except (OnlineChatApiError, ValueError) as exc:
        return _error(OnlineChatApiError(str(exc)))


@csrf_exempt
@require_http_methods(["POST"])
def dialog_accept(request: HttpRequest, dialog_id: str) -> HttpResponse:
    dialog = get_object_or_404(Dialog, pk=dialog_id)
    try:
        payload = _json_body(request)
        operator_name = _str_field(payload, "operator_name", "Иванов И.И.") or "Иванов И.И."
        if dialog.status == Dialog.Status.CLOSED:
            raise OnlineChatApiError("dialog is closed")
        operator_id = _str_field(payload, "operator_id")
        if operator_id:
            operator = get_object_or_404(OperatorProfile, pk=operator_id)
            dialog = accept_waiting_dialog(dialog.pk, operator=operator)
        else:
            dialog = accept_dialog(dialog, operator_name)
        return JsonResponse(
            {"ok": True, "dialog": serialize_dialog(dialog, include_messages=True)},
        )
    except (OnlineChatApiError, ValueError) as exc:
        return _error(OnlineChatApiError(str(exc)), status=409 if isinstance(exc, ValueError) else 400)


@csrf_exempt
@require_http_methods(["POST"])
def dialog_transfer(request: HttpRequest, dialog_id: str) -> HttpResponse:
    dialog = get_object_or_404(Dialog, pk=dialog_id)
    try:
        payload = _json_body(request)
        to_operator = _str_field(payload, "to_operator_name") or _str_field(
            payload,
            "operator_name",
        )
        operator_id = _str_field(payload, "operator_id")
        if not to_operator and not operator_id:
            raise OnlineChatApiError("to_operator_name or operator_id is required")
        if dialog.status in {Dialog.Status.CLOSED, Dialog.Status.BLOCKED}:
            raise OnlineChatApiError("dialog is closed")
        if operator_id:
            dialog = transfer_to_operator(dialog, operator_id=operator_id)
        else:
            dialog = transfer_dialog(
                dialog,
                to_operator_name=to_operator,
                from_operator_name=_str_field(payload, "from_operator_name"),
            )
        return JsonResponse({"ok": True, "dialog": serialize_dialog(dialog)})
    except (OnlineChatApiError, ValueError) as exc:
        return _error(OnlineChatApiError(str(exc)))


@csrf_exempt
@require_http_methods(["POST"])
def dialog_close(request: HttpRequest, dialog_id: str) -> HttpResponse:
    dialog = get_object_or_404(Dialog, pk=dialog_id)
    try:
        payload = _json_body(request)
        topic = _str_field(payload, "topic") or _str_field(payload, "close_topic")
        if not topic:
            raise OnlineChatApiError("topic is required")
        if dialog.status == Dialog.Status.CLOSED:
            if topic != dialog.close_topic:
                dialog.close_topic = topic
                dialog.save(update_fields=["close_topic", "updated_at"])
            return JsonResponse({"ok": True, "dialog": serialize_dialog(dialog)})
        close_dialog(dialog, topic=topic)
        return JsonResponse({"ok": True, "dialog": serialize_dialog(dialog)})
    except OnlineChatApiError as exc:
        return _error(exc)


@csrf_exempt
@require_http_methods(["POST"])
def dialog_mark_read(request: HttpRequest, dialog_id: str) -> HttpResponse:
    dialog = get_object_or_404(Dialog, pk=dialog_id)
    try:
        payload = _json_body(request)
        reader = _str_field(payload, "reader")
        if reader not in {
            DialogMessage.Speaker.CLIENT,
            DialogMessage.Speaker.OPERATOR,
        }:
            raise OnlineChatApiError("reader must be client or operator")
        updated = mark_dialog_messages_read(dialog, reader=reader)
        return JsonResponse(
            {
                "ok": True,
                "dialog_id": str(dialog.id),
                "reader": reader,
                "message_ids": [str(item.id) for item in updated],
                "messages": [serialize_message(item) for item in updated],
            },
        )
    except OnlineChatApiError as exc:
        return _error(exc)


@csrf_exempt
@require_http_methods(["POST"])
def dialog_presence(request: HttpRequest, dialog_id: str) -> HttpResponse:
    dialog = get_object_or_404(Dialog, pk=dialog_id)
    try:
        payload = _json_body(request)
        online_raw = payload.get("online", True)
        online = bool(online_raw) if not isinstance(online_raw, str) else online_raw.lower() in {
            "1",
            "true",
            "yes",
        }
        set_client_presence(dialog, online=online)
        return JsonResponse({"ok": True, "dialog": serialize_dialog(dialog)})
    except OnlineChatApiError as exc:
        return _error(exc)


@csrf_exempt
@require_http_methods(["POST"])
def dialog_block(request: HttpRequest, dialog_id: str) -> HttpResponse:
    dialog = get_object_or_404(Dialog, pk=dialog_id)
    try:
        payload = _json_body(request)
        dialog, block = block_dialog(
            dialog,
            blocked_by=_str_field(payload, "blocked_by"),
            reason=_str_field(payload, "reason"),
        )
        body: dict[str, Any] = {"ok": True, "dialog": serialize_dialog(dialog)}
        if block is not None:
            body["block"] = serialize_client_block(block)
        return JsonResponse(body)
    except OnlineChatApiError as exc:
        return _error(exc)


@csrf_exempt
@require_http_methods(["GET", "POST"])
def client_blocks_collection(request: HttpRequest) -> HttpResponse:
    if request.method == "GET":
        active_only = (request.GET.get("active") or "1").strip().lower() not in {
            "0",
            "false",
            "no",
        }
        qs = ClientBlock.objects.all()
        if active_only:
            qs = qs.filter(is_active=True)
        items = [serialize_client_block(item) for item in qs[:200]]
        return JsonResponse({"ok": True, "items": items, "count": len(items)})
    return JsonResponse(
        {"ok": False, "error": "method_not_allowed", "detail": "POST via dialog block"},
        status=405,
    )


@csrf_exempt
@require_http_methods(["POST"])
def client_block_lift(request: HttpRequest, block_id: str) -> HttpResponse:
    block = get_object_or_404(ClientBlock, pk=block_id)
    try:
        payload = _json_body(request)
        unblock_client(block, lifted_by=_str_field(payload, "lifted_by", "admin"))
        return JsonResponse({"ok": True, "block": serialize_client_block(block)})
    except OnlineChatApiError as exc:
        return _error(exc)


@csrf_exempt
@require_http_methods(["POST"])
def dialog_feedback(request: HttpRequest, dialog_id: str) -> HttpResponse:
    dialog = get_object_or_404(Dialog, pk=dialog_id)
    try:
        if dialog.status != Dialog.Status.CLOSED:
            raise OnlineChatApiError("dialog must be closed before feedback")
        payload = _json_body(request)
        rating = _int_field(payload, "rating")
        if rating < 1 or rating > 5:
            raise OnlineChatApiError("rating must be between 1 and 5")
        comment = _str_field(payload, "comment")
        feedback = save_feedback(dialog, rating=rating, comment=comment)
        return JsonResponse(
            {"ok": True, "feedback": serialize_feedback(feedback)},
            status=201,
        )
    except OnlineChatApiError as exc:
        return _error(exc)


@csrf_exempt
@require_http_methods(["POST"])
def dialog_send_transcript(request: HttpRequest, dialog_id: str) -> HttpResponse:
    dialog = get_object_or_404(Dialog, pk=dialog_id)
    try:
        if dialog.status != Dialog.Status.CLOSED:
            raise OnlineChatApiError("dialog must be closed before sending transcript")
        payload = _json_body(request)
        email = _str_field(payload, "email")
        if not email:
            raise OnlineChatApiError("email is required")
        try:
            validate_email(email)
        except DjangoValidationError as exc:
            raise OnlineChatApiError("email is invalid") from exc
        if not EMAIL_RE.match(email):
            raise OnlineChatApiError("email is invalid")
        record = request_transcript_email(dialog, email=email)
        return JsonResponse(
            {
                "ok": record.status == "sent",
                "transcript_email": serialize_transcript_email(record),
            },
            status=201 if record.status == "sent" else 502,
        )
    except OnlineChatApiError as exc:
        return _error(exc)


def _bool_field(payload: Mapping[str, Any], key: str, default: bool = False) -> bool:
    value = payload.get(key, default)
    if isinstance(value, bool):
        return value
    if isinstance(value, str) and value.lower() in {"true", "false", "1", "0"}:
        return value.lower() in {"true", "1"}
    raise OnlineChatApiError(f"{key} must be a boolean")


def _json_field(
    payload: Mapping[str, Any], key: str, expected: type, default: Any
) -> Any:
    value = payload.get(key, default)
    if not isinstance(value, expected):
        raise OnlineChatApiError(f"{key} must be a JSON {expected.__name__}")
    return value


def _department_dict(item: Department) -> dict[str, Any]:
    return {
        "id": str(item.id), "code": item.code, "name": item.name,
        "description": item.description, "is_active": item.is_active,
        "priority": item.priority, "max_queue_size": item.max_queue_size,
        "created_at": item.created_at.isoformat(), "updated_at": item.updated_at.isoformat(),
    }


def _operator_dict(item: OperatorProfile) -> dict[str, Any]:
    department_ids = [
        str(value) for value in item.departments.values_list("id", flat=True)
    ]
    first_department = item.departments.order_by("priority", "name").first()
    return {
        "id": str(item.id), "external_id": item.external_id,
        "display_name": item.display_name, "email": item.email, "role": item.role,
        "presence": item.presence,
        "department_ids": department_ids,
        "max_active_dialogs": item.max_active_dialogs, "auto_assign": item.auto_assign,
        "last_seen_at": item.last_seen_at.isoformat() if item.last_seen_at else None,
        "is_active": item.is_active,
        # Stable aliases consumed by the management SPA.
        "name": item.display_name,
        "username": item.external_id,
        "capacity": item.max_active_dialogs,
        "department_id": str(first_department.id) if first_department else None,
        "department_name": first_department.name if first_department else "",
        "created_at": item.created_at.isoformat(), "updated_at": item.updated_at.isoformat(),
    }


def _placement_dict(item: WidgetPlacement, *, public: bool = False) -> dict[str, Any]:
    data = {
        "widget_id": item.widget_id, "name": item.name, "site_url": item.site_url,
        "code": item.widget_id,
        "allowed_domains": item.allowed_domains,
        "department_id": str(item.department_id) if item.department_id else None,
        "is_active": item.is_active, "theme": item.theme, "config": item.config,
        "welcome_message": item.welcome_message, "queue_message": item.queue_message,
        "offline_message": item.offline_message, "require_phone": item.require_phone,
        "form_fields": item.form_fields,
        "theme_accent": item.theme.get("accent", "#007A43"),
    }
    if not public:
        data.update({
            "id": str(item.id), "created_at": item.created_at.isoformat(),
            "updated_at": item.updated_at.isoformat(),
        })
    return data


SECRET_MARKERS = ("token", "secret", "password", "api_key", "private_key", "credential")


def _safe_config(value: object) -> object:
    if isinstance(value, dict):
        return {
            key: (
                "***"
                if any(marker in key.lower() for marker in SECRET_MARKERS)
                else _safe_config(item)
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_safe_config(item) for item in value]
    return value


def _channel_counters(channel: str) -> dict[str, int]:
    from django.utils import timezone

    today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    qs = Dialog.objects.filter(channel=channel)
    return {
        "waiting": qs.filter(status=Dialog.Status.WAITING).count(),
        "active": qs.filter(status=Dialog.Status.ACTIVE).count(),
        "today": qs.filter(created_at__gte=today_start).count(),
        "closed_today": qs.filter(
            status=Dialog.Status.CLOSED, closed_at__gte=today_start
        ).count(),
    }


def _channel_dict(item: ChannelConnection) -> dict[str, Any]:
    safe_config = _safe_config(item.config)
    return {
        "id": str(item.id), "channel": item.channel, "name": item.name,
        "kind": item.channel,
        "external_id": item.external_id,
        "account": item.external_id,
        "department_id": str(item.department_id) if item.department_id else None,
        "is_active": item.is_active, "config": safe_config,
        "endpoint": safe_config.get("endpoint", "") if isinstance(safe_config, dict) else "",
        "configured": bool(item.external_id or item.config),
        "health_status": item.health_status,
        "last_health_check_at": (
            item.last_health_check_at.isoformat() if item.last_health_check_at else None
        ),
        "counters": _channel_counters(item.channel),
        "created_at": item.created_at.isoformat(), "updated_at": item.updated_at.isoformat(),
    }


def _rule_dict(item: RoutingRule) -> dict[str, Any]:
    connection = ChannelConnection.objects.filter(channel=item.channel).first()
    return {
        "id": str(item.id), "name": item.name, "priority": item.priority,
        "channel": item.channel,
        "channel_id": str(connection.id) if connection else None,
        "placement_id": str(item.placement_id) if item.placement_id else None,
        "department_id": str(item.department_id), "conditions": item.conditions,
        "max_load": item.conditions.get("max_load") if isinstance(item.conditions, dict) else None,
        "is_active": item.is_active, "created_at": item.created_at.isoformat(),
        "updated_at": item.updated_at.isoformat(),
    }


def _bot_dict(item: BotConfiguration) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "name": item.name,
        "department_id": str(item.department_id),
        "is_active": item.is_active,
        "welcome_message": item.welcome_message,
        "fallback_message": item.fallback_message,
        "trigger_responses": item.trigger_responses,
        "max_bot_turns": item.max_bot_turns,
        "handoff_message": item.handoff_message,
        "created_at": item.created_at.isoformat(),
        "updated_at": item.updated_at.isoformat(),
    }


def _bot_values(
    data: Mapping[str, Any],
    item: BotConfiguration | None = None,
) -> BotConfiguration:
    item = item or BotConfiguration()
    for field in (
        "name",
        "welcome_message",
        "fallback_message",
        "handoff_message",
    ):
        if field in data:
            setattr(item, field, _str_field(data, field))
    if "department_id" in data:
        item.department = get_object_or_404(
            Department,
            pk=data["department_id"],
        )
    if "trigger_responses" in data:
        item.trigger_responses = _json_field(
            data,
            "trigger_responses",
            dict,
            {},
        )
    if "max_bot_turns" in data:
        item.max_bot_turns = _int_field(data, "max_bot_turns")
    if "is_active" in data:
        item.is_active = _bool_field(data, "is_active")
    if not item.name or not item.department_id:
        raise OnlineChatApiError("name and department_id are required")
    item.save()
    return item


@csrf_exempt
@require_http_methods(["GET", "POST"])
@_chat_permissions(PERM_CC_ADMIN)
def bots_collection(request: HttpRequest) -> HttpResponse:
    if request.method == "GET":
        items = [_bot_dict(item) for item in BotConfiguration.objects.all()]
        return JsonResponse({"ok": True, "items": items, "count": len(items)})
    try:
        item = _bot_values(_json_body(request))
        return JsonResponse(
            {"ok": True, "bot": _bot_dict(item)},
            status=201,
        )
    except OnlineChatApiError as exc:
        return _error(exc)


@csrf_exempt
@require_http_methods(["PATCH", "DELETE"])
@_chat_permissions(PERM_CC_ADMIN)
def bot_detail(request: HttpRequest, item_id: str) -> HttpResponse:
    item = get_object_or_404(BotConfiguration, pk=item_id)
    if request.method == "DELETE":
        item.delete()
        return JsonResponse({"ok": True})
    try:
        item = _bot_values(_json_body(request), item)
        return JsonResponse({"ok": True, "bot": _bot_dict(item)})
    except OnlineChatApiError as exc:
        return _error(exc)


def _set_departments(operator: OperatorProfile, payload: Mapping[str, Any]) -> None:
    if "department_ids" not in payload:
        return
    ids = _json_field(payload, "department_ids", list, [])
    departments = list(Department.objects.filter(id__in=ids))
    if len(departments) != len(set(ids)):
        raise OnlineChatApiError("one or more department_ids are invalid")
    operator.departments.set(departments)


@csrf_exempt
@require_http_methods(["GET", "POST"])
@_chat_permissions(PERM_CC_ADMIN)
def departments_collection(request: HttpRequest) -> HttpResponse:
    if request.method == "GET":
        items = [_department_dict(item) for item in Department.objects.all()]
        return JsonResponse({"ok": True, "items": items, "count": len(items)})
    try:
        data = _json_body(request)
        code = _str_field(data, "code")
        name = _str_field(data, "name")
        if not name:
            raise OnlineChatApiError("name is required")
        if not code:
            code = f"dept-{uuid.uuid4().hex[:8]}"
        item = Department.objects.create(
            code=code, name=name,
            description=_str_field(data, "description"),
            is_active=_bool_field(data, "is_active", True),
            priority=data.get("priority", 100), max_queue_size=data.get("max_queue_size", 100),
        )
        return JsonResponse({"ok": True, "department": _department_dict(item)}, status=201)
    except (OnlineChatApiError, ValueError) as exc:
        return _error(OnlineChatApiError(str(exc)))


@csrf_exempt
@require_http_methods(["PATCH", "DELETE"])
@_chat_permissions(PERM_CC_ADMIN)
def department_detail(request: HttpRequest, item_id: str) -> HttpResponse:
    item = get_object_or_404(Department, pk=item_id)
    if request.method == "DELETE":
        item.delete()
        return JsonResponse({"ok": True})
    try:
        data = _json_body(request)
        for field in ("code", "name", "description"):
            if field in data:
                setattr(item, field, _str_field(data, field))
        for field in ("priority", "max_queue_size"):
            if field in data:
                setattr(item, field, _int_field(data, field))
        if "is_active" in data:
            item.is_active = _bool_field(data, "is_active")
        item.save()
        return JsonResponse({"ok": True, "department": _department_dict(item)})
    except OnlineChatApiError as exc:
        return _error(exc)


@csrf_exempt
@require_http_methods(["GET", "POST"])
@_chat_permissions(PERM_CC_ADMIN, PERM_CC_REPORTS)
def operators_collection(request: HttpRequest) -> HttpResponse:
    if request.method == "GET":
        items = [_operator_dict(item) for item in OperatorProfile.objects.prefetch_related("departments")]
        return JsonResponse({"ok": True, "items": items, "count": len(items)})
    try:
        data = _json_body(request)
        role = _str_field(data, "role", OperatorProfile.Role.OPERATOR)
        presence = _str_field(data, "presence", OperatorProfile.Presence.OFFLINE)
        external_id = _str_field(data, "external_id") or _str_field(data, "username")
        display_name = _str_field(data, "display_name") or _str_field(data, "name")
        if not external_id or not display_name:
            raise OnlineChatApiError("external_id and display_name are required")
        if role not in OperatorProfile.Role.values or presence not in OperatorProfile.Presence.values:
            raise OnlineChatApiError("invalid role or presence")
        item = OperatorProfile.objects.create(
            external_id=external_id,
            display_name=display_name, email=_str_field(data, "email"),
            role=role, presence=presence,
            max_active_dialogs=data.get("max_active_dialogs", data.get("capacity", 3)),
            auto_assign=_bool_field(data, "auto_assign", True),
            is_active=_bool_field(data, "is_active", True),
        )
        if "department_id" in data and "department_ids" not in data:
            data = {**data, "department_ids": [data["department_id"]] if data["department_id"] else []}
        _set_departments(item, data)
        return JsonResponse({"ok": True, "operator": _operator_dict(item)}, status=201)
    except (OnlineChatApiError, ValueError) as exc:
        return _error(OnlineChatApiError(str(exc)))


@csrf_exempt
@require_http_methods(["PATCH"])
@_chat_permissions(PERM_CC_ADMIN)
def operator_detail(request: HttpRequest, item_id: str) -> HttpResponse:
    item = get_object_or_404(OperatorProfile, pk=item_id)
    try:
        data = _json_body(request)
        if "name" in data and "display_name" not in data:
            data = {**data, "display_name": data["name"]}
        if "username" in data and "external_id" not in data:
            data = {**data, "external_id": data["username"]}
        for field in ("external_id", "display_name", "email", "role", "presence"):
            if field in data:
                setattr(item, field, _str_field(data, field))
        if item.role not in OperatorProfile.Role.values or item.presence not in OperatorProfile.Presence.values:
            raise OnlineChatApiError("invalid role or presence")
        if "max_active_dialogs" in data:
            item.max_active_dialogs = _int_field(data, "max_active_dialogs")
        elif "capacity" in data:
            item.max_active_dialogs = _int_field(data, "capacity")
        for field in ("auto_assign", "is_active"):
            if field in data:
                setattr(item, field, _bool_field(data, field))
        item.save()
        if "department_id" in data and "department_ids" not in data:
            data = {**data, "department_ids": [data["department_id"]] if data["department_id"] else []}
        _set_departments(item, data)
        return JsonResponse({"ok": True, "operator": _operator_dict(item)})
    except OnlineChatApiError as exc:
        return _error(exc)


@csrf_exempt
@require_http_methods(["POST"])
@_chat_permissions(PERM_SUFLER_CHAT, PERM_CC_ADMIN)
def operator_presence(request: HttpRequest, item_id: str) -> HttpResponse:
    item = get_object_or_404(OperatorProfile, pk=item_id)
    try:
        item = update_operator_presence(item, _str_field(_json_body(request), "presence"))
        return JsonResponse({"ok": True, "operator": _operator_dict(item)})
    except (OnlineChatApiError, ValueError) as exc:
        return _error(OnlineChatApiError(str(exc)))


def _placement_values(data: Mapping[str, Any], item: WidgetPlacement | None = None) -> WidgetPlacement:
    item = item or WidgetPlacement()
    if "code" in data and "widget_id" not in data:
        data = {**data, "widget_id": data["code"]}
    for field in (
        "widget_id", "name", "site_url", "welcome_message", "queue_message", "offline_message"
    ):
        if field in data:
            setattr(item, field, _str_field(data, field))
    for field, expected, default in (
        ("allowed_domains", list, []), ("theme", dict, {}),
        ("config", dict, {}), ("form_fields", list, []),
    ):
        if field in data:
            setattr(item, field, _json_field(data, field, expected, default))
    if "theme_accent" in data:
        theme = dict(item.theme or {})
        theme["accent"] = _str_field(data, "theme_accent")
        item.theme = theme
    for field in ("is_active", "require_phone"):
        if field in data:
            setattr(item, field, _bool_field(data, field))
    if "department_id" in data:
        item.department = (
            get_object_or_404(Department, pk=data["department_id"])
            if data["department_id"] else None
        )
    if not item.name:
        raise OnlineChatApiError("name is required")
    if not item.widget_id:
        item.widget_id = f"widget-{uuid.uuid4().hex[:8]}"
    item.save()
    return item


@csrf_exempt
@require_http_methods(["GET", "POST"])
@_chat_permissions(PERM_CC_ADMIN)
def placements_collection(request: HttpRequest) -> HttpResponse:
    if request.method == "GET":
        items = [_placement_dict(item) for item in WidgetPlacement.objects.all()]
        return JsonResponse({"ok": True, "items": items, "count": len(items)})
    try:
        item = _placement_values(_json_body(request))
        return JsonResponse({"ok": True, "placement": _placement_dict(item)}, status=201)
    except OnlineChatApiError as exc:
        return _error(exc)


@csrf_exempt
@require_http_methods(["PATCH", "DELETE"])
@_chat_permissions(PERM_CC_ADMIN)
def placement_detail(request: HttpRequest, item_id: str) -> HttpResponse:
    item = get_object_or_404(WidgetPlacement, pk=item_id)
    if request.method == "DELETE":
        item.delete()
        return JsonResponse({"ok": True})
    try:
        item = _placement_values(_json_body(request), item)
        return JsonResponse({"ok": True, "placement": _placement_dict(item)})
    except OnlineChatApiError as exc:
        return _error(exc)


def _channel_values(data: Mapping[str, Any], item: ChannelConnection | None = None) -> ChannelConnection:
    item = item or ChannelConnection()
    if "kind" in data and "channel" not in data:
        channel = "api" if data["kind"] == "external" else data["kind"]
        data = {**data, "channel": channel}
    if "account" in data and "external_id" not in data:
        data = {**data, "external_id": data["account"]}
    for field in ("channel", "name", "external_id", "health_status"):
        if field in data:
            setattr(item, field, _str_field(data, field))
    if item.channel not in ChannelConnection.Channel.values:
        raise OnlineChatApiError("invalid channel")
    if "config" in data:
        item.config = _json_field(data, "config", dict, {})
    if "endpoint" in data:
        config = dict(item.config or {})
        config["endpoint"] = _str_field(data, "endpoint")
        item.config = config
    if "is_active" in data:
        item.is_active = _bool_field(data, "is_active")
    if "department_id" in data:
        item.department = (
            get_object_or_404(Department, pk=data["department_id"])
            if data["department_id"] else None
        )
    if not item.name:
        raise OnlineChatApiError("name is required")
    item.save()
    return item


@csrf_exempt
@require_http_methods(["GET", "POST"])
@_chat_permissions(PERM_CC_ADMIN)
def channels_collection(request: HttpRequest) -> HttpResponse:
    if request.method == "GET":
        items = [_channel_dict(item) for item in ChannelConnection.objects.all()]
        return JsonResponse({"ok": True, "items": items, "count": len(items)})
    try:
        item = _channel_values(_json_body(request))
        return JsonResponse({"ok": True, "channel": _channel_dict(item)}, status=201)
    except OnlineChatApiError as exc:
        return _error(exc)


@csrf_exempt
@require_http_methods(["PATCH"])
@_chat_permissions(PERM_CC_ADMIN)
def channel_detail(request: HttpRequest, item_id: str) -> HttpResponse:
    try:
        item = _channel_values(_json_body(request), get_object_or_404(ChannelConnection, pk=item_id))
        return JsonResponse({"ok": True, "channel": _channel_dict(item)})
    except OnlineChatApiError as exc:
        return _error(exc)


@csrf_exempt
@require_http_methods(["POST"])
@_chat_permissions(PERM_CC_ADMIN)
def channel_health_check(request: HttpRequest, item_id: str) -> HttpResponse:
    from django.utils import timezone

    from online_chat.channel_delivery import probe_channel

    item = get_object_or_404(ChannelConnection, pk=item_id)
    status, detail = probe_channel(item)
    item.health_status = status
    item.last_health_check_at = timezone.now()
    item.save(update_fields=["health_status", "last_health_check_at", "updated_at"])
    return JsonResponse(
        {
            "ok": True,
            "channel": _channel_dict(item),
            "health_status": status,
            "detail": detail,
        }
    )


def _rule_values(data: Mapping[str, Any], item: RoutingRule | None = None) -> RoutingRule:
    item = item or RoutingRule()
    if "channel_id" in data and "channel" not in data:
        channel_id = data.get("channel_id")
        connection = (
            get_object_or_404(ChannelConnection, pk=channel_id) if channel_id else None
        )
        data = {**data, "channel": connection.channel if connection else ""}
    for field in ("name", "channel"):
        if field in data:
            setattr(item, field, _str_field(data, field))
    if "priority" in data:
        item.priority = _int_field(data, "priority")
    if "conditions" in data:
        item.conditions = _json_field(data, "conditions", dict, {})
    if "max_load" in data:
        conditions = dict(item.conditions or {})
        conditions["max_load"] = _int_field(data, "max_load")
        item.conditions = conditions
    if "is_active" in data:
        item.is_active = _bool_field(data, "is_active")
    if "department_id" in data:
        item.department = get_object_or_404(Department, pk=data["department_id"])
    if "placement_id" in data:
        item.placement = (
            get_object_or_404(WidgetPlacement, pk=data["placement_id"])
            if data["placement_id"] else None
        )
    if not item.name or not item.department_id:
        raise OnlineChatApiError("name and department_id are required")
    item.save()
    return item


@csrf_exempt
@require_http_methods(["GET", "POST"])
@_chat_permissions(PERM_CC_ADMIN)
def routing_rules_collection(request: HttpRequest) -> HttpResponse:
    if request.method == "GET":
        items = [_rule_dict(item) for item in RoutingRule.objects.all()]
        return JsonResponse({"ok": True, "items": items, "count": len(items)})
    try:
        item = _rule_values(_json_body(request))
        return JsonResponse({"ok": True, "routing_rule": _rule_dict(item)}, status=201)
    except OnlineChatApiError as exc:
        return _error(exc)


@csrf_exempt
@require_http_methods(["PATCH", "DELETE"])
@_chat_permissions(PERM_CC_ADMIN)
def routing_rule_detail(request: HttpRequest, item_id: str) -> HttpResponse:
    item = get_object_or_404(RoutingRule, pk=item_id)
    if request.method == "DELETE":
        item.delete()
        return JsonResponse({"ok": True})
    try:
        item = _rule_values(_json_body(request), item)
        return JsonResponse({"ok": True, "routing_rule": _rule_dict(item)})
    except OnlineChatApiError as exc:
        return _error(exc)


@require_http_methods(["GET"])
@_chat_permissions(PERM_CC_REPORTS, PERM_CC_ADMIN)
def supervisor_overview(request: HttpRequest) -> HttpResponse:
    from datetime import timedelta

    from django.utils import timezone

    statuses = dict(Dialog.objects.values_list("status").annotate(count=Count("id")))
    now = timezone.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    waiting_dialogs = list(
        Dialog.objects.filter(status=Dialog.Status.WAITING).only(
            "id", "created_at", "accepted_at", "status"
        )
    )
    wait_seconds = [
        max(0, int((now - item.created_at).total_seconds())) for item in waiting_dialogs
    ]
    average_wait = round(sum(wait_seconds) / len(wait_seconds)) if wait_seconds else 0
    sla_window = timedelta(seconds=120)
    answered = list(
        Dialog.objects.filter(
            first_response_at__isnull=False,
            created_at__gte=today_start - timedelta(days=1),
        ).only("created_at", "first_response_at")[:2000]
    )
    answered_count = len(answered)
    within_sla = sum(
        1
        for item in answered
        if item.first_response_at and item.first_response_at - item.created_at <= sla_window
    )
    sla_percent = round(within_sla / answered_count * 100, 1) if answered_count else None

    operators = []
    for item in OperatorProfile.objects.prefetch_related("departments"):
        data = _operator_dict(item)
        data["active_dialogs"] = Dialog.objects.filter(
            operator=item, status=Dialog.Status.ACTIVE
        ).count()
        data["load"] = data["active_dialogs"]
        operators.append(data)

    queues = []
    for item in Department.objects.filter(is_active=True):
        dept_waiting = list(
            item.dialogs.filter(status=Dialog.Status.WAITING).only("created_at")
        )
        longest = (
            max(int((now - d.created_at).total_seconds()) for d in dept_waiting)
            if dept_waiting
            else 0
        )
        queues.append(
            {
                "id": str(item.id),
                "department_id": str(item.id),
                "department_name": item.name,
                "name": item.name,
                "department": item.name,
                "waiting": len(dept_waiting),
                "active": item.dialogs.filter(status=Dialog.Status.ACTIVE).count(),
                "longest_wait_seconds": longest,
            }
        )

    return JsonResponse(
        {
            "ok": True,
            "kpis": {
                "waiting": statuses.get(Dialog.Status.WAITING, 0),
                "active": statuses.get(Dialog.Status.ACTIVE, 0),
                "closed": statuses.get(Dialog.Status.CLOSED, 0),
                "closed_today": Dialog.objects.filter(
                    status=Dialog.Status.CLOSED, closed_at__gte=today_start
                ).count(),
                "online_operators": OperatorProfile.objects.filter(
                    is_active=True, presence=OperatorProfile.Presence.ONLINE
                ).count(),
                "average_wait_seconds": average_wait,
                "sla_percent": sla_percent,
            },
            "operators": operators,
            "queues": queues,
        }
    )


@require_http_methods(["GET"])
@_chat_permissions(PERM_CC_REPORTS, PERM_CC_ADMIN)
def analytics(request: HttpRequest) -> HttpResponse:
    from datetime import timedelta
    from django.utils import timezone

    period = (request.GET.get("period") or "7d").lower()
    days = {
        "today": 1, "day": 1, "7d": 7, "week": 7,
        "30d": 30, "month": 30, "90d": 90,
    }.get(period, 7)
    start = timezone.now() - timedelta(days=days)
    dialogs = Dialog.objects.filter(created_at__gte=start)
    closed = dialogs.filter(status=Dialog.Status.CLOSED)
    feedback = DialogFeedback.objects.filter(dialog__in=dialogs).aggregate(avg=Avg("rating"))
    response_seconds = [
        (item.first_response_at - item.created_at).total_seconds()
        for item in dialogs.exclude(first_response_at=None)
    ]
    return JsonResponse({
        "ok": True, "period": period, "from": start.isoformat(),
        "kpis": {
            "dialogs": dialogs.count(), "closed": closed.count(),
            "waiting": dialogs.filter(status=Dialog.Status.WAITING).count(),
            "resolution_rate": round(closed.count() / dialogs.count() * 100, 2) if dialogs.count() else 0,
            "average_first_response_seconds": (
                round(sum(response_seconds) / len(response_seconds), 2) if response_seconds else None
            ),
            "average_rating": feedback["avg"],
        },
    })


@require_http_methods(["GET"])
def client_history(request: HttpRequest) -> HttpResponse:
    dialog_id = (request.GET.get("dialog_id") or "").strip()
    phone = (request.GET.get("phone") or "").strip()
    external_id = (request.GET.get("external_id") or "").strip()
    if dialog_id:
        current = get_object_or_404(Dialog, pk=dialog_id)
        phone = phone or current.client_phone
        external_id = external_id or current.client_external_id
    query = Q()
    normalized = normalize_phone(phone)
    if normalized:
        candidate_ids = [
            item.id
            for item in Dialog.objects.only("id", "client_phone")
            if normalize_phone(item.client_phone) == normalized
        ]
        query |= Q(id__in=candidate_ids)
    if external_id:
        query |= Q(client_external_id=external_id)
    if not query:
        return JsonResponse({"ok": True, "items": [], "count": 0, "summary": ""})
    dialogs = (
        Dialog.objects.filter(query)
        .prefetch_related("messages")
        .order_by("-created_at")[:100]
    )
    items = [
        {
            "id": str(item.id),
            "channel": item.channel,
            "status": item.status,
            "outcome": item.outcome,
            "topic": item.close_topic,
            "operator_name": item.operator_name,
            "preview": item.preview,
            "created_at": item.created_at.isoformat(),
            "closed_at": item.closed_at.isoformat() if item.closed_at else None,
            "message_count": len(item.messages.all()),
        }
        for item in dialogs
    ]
    topics = [item["topic"] for item in items if item["topic"]]
    channels = sorted({item["channel"] for item in items})
    summary = (
        f"Обращений: {len(items)}. Каналы: {', '.join(channels) or '—'}. "
        f"Последние темы: {', '.join(topics[:3]) or 'не определены'}."
    )
    return JsonResponse(
        {"ok": True, "items": items, "count": len(items), "summary": summary}
    )


@csrf_exempt
@require_http_methods(["GET", "POST"])
@_chat_permissions(PERM_SUFLER_CHAT, PERM_CC_ADMIN)
def internal_messages_collection(request: HttpRequest) -> HttpResponse:
    if request.method == "GET":
        qs = InternalMessage.objects.select_related("sender", "recipient")
        if request.GET.get("operator_id"):
            operator_id = request.GET["operator_id"]
            qs = qs.filter(Q(sender_id=operator_id) | Q(recipient_id=operator_id))
        items = [{
            "id": str(item.id), "sender_id": str(item.sender_id),
            "sender_name": item.sender.display_name, "recipient_id": str(item.recipient_id),
            "recipient_name": item.recipient.display_name,
            "dialog_id": str(item.dialog_id) if item.dialog_id else None, "text": item.text,
            "read_at": item.read_at.isoformat() if item.read_at else None,
            "created_at": item.created_at.isoformat(),
        } for item in qs[:500]]
        return JsonResponse({"ok": True, "items": items, "count": len(items)})
    try:
        data = _json_body(request)
        text = _str_field(data, "text")
        if not text:
            raise OnlineChatApiError("text is required")
        item = InternalMessage.objects.create(
            sender=get_object_or_404(OperatorProfile, pk=data.get("sender_id")),
            recipient=get_object_or_404(OperatorProfile, pk=data.get("recipient_id")),
            dialog=(
                get_object_or_404(Dialog, pk=data["dialog_id"]) if data.get("dialog_id") else None
            ),
            text=text,
        )
        return JsonResponse({"ok": True, "message": {"id": str(item.id), "text": item.text}}, status=201)
    except OnlineChatApiError as exc:
        return _error(exc)


@csrf_exempt
@require_http_methods(["POST"])
@_chat_permissions(PERM_CC_ADMIN)
def routing_run(request: HttpRequest) -> HttpResponse:
    assigned = run_assignments()
    return JsonResponse({
        "ok": True, "assigned": len(assigned),
        "dialog_ids": [str(item.id) for item in assigned],
    })


@require_http_methods(["GET"])
def widget_config(request: HttpRequest, widget_id: str) -> HttpResponse:
    item = get_object_or_404(WidgetPlacement, widget_id=widget_id, is_active=True)
    source = request.headers.get("Origin") or request.headers.get("Referer") or ""
    source_host = (urlparse(source).hostname or "").casefold()
    allowed = {
        str(domain).strip().casefold()
        for domain in item.allowed_domains
        if str(domain).strip()
    }
    if allowed and source_host and source_host not in allowed:
        return JsonResponse(
            {"ok": False, "error": "origin_not_allowed"},
            status=403,
        )
    return JsonResponse({"ok": True, "config": _placement_dict(item, public=True)})


def _debug_only() -> JsonResponse | None:
    if not settings.DEBUG:
        return JsonResponse({"detail": "Not found"}, status=404)
    return None


_SEED_OPERATOR_NAMES = (
    "Иванов И.И.",
    "Петрова А.С.",
    "Сидоров М.В.",
    "Козлова Е.Н.",
    "Морозов Д.А.",
    "Васильева Н.П.",
    "Новиков А.В.",
    "Фёдорова О.Л.",
    "Смирнов К.С.",
    "Орлова Т.М.",
)


def _seed_operator_name(index: int) -> str:
    if index < len(_SEED_OPERATOR_NAMES):
        return _SEED_OPERATOR_NAMES[index]
    return f"Оператор {index + 1}"


def _seed_client_phone(index: int) -> str:
    # Matches widget.js sim_client phone pattern: +375 29 + last 7 of (1000000 + N)
    return f"+375 29 {str(1000000 + index + 1)[-7:]}"


@csrf_exempt
@require_http_methods(["POST"])
def dev_reset(request: HttpRequest) -> HttpResponse:
    denied = _debug_only()
    if denied:
        return denied
    Dialog.objects.all().delete()
    RoutingRule.objects.all().delete()
    BotConfiguration.objects.all().delete()
    WidgetPlacement.objects.all().delete()
    ChannelConnection.objects.all().delete()
    OperatorProfile.objects.all().delete()
    Department.objects.all().delete()
    return JsonResponse({"ok": True, "summary": {"reset": True}})


@csrf_exempt
@require_http_methods(["POST"])
def dev_seed(request: HttpRequest) -> HttpResponse:
    denied = _debug_only()
    if denied:
        return denied
    try:
        data = _json_body(request)
        operator_count = int(data.get("operators", 3))
        client_count = int(data.get("clients", 10))
        message_count = int(data.get("messages_per_dialog", 1))
        should_assign = _bool_field(data, "auto_assign", True)
        should_reset = _bool_field(data, "reset", False)
        if not 0 <= operator_count <= 100 or not 0 <= client_count <= 1000:
            raise OnlineChatApiError("seed counts are out of range")
        if should_reset:
            Dialog.objects.all().delete()
            OperatorProfile.objects.filter(external_id__startswith="dev-operator-").delete()
            WidgetPlacement.objects.filter(
                widget_id__in=("dev-widget", "site-belarusbank")
            ).delete()
            ChannelConnection.objects.filter(external_id__startswith="dev-").delete()
            RoutingRule.objects.filter(name__startswith="Dev ").delete()
            BotConfiguration.objects.filter(name__startswith="Dev ").delete()
            Department.objects.filter(code="dev-support").delete()
        department, _ = Department.objects.update_or_create(
            code="dev-support",
            defaults={
                "name": "Поддержка КЦ",
                "priority": 10,
                "description": "Отдел для локальной симуляции онлайн-чата",
                "max_queue_size": 200,
                "is_active": True,
            },
        )
        placement, _ = WidgetPlacement.objects.update_or_create(
            widget_id="site-belarusbank",
            defaults={
                "name": "Сайт Беларусбанка",
                "department": department,
                "is_active": True,
                "welcome_message": "Здравствуйте! Чем можем помочь?",
                "queue_message": "Ожидайте ответа оператора…",
                "offline_message": "Сейчас операторы недоступны. Оставьте сообщение — ответим позже.",
                "require_phone": False,
                "allowed_domains": ["localhost", "127.0.0.1"],
                "theme": {"accent": "#2E7D52"},
                "form_fields": [
                    {"key": "name", "label": "Имя", "required": True, "type": "text"},
                    {"key": "last_name", "label": "Фамилия", "required": False, "type": "text"},
                    {"key": "phone", "label": "Телефон", "required": False, "type": "tel"},
                    {"key": "question", "label": "Вопрос", "required": True, "type": "text"},
                ],
            },
        )
        ChannelConnection.objects.update_or_create(
            channel=ChannelConnection.Channel.WIDGET,
            external_id="dev-widget-site",
            defaults={
                "name": "Виджет сайта",
                "department": department,
                "is_active": True,
                "health_status": "ok",
            },
        )
        ChannelConnection.objects.update_or_create(
            channel=ChannelConnection.Channel.TELEGRAM,
            external_id="dev-telegram",
            defaults={
                "name": "Telegram (demo)",
                "department": department,
                "is_active": True,
                "health_status": "not_configured",
                "config": {"note": "Токен задаётся через TELEGRAM_BOT_TOKEN"},
            },
        )
        RoutingRule.objects.update_or_create(
            name="Dev widget → Поддержка КЦ",
            defaults={
                "priority": 10,
                "channel": "widget",
                "placement": placement,
                "department": department,
                "conditions": {"max_load": 5},
                "is_active": True,
            },
        )
        BotConfiguration.objects.update_or_create(
            name="Dev бот FAQ",
            department=department,
            defaults={
                "is_active": False,
                "welcome_message": "Здравствуйте! Я виртуальный помощник. Напишите «карта» или «вклад».",
                "fallback_message": "Передаю обращение оператору.",
                "handoff_message": "Подключаю оператора. Пожалуйста, ожидайте.",
                "trigger_responses": {
                    "карт": "Уточните, пожалуйста, вопрос по карте.",
                    "вклад": "Какой вклад вас интересует?",
                },
                "max_bot_turns": 3,
            },
        )
        operators = []
        for index in range(operator_count):
            display_name = _seed_operator_name(index)
            operator, _ = OperatorProfile.objects.update_or_create(
                external_id=f"dev-operator-{index + 1}",
                defaults={
                    "display_name": display_name,
                    "email": f"operator{index + 1}@dev.local",
                    "presence": OperatorProfile.Presence.ONLINE,
                    "auto_assign": should_assign,
                    "max_active_dialogs": 3,
                    "is_active": True,
                    "role": OperatorProfile.Role.OPERATOR,
                },
            )
            operator.departments.set([department])
            operators.append(operator)
        dialogs = []
        clients_payload = []
        for index in range(client_count):
            sim_id = f"sim-{index + 1}"
            phone = _seed_client_phone(index)
            dialog, _ = create_dialog_with_message(
                text=f"Тестовое обращение клиента {index + 1}: нужна консультация.",
                widget_id=placement.widget_id,
                placement="website",
                client_first_name="Клиент",
                client_last_name=str(index + 1),
                client_phone=phone,
                client_external_id=sim_id,
            )
            for message_index in range(1, message_count):
                append_message(
                    dialog,
                    speaker=DialogMessage.Speaker.CLIENT,
                    text=f"Дополнение {message_index + 1} от клиента {index + 1}",
                )
            dialogs.append(dialog)
            widget_url = (
                f"/widget/sample.html?sim_client={quote(sim_id)}"
                f"&dialog_id={quote(str(dialog.id))}"
            )
            clients_payload.append(
                {
                    "id": sim_id,
                    "dialog_id": str(dialog.id),
                    "name": f"Клиент {index + 1}",
                    "phone": phone,
                    "widget_url": widget_url,
                    "status": dialog.status,
                    "operator_name": dialog.operator_name,
                }
            )
        counts = dict(
            Dialog.objects.filter(id__in=[item.id for item in dialogs])
            .values_list("status")
            .annotate(count=Count("id"))
        )
        return JsonResponse(
            {
                "ok": True,
                "summary": {
                    "departments": 1,
                    "placements": 1,
                    "operators": len(operators),
                    "clients": len(dialogs),
                    "dialogs": len(dialogs),
                    "messages": len(dialogs) * max(message_count, 1),
                    "waiting": counts.get(Dialog.Status.WAITING, 0),
                    "active": counts.get(Dialog.Status.ACTIVE, 0),
                    "auto_assign": should_assign,
                    "reset": should_reset,
                    "widget_id": placement.widget_id,
                },
                "operator_names": [item.display_name for item in operators],
                "operators": [_operator_dict(item) for item in operators],
                "client_ids": [item["id"] for item in clients_payload],
                "clients": clients_payload,
                "widget_id": placement.widget_id,
            },
            status=201,
        )
    except (OnlineChatApiError, ValueError, TypeError) as exc:
        return _error(OnlineChatApiError(str(exc)))
