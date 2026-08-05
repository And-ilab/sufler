from __future__ import annotations

from typing import Any

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.utils import timezone

from online_chat.models import Dialog, DialogMessage


ARM_GROUP = "online_chat_arm"


def dialog_group(dialog_id: str) -> str:
    return f"online_chat_dialog_{dialog_id}"


def serialize_message(message: DialogMessage) -> dict[str, Any]:
    return {
        "id": str(message.id),
        "dialog_id": str(message.dialog_id),
        "speaker": message.speaker,
        "text": message.text,
        "created_at": message.created_at.isoformat(),
    }


def serialize_dialog(dialog: Dialog, *, include_messages: bool = False) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": str(dialog.id),
        "widget_id": dialog.widget_id,
        "placement": dialog.placement,
        "channel": dialog.channel,
        "status": dialog.status,
        "client_first_name": dialog.client_first_name,
        "client_last_name": dialog.client_last_name,
        "client_phone": dialog.client_phone,
        "client_name": dialog.client_display_name(),
        "operator_name": dialog.operator_name,
        "preview": dialog.preview,
        "created_at": dialog.created_at.isoformat(),
        "updated_at": dialog.updated_at.isoformat(),
        "accepted_at": dialog.accepted_at.isoformat() if dialog.accepted_at else None,
        "closed_at": dialog.closed_at.isoformat() if dialog.closed_at else None,
        "wait_seconds": max(
            0,
            int((timezone.now() - dialog.created_at).total_seconds()),
        ),
    }
    if include_messages:
        payload["messages"] = [
            serialize_message(item) for item in dialog.messages.all()
        ]
    return payload


def broadcast(group: str, event_type: str, payload: dict[str, Any]) -> None:
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return
    async_to_sync(channel_layer.group_send)(
        group,
        {"type": "online_chat.event", "event_type": event_type, "payload": payload},
    )


def create_dialog_with_message(
    *,
    text: str,
    widget_id: str = "site-belarusbank",
    placement: str = "website",
    client_first_name: str = "",
    client_last_name: str = "",
    client_phone: str = "",
    channel: str = "widget",
) -> tuple[Dialog, DialogMessage]:
    preview = text.strip()[:500]
    dialog = Dialog.objects.create(
        widget_id=widget_id,
        placement=placement,
        channel=channel,
        status=Dialog.Status.WAITING,
        client_first_name=client_first_name.strip(),
        client_last_name=client_last_name.strip(),
        client_phone=client_phone.strip(),
        preview=preview,
    )
    message = DialogMessage.objects.create(
        dialog=dialog,
        speaker=DialogMessage.Speaker.CLIENT,
        text=text.strip(),
    )
    dialog_payload = serialize_dialog(dialog)
    message_payload = serialize_message(message)
    broadcast(ARM_GROUP, "dialog.created", dialog_payload)
    broadcast(dialog_group(str(dialog.id)), "message.created", message_payload)
    broadcast(ARM_GROUP, "message.created", message_payload)
    return dialog, message


def append_message(
    dialog: Dialog,
    *,
    speaker: str,
    text: str,
) -> DialogMessage:
    cleaned = text.strip()
    message = DialogMessage.objects.create(
        dialog=dialog,
        speaker=speaker,
        text=cleaned,
    )
    update_fields = ["updated_at"]
    if speaker == DialogMessage.Speaker.CLIENT:
        dialog.preview = cleaned[:500]
        update_fields.append("preview")
    dialog.save(update_fields=update_fields)
    payload = serialize_message(message)
    broadcast(dialog_group(str(dialog.id)), "message.created", payload)
    broadcast(ARM_GROUP, "message.created", payload)
    return message


def accept_dialog(dialog: Dialog, operator_name: str) -> Dialog:
    dialog.mark_accepted(operator_name)
    system = DialogMessage.objects.create(
        dialog=dialog,
        speaker=DialogMessage.Speaker.SYSTEM,
        text=f"{operator_name} подключился к диалогу",
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


def close_dialog(dialog: Dialog) -> Dialog:
    dialog.mark_closed()
    payload = serialize_dialog(dialog)
    broadcast(ARM_GROUP, "dialog.updated", payload)
    broadcast(dialog_group(str(dialog.id)), "dialog.closed", payload)
    return dialog


def block_dialog(dialog: Dialog) -> Dialog:
    dialog.mark_blocked()
    payload = serialize_dialog(dialog)
    broadcast(ARM_GROUP, "dialog.updated", payload)
    broadcast(dialog_group(str(dialog.id)), "dialog.blocked", payload)
    return dialog
