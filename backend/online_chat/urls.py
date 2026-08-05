from django.urls import path

from online_chat.views import (
    dialog_accept,
    dialog_block,
    dialog_close,
    dialog_detail,
    dialog_messages,
    dialogs_collection,
)

urlpatterns = [
    path("dialogs/", dialogs_collection, name="online_chat_dialogs"),
    path("dialogs/<uuid:dialog_id>/", dialog_detail, name="online_chat_dialog"),
    path(
        "dialogs/<uuid:dialog_id>/messages/",
        dialog_messages,
        name="online_chat_dialog_messages",
    ),
    path(
        "dialogs/<uuid:dialog_id>/accept/",
        dialog_accept,
        name="online_chat_dialog_accept",
    ),
    path(
        "dialogs/<uuid:dialog_id>/close/",
        dialog_close,
        name="online_chat_dialog_close",
    ),
    path(
        "dialogs/<uuid:dialog_id>/block/",
        dialog_block,
        name="online_chat_dialog_block",
    ),
]
