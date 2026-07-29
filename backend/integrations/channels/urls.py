from django.urls import path

from integrations.channels.webhooks import (
    channel_inbox,
    telegram_webhook,
    viber_webhook,
    widget_message,
)

urlpatterns = [
    path(
        "telegram/webhook/",
        telegram_webhook,
        name="telegram_webhook",
    ),
    path(
        "viber/webhook/",
        viber_webhook,
        name="viber_webhook",
    ),
    path(
        "widget/<str:widget_id>/messages/",
        widget_message,
        name="widget_message",
    ),
    path("inbox/", channel_inbox, name="channel_inbox"),
]
