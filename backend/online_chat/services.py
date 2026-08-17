from __future__ import annotations

import logging
import re
from typing import Any

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db.models import Q
from django.utils import timezone

from audit.events import (
    CATEGORY_DATA_SECURITY,
    ONLINE_CHAT_CLIENT_BLOCKED,
    ONLINE_CHAT_CLIENT_UNBLOCKED,
    RESULT_SUCCESS,
)
from audit.schema import AuditSubject
from audit.service import emit
from online_chat.mail import send_dialog_transcript
from online_chat.models import (
    AssignmentSettings,
    BaseMessage,
    BotConfiguration,
    ClientBlock,
    Dialog,
    DialogFeedback,
    DialogMessage,
    DialogTranscriptEmail,
    OperatorProfile,
    WidgetPlacement,
    format_phone_e164,
    normalize_phone,
)
from online_chat.routing_services import (
    accept_waiting_dialog,
    auto_assign_dialog,
    department_queue_is_full,
    record_event,
    select_department,
    start_post_close_grace,
    transfer_to_operator,
)

logger = logging.getLogger(__name__)

ARM_GROUP = "online_chat_arm"


def _active_bot_for_department(department_id: object | None) -> BotConfiguration | None:
    if department_id:
        department_bot = (
            BotConfiguration.objects.filter(department_id=department_id, is_active=True)
            .order_by("created_at")
            .first()
        )
        if department_bot:
            return department_bot
    return (
        BotConfiguration.objects.filter(department__isnull=True, is_active=True)
        .order_by("created_at")
        .first()
    )


def _active_bot(dialog: Dialog) -> BotConfiguration | None:
    return _active_bot_for_department(dialog.department_id)


def _create_bot_message(dialog: Dialog, text: str) -> DialogMessage:
    delivery_status = DialogMessage.ChannelDeliveryStatus.NOT_REQUIRED
    if dialog.channel != "widget":
        delivery_status = DialogMessage.ChannelDeliveryStatus.PENDING
    message = DialogMessage.objects.create(
        dialog=dialog,
        speaker=DialogMessage.Speaker.BOT,
        text=text,
        receipt_status=DialogMessage.ReceiptStatus.DELIVERED,
        channel_delivery_status=delivery_status,
    )
    payload = serialize_message(message)
    broadcast(dialog_group(str(dialog.id)), "message.created", payload)
    broadcast(ARM_GROUP, "message.created", payload)
    if delivery_status == DialogMessage.ChannelDeliveryStatus.PENDING:
        from online_chat.tasks import deliver_channel_message

        try:
            deliver_channel_message.delay(str(message.id))
        except Exception:  # noqa: BLE001 — broker down: deliver inline
            deliver_channel_message(str(message.id))
    return message


def _base_message_matches(
    message: BaseMessage,
    dialog: Dialog,
    placement_config: WidgetPlacement | None = None,
) -> bool:
    targets = [str(value) for value in (message.channels or []) if str(value)]
    if not targets:
        if message.placement_id:
            targets = [f"widget:{message.placement_id}"]
        elif message.channel:
            targets = [message.channel]
        else:
            return True

    if dialog.channel in targets:
        return True
    if dialog.channel != "widget":
        return False
    placement_config = placement_config or WidgetPlacement.objects.filter(
        widget_id=dialog.widget_id
    ).first()
    return bool(
        placement_config
        and f"widget:{placement_config.id}" in targets
    )


def _send_base_messages(
    dialog: Dialog,
    phase: str,
    placement_config: WidgetPlacement | None = None,
) -> int:
    sent = 0
    messages = BaseMessage.objects.filter(
        is_active=True,
        send_phase=phase,
    ).order_by("sort_order", "created_at")
    for message in messages:
        if _base_message_matches(message, dialog, placement_config):
            _create_bot_message(dialog, message.text)
            sent += 1
    return sent


def _handle_bot_turn(dialog: Dialog, client_text: str) -> None:
    bot = _active_bot(dialog)
    if not bot or not dialog.bot_active:
        return
    normalized = client_text.casefold()
    response = ""
    if isinstance(bot.trigger_responses, dict):
        for trigger, candidate in bot.trigger_responses.items():
            if str(trigger).casefold() in normalized:
                response = str(candidate)
                break
    dialog.bot_turns += 1
    should_handoff = not response or dialog.bot_turns >= bot.max_bot_turns
    if should_handoff:
        dialog.bot_active = False
        dialog.routing_reason = f"bot_handoff:{bot.name}"
        dialog.save(
            update_fields=[
                "bot_active",
                "bot_turns",
                "routing_reason",
                "updated_at",
            ]
        )
        _send_base_messages(dialog, BaseMessage.SendPhase.AFTER_BOT)
        _create_bot_message(
            dialog,
            bot.handoff_message or bot.fallback_message,
        )
        auto_assign_dialog(dialog)
        record_event(dialog, "bot_handoff", actor_name=bot.name)
        return
    dialog.save(update_fields=["bot_turns", "updated_at"])
    _create_bot_message(dialog, response)
    record_event(
        dialog,
        "bot_replied",
        actor_name=bot.name,
        payload={"turn": dialog.bot_turns},
    )


def dialog_group(dialog_id: str) -> str:
    return f"online_chat_dialog_{dialog_id}"


def serialize_message(message: DialogMessage) -> dict[str, Any]:
    return {
        "id": str(message.id),
        "dialog_id": str(message.dialog_id),
        "speaker": message.speaker,
        "text": message.display_text(),
        "raw_text": "" if message.is_deleted else message.text,
        "receipt_status": message.receipt_status,
        "reply_to_id": str(message.reply_to_id) if message.reply_to_id else None,
        "quoted_text": message.quoted_text,
        "edited_at": message.edited_at.isoformat() if message.edited_at else None,
        "is_deleted": message.is_deleted,
        "attachment_name": message.attachment_name,
        "attachment_key": message.attachment_key,
        "attachment_content_type": message.attachment_content_type,
        "attachment_size": message.attachment_size,
        "attachment_scan_status": message.attachment_scan_status,
        "external_message_id": message.external_message_id,
        "channel_delivery_status": message.channel_delivery_status,
        "channel_delivery_error": message.channel_delivery_error,
        "response_origin": message.response_origin,
        "created_at": message.created_at.isoformat(),
    }


def serialize_feedback(feedback: DialogFeedback) -> dict[str, Any]:
    return {
        "id": str(feedback.id),
        "dialog_id": str(feedback.dialog_id),
        "rating": feedback.rating,
        "comment": feedback.comment,
        "created_at": feedback.created_at.isoformat(),
    }


def serialize_transcript_email(record: DialogTranscriptEmail) -> dict[str, Any]:
    return {
        "id": str(record.id),
        "dialog_id": str(record.dialog_id),
        "email": record.email,
        "status": record.status,
        "error_detail": record.error_detail,
        "created_at": record.created_at.isoformat(),
        "sent_at": record.sent_at.isoformat() if record.sent_at else None,
    }


def serialize_client_block(block: ClientBlock) -> dict[str, Any]:
    return {
        "id": str(block.id),
        "phone": block.phone,
        "phone_normalized": block.phone_normalized,
        "reason": block.reason,
        "blocked_by": block.blocked_by,
        "dialog_id": str(block.dialog_id) if block.dialog_id else None,
        "is_active": block.is_active,
        "created_at": block.created_at.isoformat(),
        "lifted_at": block.lifted_at.isoformat() if block.lifted_at else None,
    }


def _last_human_message(dialog: Dialog) -> DialogMessage | None:
    return (
        dialog.messages.filter(
            is_deleted=False,
            speaker__in=(
                DialogMessage.Speaker.CLIENT,
                DialogMessage.Speaker.OPERATOR,
            ),
        )
        .order_by("-created_at")
        .first()
    )


def dialog_needs_reply(dialog: Dialog) -> bool:
    """True when the last human message is from the client (operator must answer)."""
    if dialog.status in {Dialog.Status.CLOSED, Dialog.Status.BLOCKED}:
        return False
    last = _last_human_message(dialog)
    return last is not None and last.speaker == DialogMessage.Speaker.CLIENT


def _wait_anchor(dialog: Dialog):
    """Absolute timestamp for the SLA stopwatch (None when not waiting)."""
    if dialog.status in {Dialog.Status.CLOSED, Dialog.Status.BLOCKED}:
        return None
    if not dialog_needs_reply(dialog):
        return None
    last_client = (
        dialog.messages.filter(
            speaker=DialogMessage.Speaker.CLIENT,
            is_deleted=False,
        )
        .order_by("-created_at")
        .first()
    )
    if last_client is None:
        return None
    anchor = last_client.created_at
    if dialog.accepted_at and last_client.created_at <= dialog.accepted_at:
        anchor = dialog.accepted_at
    return anchor


def _wait_seconds(dialog: Dialog) -> int:
    """SLA wait while a client message awaits operator reply; 0 after operator answers.

    TZ: timer from last unanswered client message; resets when operator works/replies.
    Unassigned queue: from client message time. After accept of that same message:
    anchor moves to accepted_at (SLA reset on take). New client messages after accept
    restart the timer from their created_at.
    """
    anchor = _wait_anchor(dialog)
    if anchor is None:
        return 0
    return max(0, int((timezone.now() - anchor).total_seconds()))


def is_test_client_dialog(dialog: Dialog) -> bool:
    """Simulator / seed clients — sufler must stay disabled for these."""
    external = (dialog.client_external_id or "").strip().casefold()
    if external.startswith("sim-") or external.startswith("dev-sim"):
        return True
    first = (dialog.client_first_name or "").strip().casefold()
    last = (dialog.client_last_name or "").strip()
    if first == "клиент" and last.isdigit():
        return True
    preview = (dialog.preview or "").casefold()
    if preview.startswith("тестовое обращение клиента"):
        return True
    return False


_CHANNEL_LABELS = {
    "widget": "Виджет сайта",
    "telegram": "Telegram",
    "viber": "Viber",
    "vk": "VK",
    "ok": "OK",
    "api": "API",
    "email": "E-mail",
}


def channel_label(channel: str) -> str:
    key = (channel or "").strip().lower()
    return _CHANNEL_LABELS.get(key, channel or "неизвестный канал")


def phones_linked(left: str, right: str) -> bool:
    """Same client phone: exact normalized, national BY mobile, or 1-digit typo."""
    a = normalize_phone(left)
    b = normalize_phone(right)
    if not a or not b:
        return False
    if a == b:
        return True
    if len(a) >= 9 and len(b) >= 9 and a[-9:] == b[-9:]:
        return True
    if len(a) == len(b) and len(a) >= 10:
        diffs = sum(1 for x, y in zip(a, b) if x != y)
        if diffs == 1:
            return True
    return len(a) >= 7 and len(b) >= 7 and a[-7:] == b[-7:]


def _name_token_set(first_name: str, last_name: str) -> frozenset[str]:
    parts = []
    for raw in (first_name or "", last_name or ""):
        for token in re.split(r"[\s\-]+", raw.strip().casefold()):
            if len(token) >= 2:
                parts.append(token)
    return frozenset(parts)


def names_linked(
    first_a: str,
    last_a: str,
    first_b: str,
    last_b: str,
) -> bool:
    """Same person even if widget/TG swapped имя/фамилия fields."""
    left = _name_token_set(first_a, last_a)
    right = _name_token_set(first_b, last_b)
    return len(left) >= 2 and left == right


def history_identity_query(
    *,
    phone: str = "",
    external_id: str = "",
    first_name: str = "",
    last_name: str = "",
) -> Q:
    """Match dialogs by phone (primary), external id, and FIO tokens."""
    normalized = normalize_phone(phone)
    phones: set[str] = {normalized} if normalized else set()
    external_ids: set[str] = {external_id.strip()} if external_id.strip() else set()
    name_key = _name_token_set(first_name, last_name)
    matched_ids: set[Any] = set()

    # Expand TG chat_id ↔ phone ↔ widget phone ↔ FIO (order-independent).
    for _ in range(3):
        before = (frozenset(phones), frozenset(external_ids), frozenset(matched_ids))
        for item in Dialog.objects.only(
            "id",
            "client_phone",
            "client_external_id",
            "client_first_name",
            "client_last_name",
        ).iterator(chunk_size=500):
            phone_hit = bool(phones) and any(
                phones_linked(item.client_phone, p) for p in phones
            )
            external_hit = bool(
                item.client_external_id and item.client_external_id in external_ids
            )
            same_fio = bool(name_key) and names_linked(
                first_name,
                last_name,
                item.client_first_name,
                item.client_last_name,
            )
            candidate_phone = normalize_phone(item.client_phone)
            if same_fio and not phone_hit and not external_hit:
                if phones or external_ids:
                    if candidate_phone and not any(
                        phones_linked(candidate_phone, p) for p in phones
                    ):
                        same_fio = False
                else:
                    same_fio = not candidate_phone and not (
                        item.client_external_id or ""
                    ).strip()
            if not (phone_hit or external_hit or same_fio):
                continue
            matched_ids.add(item.id)
            phone_norm = normalize_phone(item.client_phone)
            if phone_norm:
                phones.add(phone_norm)
            if item.client_external_id:
                external_ids.add(item.client_external_id)
        after = (frozenset(phones), frozenset(external_ids), frozenset(matched_ids))
        if after == before:
            break

    if not matched_ids and not phones and not external_ids:
        return Q()

    query = Q()
    if matched_ids:
        query |= Q(id__in=list(matched_ids))
    if phones:
        query |= Q(
            id__in=[
                item.id
                for item in Dialog.objects.only("id", "client_phone")
                if any(phones_linked(item.client_phone, p) for p in phones)
            ]
        )
    if external_ids:
        query |= Q(client_external_id__in=list(external_ids))
    return query if query else Q(pk__in=[])


def serialize_dialog(
    dialog: Dialog,
    *,
    include_messages: bool = False,
    include_history: bool = False,
) -> dict[str, Any]:
    needs_reply = dialog_needs_reply(dialog)
    wait_anchor = _wait_anchor(dialog)
    payload: dict[str, Any] = {
        "id": str(dialog.id),
        "ref_code": dialog.ref_code(),
        "widget_id": dialog.widget_id,
        "placement": dialog.placement,
        "channel": dialog.channel,
        "status": dialog.status,
        "initiated_by": dialog.initiated_by,
        "client_first_name": dialog.client_first_name,
        "client_last_name": dialog.client_last_name,
        "client_phone": dialog.client_phone,
        "client_external_id": dialog.client_external_id,
        "entry_url": dialog.entry_url,
        "locale": dialog.locale,
        "client_name": dialog.client_display_name(),
        "client_online": dialog.client_online,
        "operator_name": dialog.operator_name,
        "operator_id": str(dialog.operator_id) if dialog.operator_id else None,
        "department_id": str(dialog.department_id) if dialog.department_id else None,
        "department_name": dialog.department.name if dialog.department_id else None,
        "routing_reason": dialog.routing_reason,
        "outcome": dialog.outcome,
        "preview": dialog.preview,
        "close_topic": dialog.close_topic,
        "created_at": dialog.created_at.isoformat(),
        "updated_at": dialog.updated_at.isoformat(),
        "accepted_at": dialog.accepted_at.isoformat() if dialog.accepted_at else None,
        "closed_at": dialog.closed_at.isoformat() if dialog.closed_at else None,
        "last_client_message_at": (
            dialog.last_client_message_at.isoformat() if dialog.last_client_message_at else None
        ),
        "first_response_at": (
            dialog.first_response_at.isoformat() if dialog.first_response_at else None
        ),
        "sla_deadline_at": dialog.sla_deadline_at.isoformat() if dialog.sla_deadline_at else None,
        "client_last_seen_at": (
            dialog.client_last_seen_at.isoformat() if dialog.client_last_seen_at else None
        ),
        "needs_reply": needs_reply,
        "wait_seconds": (
            max(0, int((timezone.now() - wait_anchor).total_seconds()))
            if wait_anchor is not None
            else 0
        ),
        "wait_anchor_at": wait_anchor.isoformat() if wait_anchor is not None else None,
        "is_test_client": is_test_client_dialog(dialog),
        "has_feedback": DialogFeedback.objects.filter(dialog_id=dialog.id).exists(),
    }
    if include_messages:
        current_messages = [serialize_message(item) for item in dialog.messages.all()]
        history_messages = (
            _prior_dialog_messages_for_operator(dialog) if include_history else []
        )
        payload["messages"] = history_messages + current_messages
        payload["history_message_count"] = len(history_messages)
    return payload


def _history_separator_payload(
    *,
    separator_id: str,
    dialog_id: str,
    text: str,
    created_at,
) -> dict[str, Any]:
    return {
        "id": separator_id,
        "dialog_id": dialog_id,
        "speaker": "system",
        "text": text,
        "raw_text": text,
        "receipt_status": "read",
        "reply_to_id": None,
        "quoted_text": "",
        "edited_at": None,
        "is_deleted": False,
        "attachment_name": "",
        "attachment_key": "",
        "attachment_content_type": "",
        "attachment_size": 0,
        "attachment_scan_status": "not_required",
        "external_message_id": "",
        "channel_delivery_status": "not_required",
        "channel_delivery_error": "",
        "response_origin": "",
        "created_at": created_at.isoformat(),
        "is_history": True,
    }


def _prior_dialog_messages_for_operator(dialog: Dialog) -> list[dict[str, Any]]:
    """Prepend prior appeals of the same client for ARM scrollback.

    Client channels never receive these — only operator getDialog with
    include_history=1. Identity is cross-channel (phone / external id / FIO).
    """
    query = history_identity_query(
        phone=dialog.client_phone,
        external_id=dialog.client_external_id,
        first_name=dialog.client_first_name,
        last_name=dialog.client_last_name,
    )
    if not query:
        return []
    prior = list(
        Dialog.objects.filter(query)
        .exclude(pk=dialog.pk)
        .prefetch_related("messages")
        .order_by("created_at")[:100]
    )
    packed: list[dict[str, Any]] = []
    current_id = str(dialog.id)
    for prior_dialog in prior:
        when = prior_dialog.closed_at or prior_dialog.created_at
        when_label = when.strftime("%d.%m.%Y %H:%M") if when else ""
        topic = (prior_dialog.close_topic or "").strip() or "без темы"
        channel = channel_label(prior_dialog.channel)
        sep_text = f"—— Предыдущее обращение · {channel} · {when_label} · {topic} ——"
        packed.append(
            _history_separator_payload(
                separator_id=f"history-sep-{prior_dialog.id}",
                dialog_id=current_id,
                text=sep_text,
                created_at=when,
            )
        )
        for message in prior_dialog.messages.all():
            item = serialize_message(message)
            item["is_history"] = True
            packed.append(item)
    if packed:
        packed.append(
            _history_separator_payload(
                separator_id=f"history-sep-current-{dialog.id}",
                dialog_id=current_id,
                text="—— Текущее обращение ——",
                created_at=dialog.created_at,
            )
        )
    return packed


def broadcast(group: str, event_type: str, payload: dict[str, Any]) -> None:
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return
    async_to_sync(channel_layer.group_send)(
        group,
        {"type": "online_chat.event", "event_type": event_type, "payload": payload},
    )


def is_phone_blocked(phone: str) -> ClientBlock | None:
    normalized = normalize_phone(phone)
    if not normalized:
        return None
    return (
        ClientBlock.objects.filter(phone_normalized=normalized, is_active=True)
        .order_by("-created_at")
        .first()
    )


def _emit_block_audit(*, event_type: str, description: str, details: dict[str, Any]) -> None:
    try:
        emit(
            category=CATEGORY_DATA_SECURITY,
            event_type=event_type,
            result=RESULT_SUCCESS,
            subject=AuditSubject(user_login="online-chat", roles=("operator",)),
            module="online_chat",
            description=description,
            severity="warning",
            details=details,
        )
    except Exception:  # noqa: BLE001 — audit must not break chat
        logger.exception("online_chat audit emit failed")


def create_dialog_with_message(
    *,
    text: str,
    widget_id: str = "site-belarusbank",
    placement: str = "website",
    client_first_name: str = "",
    client_last_name: str = "",
    client_phone: str = "",
    client_external_id: str = "",
    entry_url: str = "",
    locale: str = "ru",
    channel: str = "widget",
    initiated_by: str = Dialog.InitiatedBy.CLIENT,
    operator_name: str = "",
) -> tuple[Dialog, DialogMessage]:
    if is_phone_blocked(client_phone):
        raise PermissionError("client is blocked")

    preview = text.strip()[:500]
    status = Dialog.Status.WAITING
    if initiated_by == Dialog.InitiatedBy.OPERATOR and operator_name.strip():
        status = Dialog.Status.ACTIVE
    normalized_phone = format_phone_e164(client_phone) if client_phone else ""

    department, placement_config, routing_reason = select_department(
        widget_id=widget_id,
        channel=channel,
        context={"placement": placement},
    )
    queue_full = department_queue_is_full(department)
    if queue_full:
        routing_reason = f"{routing_reason};queue_full"
    bot = _active_bot_for_department(department.id if department else None)
    now = timezone.now()
    dialog = Dialog.objects.create(
        widget_id=widget_id,
        placement=placement,
        channel=channel,
        status=status,
        initiated_by=initiated_by,
        client_first_name=client_first_name.strip(),
        client_last_name=client_last_name.strip(),
        client_phone=normalized_phone or client_phone.strip(),
        client_external_id=client_external_id.strip(),
        entry_url=entry_url.strip(),
        locale=locale.strip() or "ru",
        operator_name=operator_name.strip(),
        preview=preview,
        department=department,
        routing_reason=routing_reason,
        bot_active=bool(bot) and not queue_full,
        client_online=initiated_by == Dialog.InitiatedBy.CLIENT,
        client_last_seen_at=now if initiated_by == Dialog.InitiatedBy.CLIENT else None,
        last_client_message_at=now if initiated_by == Dialog.InitiatedBy.CLIENT else None,
        accepted_at=now if status == Dialog.Status.ACTIVE else None,
    )
    speaker = (
        DialogMessage.Speaker.OPERATOR
        if initiated_by == Dialog.InitiatedBy.OPERATOR
        else DialogMessage.Speaker.CLIENT
    )
    delivery_status = DialogMessage.ChannelDeliveryStatus.NOT_REQUIRED
    if speaker == DialogMessage.Speaker.OPERATOR and dialog.channel != "widget":
        delivery_status = DialogMessage.ChannelDeliveryStatus.PENDING
    message = DialogMessage.objects.create(
        dialog=dialog,
        speaker=speaker,
        text=text.strip(),
        channel_delivery_status=delivery_status,
    )
    base_messages_sent = _send_base_messages(
        dialog,
        BaseMessage.SendPhase.BEFORE_BOT,
        placement_config,
    )
    if not base_messages_sent and bot and bot.welcome_message:
        _create_bot_message(dialog, bot.welcome_message)
    record_event(
        dialog,
        "created",
        actor_name=operator_name if initiated_by == Dialog.InitiatedBy.OPERATOR else "client",
        payload={
            "widget_id": widget_id,
            "placement_id": str(placement_config.id) if placement_config else None,
            "routing_reason": routing_reason,
        },
    )
    if status == Dialog.Status.WAITING and not dialog.bot_active and not queue_full:
        assigned = auto_assign_dialog(dialog)
        if assigned:
            dialog = assigned
    dialog_payload = serialize_dialog(dialog)
    message_payload = serialize_message(message)
    broadcast(ARM_GROUP, "dialog.created", dialog_payload)
    broadcast(dialog_group(str(dialog.id)), "message.created", message_payload)
    broadcast(ARM_GROUP, "message.created", message_payload)
    if delivery_status == DialogMessage.ChannelDeliveryStatus.PENDING:
        from online_chat.tasks import deliver_channel_message

        deliver_channel_message.delay(str(message.id))
    return dialog, message


def append_message(
    dialog: Dialog,
    *,
    speaker: str,
    text: str,
    reply_to: DialogMessage | None = None,
    attachment_name: str = "",
    attachment_key: str = "",
    attachment_content_type: str = "",
    attachment_size: int = 0,
    attachment_scan_status: str = "not_required",
    external_message_id: str = "",
    response_origin: str = "",
    sufler_suggestion_text: str = "",
) -> DialogMessage:
    cleaned = text.strip()
    quoted = ""
    if reply_to is not None:
        quoted = (reply_to.display_text() or "")[:500]
    if attachment_name and not cleaned:
        cleaned = f"Файл: {attachment_name}"
    receipt = DialogMessage.ReceiptStatus.DELIVERED
    delivery_status = DialogMessage.ChannelDeliveryStatus.NOT_REQUIRED
    if speaker == DialogMessage.Speaker.OPERATOR and dialog.channel != "widget":
        delivery_status = DialogMessage.ChannelDeliveryStatus.PENDING
    message = DialogMessage.objects.create(
        dialog=dialog,
        speaker=speaker,
        text=cleaned,
        reply_to=reply_to,
        quoted_text=quoted,
        attachment_name=attachment_name.strip(),
        attachment_key=attachment_key,
        attachment_content_type=attachment_content_type,
        attachment_size=max(0, attachment_size),
        attachment_scan_status=attachment_scan_status,
        external_message_id=external_message_id.strip(),
        response_origin=response_origin.strip(),
        sufler_suggestion_text=sufler_suggestion_text,
        channel_delivery_status=delivery_status,
        receipt_status=receipt,
    )
    update_fields = ["updated_at", "preview"]
    dialog.preview = cleaned[:500]
    if speaker == DialogMessage.Speaker.CLIENT:
        dialog.client_online = True
        dialog.client_last_seen_at = timezone.now()
        dialog.last_client_message_at = timezone.now()
        update_fields.extend(["client_online", "client_last_seen_at", "last_client_message_at"])
    elif speaker == DialogMessage.Speaker.OPERATOR and dialog.first_response_at is None:
        dialog.first_response_at = timezone.now()
        update_fields.append("first_response_at")
    dialog.save(update_fields=update_fields)
    payload = serialize_message(message)
    broadcast(dialog_group(str(dialog.id)), "message.created", payload)
    broadcast(ARM_GROUP, "message.created", payload)
    # Backup path: client widget also POSTs /read/; if it was online but flag lagged,
    # still notify ARM when marks arrive later.
    if (
        speaker == DialogMessage.Speaker.OPERATOR
        and receipt == DialogMessage.ReceiptStatus.READ
    ):
        broadcast(
            ARM_GROUP,
            "messages.read",
            {
                "dialog_id": str(dialog.id),
                "reader": DialogMessage.Speaker.CLIENT,
                "message_ids": [str(message.id)],
                "messages": [payload],
            },
        )
    if delivery_status == DialogMessage.ChannelDeliveryStatus.PENDING:
        from online_chat.tasks import deliver_channel_message

        message_id = str(message.id)
        try:
            deliver_channel_message.delay(message_id)
        except Exception:  # noqa: BLE001 — broker down: deliver inline
            deliver_channel_message(message_id)
    if speaker == DialogMessage.Speaker.CLIENT and dialog.bot_active:
        _handle_bot_turn(dialog, cleaned)
    return message


def edit_message(message: DialogMessage, *, text: str) -> DialogMessage:
    cleaned = text.strip()
    # Attachment messages may keep an empty caption; file itself is unchanged.
    if not cleaned and not message.attachment_key:
        raise ValueError("text must be non-empty")
    if message.is_deleted:
        raise ValueError("message is deleted")
    if message.speaker == DialogMessage.Speaker.SYSTEM:
        raise ValueError("system messages cannot be edited")
    if not cleaned and message.attachment_name:
        cleaned = f"Файл: {message.attachment_name}"
    message.text = cleaned
    message.edited_at = timezone.now()
    # Keep receipt_status as-is (edit does not revoke delivery/read).
    # Attachment fields are intentionally preserved on text-only edits.
    message.save(update_fields=["text", "edited_at"])
    if message.speaker == DialogMessage.Speaker.CLIENT:
        dialog = message.dialog
        dialog.preview = cleaned[:500]
        dialog.save(update_fields=["preview", "updated_at"])
    elif message.speaker == DialogMessage.Speaker.OPERATOR:
        message.dialog.save(update_fields=["updated_at"])
    payload = serialize_message(message)
    broadcast(dialog_group(str(message.dialog_id)), "message.updated", payload)
    broadcast(ARM_GROUP, "message.updated", payload)
    return message


def delete_message(message: DialogMessage) -> DialogMessage:
    if message.speaker == DialogMessage.Speaker.SYSTEM:
        raise ValueError("system messages cannot be deleted")
    message.is_deleted = True
    message.text = ""
    message.edited_at = timezone.now()
    message.save(update_fields=["is_deleted", "text", "edited_at"])
    dialog = message.dialog
    last = _last_human_message(dialog)
    if last is not None:
        dialog.preview = last.display_text()[:500]
    else:
        dialog.preview = "—"
    dialog.save(update_fields=["preview", "updated_at"])
    payload = serialize_message(message)
    broadcast(dialog_group(str(message.dialog_id)), "message.updated", payload)
    broadcast(ARM_GROUP, "message.updated", payload)
    return message


def accept_dialog(dialog: Dialog, operator_name: str) -> Dialog:
    operator = OperatorProfile.objects.filter(
        display_name=operator_name,
        is_active=True,
    ).first()
    dialog = accept_waiting_dialog(
        dialog.pk,
        operator=operator,
        operator_name=operator_name,
    )
    system = DialogMessage.objects.create(
        dialog=dialog,
        speaker=DialogMessage.Speaker.SYSTEM,
        text=f"{operator_name} подключился к диалогу",
        receipt_status=DialogMessage.ReceiptStatus.READ,
    )
    dialog_payload = serialize_dialog(dialog)
    broadcast(ARM_GROUP, "dialog.updated", dialog_payload)
    broadcast(
        dialog_group(str(dialog.id)),
        "operator.joined",
        {
            **dialog_payload,
            "system_message": serialize_message(system),
        },
    )
    return dialog


def transfer_dialog(
    dialog: Dialog,
    *,
    to_operator_name: str,
    from_operator_name: str = "",
) -> Dialog:
    target = to_operator_name.strip()
    if not target:
        raise ValueError("to_operator_name is required")
    previous = dialog.operator_name or from_operator_name or "оператор"
    dialog = transfer_to_operator(dialog, operator_name=target)
    target_is_supervisor = OperatorProfile.objects.filter(
        display_name=target,
        role=OperatorProfile.Role.SUPERVISOR,
        is_active=True,
    ).exists()
    if previous and previous != target and target_is_supervisor:
        system_text = (
            f"К чату присоединился супервизор {target}. "
            f"Оператор {previous} отключился."
        )
    else:
        system_text = f"Диалог переведён: {previous} → {target}"
    system = DialogMessage.objects.create(
        dialog=dialog,
        speaker=DialogMessage.Speaker.SYSTEM,
        text=system_text,
        receipt_status=DialogMessage.ReceiptStatus.READ,
    )
    payload = serialize_dialog(dialog)
    broadcast(ARM_GROUP, "dialog.updated", payload)
    broadcast(
        dialog_group(str(dialog.id)),
        "dialog.transferred",
        {
            **payload,
            "system_message": serialize_message(system),
            "from_operator_name": previous,
            "to_operator_name": target,
        },
    )
    return dialog


def close_dialog(dialog: Dialog, *, topic: str) -> Dialog:
    previous_operator = dialog.operator
    dialog.mark_closed(topic)
    record_event(dialog, "closed", actor_name=dialog.operator_name, payload={"topic": topic})
    system = DialogMessage.objects.create(
        dialog=dialog,
        speaker=DialogMessage.Speaker.SYSTEM,
        text="Диалог завершён",
        receipt_status=DialogMessage.ReceiptStatus.READ,
    )
    try:
        from online_chat.summary_service import ensure_dialog_summaries

        ensure_dialog_summaries(dialog, force=True)
    except Exception:  # noqa: BLE001
        logger.exception("dialog_summary_on_close_failed dialog_id=%s", dialog.id)
    # Manual+auto: grace window for the freed operator before auto-assign fills the slot.
    try:
        hold = start_post_close_grace(previous_operator)
    except Exception:  # noqa: BLE001 — never block close on grace/timer errors
        logger.exception("start_post_close_grace_failed operator=%s", getattr(previous_operator, "id", None))
        hold = None
    payload = serialize_dialog(dialog)
    if hold is not None:
        payload["assignment_grace_until"] = hold.until.isoformat()
        payload["assignment_grace_seconds"] = AssignmentSettings.GRACE_SECONDS
    broadcast(ARM_GROUP, "dialog.updated", payload)
    broadcast(
        dialog_group(str(dialog.id)),
        "dialog.closed",
        {
            **payload,
            "system_message": serialize_message(system),
            "farewell_message": "Спасибо за обращение! Диалог завершён.",
        },
    )
    if str(dialog.channel or "").lower() == "telegram":
        try:
            from online_chat.channel_delivery import send_telegram_close_survey

            send_telegram_close_survey(dialog)
        except Exception:  # noqa: BLE001
            logger.exception("telegram_close_survey_failed dialog_id=%s", dialog.id)
    return dialog


def mark_dialog_messages_read(
    dialog: Dialog,
    *,
    reader: str,
) -> list[DialogMessage]:
    """Mark the other party's unread messages as read (1✓ → 2✓)."""
    if reader == DialogMessage.Speaker.CLIENT:
        target_speaker = DialogMessage.Speaker.OPERATOR
    elif reader == DialogMessage.Speaker.OPERATOR:
        target_speaker = DialogMessage.Speaker.CLIENT
    else:
        return []

    qs = dialog.messages.filter(
        speaker=target_speaker,
        receipt_status=DialogMessage.ReceiptStatus.DELIVERED,
        is_deleted=False,
    )
    message_ids = list(qs.values_list("id", flat=True))
    if not message_ids:
        return []
    qs.update(receipt_status=DialogMessage.ReceiptStatus.READ)
    updated = list(dialog.messages.filter(id__in=message_ids))
    payload = {
        "dialog_id": str(dialog.id),
        "reader": reader,
        "message_ids": [str(item.id) for item in updated],
        "messages": [serialize_message(item) for item in updated],
    }
    broadcast(dialog_group(str(dialog.id)), "messages.read", payload)
    broadcast(ARM_GROUP, "messages.read", payload)
    return updated


def set_client_presence(dialog: Dialog, *, online: bool) -> Dialog:
    dialog.client_online = online
    dialog.client_last_seen_at = timezone.now()
    if not online and dialog.status not in {Dialog.Status.CLOSED, Dialog.Status.BLOCKED}:
        dialog.outcome = Dialog.Outcome.OFFLINE
    elif online and dialog.outcome == Dialog.Outcome.OFFLINE:
        dialog.outcome = ""
    dialog.save(
        update_fields=[
            "client_online",
            "client_last_seen_at",
            "outcome",
            "updated_at",
        ]
    )
    payload = serialize_dialog(dialog)
    broadcast(ARM_GROUP, "dialog.updated", payload)
    broadcast(dialog_group(str(dialog.id)), "client.presence", payload)
    return dialog


def block_dialog(
    dialog: Dialog,
    *,
    blocked_by: str = "",
    reason: str = "",
) -> tuple[Dialog, ClientBlock | None]:
    phone = dialog.client_phone
    block: ClientBlock | None = None
    normalized = normalize_phone(phone)
    if normalized:
        block = ClientBlock.objects.create(
            phone=phone,
            phone_normalized=normalized,
            reason=reason.strip() or "Заблокирован оператором в онлайн-чате",
            blocked_by=blocked_by.strip() or dialog.operator_name or "operator",
            dialog=dialog,
            is_active=True,
        )
        _emit_block_audit(
            event_type=ONLINE_CHAT_CLIENT_BLOCKED,
            description=f"Client blocked in online chat ({normalized})",
            details={
                "dialog_id": str(dialog.id),
                "phone_normalized": normalized,
                "blocked_by": block.blocked_by,
                "reason": block.reason,
            },
        )

    dialog.mark_blocked()
    record_event(dialog, "blocked", actor_name=blocked_by, payload={"reason": reason})
    system = DialogMessage.objects.create(
        dialog=dialog,
        speaker=DialogMessage.Speaker.SYSTEM,
        text="Клиент заблокирован. Диалог завершён.",
        receipt_status=DialogMessage.ReceiptStatus.READ,
    )
    payload = serialize_dialog(dialog)
    broadcast(ARM_GROUP, "dialog.updated", payload)
    broadcast(
        dialog_group(str(dialog.id)),
        "dialog.blocked",
        {
            **payload,
            "system_message": serialize_message(system),
            "farewell_message": "Обращение недоступно. При необходимости обратитесь в отделение банка.",
        },
    )
    return dialog, block


def unblock_client(block: ClientBlock, *, lifted_by: str = "") -> ClientBlock:
    block.is_active = False
    block.lifted_at = timezone.now()
    block.save(update_fields=["is_active", "lifted_at"])
    _emit_block_audit(
        event_type=ONLINE_CHAT_CLIENT_UNBLOCKED,
        description=f"Client unblocked in online chat ({block.phone_normalized})",
        details={
            "block_id": str(block.id),
            "phone_normalized": block.phone_normalized,
            "lifted_by": lifted_by or "admin",
        },
    )
    return block


def save_feedback(
    dialog: Dialog,
    *,
    rating: int,
    comment: str = "",
) -> DialogFeedback:
    feedback, _created = DialogFeedback.objects.update_or_create(
        dialog=dialog,
        defaults={
            "rating": rating,
            "comment": comment.strip(),
        },
    )
    return feedback


def request_transcript_email(dialog: Dialog, *, email: str) -> DialogTranscriptEmail:
    return send_dialog_transcript(dialog, email=email)
