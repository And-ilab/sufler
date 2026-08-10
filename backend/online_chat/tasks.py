from __future__ import annotations

from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.utils import timezone

from online_chat.channel_delivery import deliver_message
from online_chat.models import DialogMessage
from online_chat.models import Dialog
from online_chat.routing_services import record_event


@shared_task(
    autoretry_for=(OSError, TimeoutError),
    retry_backoff=True,
    retry_kwargs={"max_retries": 4},
)
def deliver_channel_message(message_id: str) -> dict[str, str | bool]:
    message = DialogMessage.objects.select_related("dialog").get(pk=message_id)
    try:
        result = deliver_message(message)
    except Exception as exc:  # noqa: BLE001 — persist provider failure for ops
        message.channel_delivery_status = DialogMessage.ChannelDeliveryStatus.FAILED
        message.channel_delivery_error = str(exc)[:1000]
        message.save(
            update_fields=["channel_delivery_status", "channel_delivery_error"]
        )
        raise

    message.channel_delivery_status = (
        DialogMessage.ChannelDeliveryStatus.SENT
        if result.sent
        else DialogMessage.ChannelDeliveryStatus.FAILED
    )
    message.channel_delivery_error = "" if result.sent else result.detail
    if result.external_message_id:
        message.external_message_id = result.external_message_id
    message.save(
        update_fields=[
            "channel_delivery_status",
            "channel_delivery_error",
            "external_message_id",
        ]
    )
    return {
        "sent": result.sent,
        "external_message_id": result.external_message_id,
        "detail": result.detail,
    }


@shared_task
def classify_stale_dialogs() -> dict[str, int]:
    timeout = max(60, int(settings.ONLINE_CHAT_LOST_TIMEOUT_SECONDS))
    cutoff = timezone.now() - timedelta(seconds=timeout)
    stale = Dialog.objects.filter(
        client_online=False,
        status__in=(Dialog.Status.WAITING, Dialog.Status.ACTIVE),
        client_last_seen_at__lt=cutoff,
        outcome=Dialog.Outcome.OFFLINE,
    )
    count = 0
    for dialog in stale.iterator():
        dialog.outcome = Dialog.Outcome.LOST
        dialog.save(update_fields=["outcome", "updated_at"])
        record_event(
            dialog,
            "classified_lost",
            actor_name="system",
            payload={"timeout_seconds": timeout},
        )
        count += 1
    return {"classified_lost": count}
