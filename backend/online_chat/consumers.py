"""WebSocket consumers for widget ↔ ARM online chat."""

from __future__ import annotations

from typing import Any

from channels.generic.websocket import AsyncJsonWebsocketConsumer

from online_chat.services import ARM_GROUP, dialog_group


class OnlineChatArmConsumer(AsyncJsonWebsocketConsumer):
    """Operator ARM queue feed."""

    async def connect(self) -> None:
        await self.channel_layer.group_add(ARM_GROUP, self.channel_name)
        await self.accept()
        await self.send_json({"type": "status", "status": "connected", "role": "arm"})

    async def disconnect(self, code: int) -> None:
        await self.channel_layer.group_discard(ARM_GROUP, self.channel_name)

    async def receive_json(self, content: dict[str, Any], **kwargs: Any) -> None:
        if content.get("type") == "ping":
            await self.send_json({"type": "pong"})

    async def online_chat_event(self, event: dict[str, Any]) -> None:
        await self.send_json(
            {
                "type": event.get("event_type"),
                "payload": event.get("payload") or {},
            },
        )


class OnlineChatDialogConsumer(AsyncJsonWebsocketConsumer):
    """Client widget dialog room."""

    dialog_id: str

    async def connect(self) -> None:
        self.dialog_id = str(self.scope["url_route"]["kwargs"]["dialog_id"])
        await self.channel_layer.group_add(
            dialog_group(self.dialog_id),
            self.channel_name,
        )
        await self.accept()
        await self.send_json(
            {
                "type": "status",
                "status": "connected",
                "role": "widget",
                "dialog_id": self.dialog_id,
            },
        )

    async def disconnect(self, code: int) -> None:
        await self.channel_layer.group_discard(
            dialog_group(self.dialog_id),
            self.channel_name,
        )

    async def receive_json(self, content: dict[str, Any], **kwargs: Any) -> None:
        if content.get("type") == "ping":
            await self.send_json({"type": "pong"})
            return
        # Typing events from either side are relayed into the dialog room.
        if content.get("type") in {"typing.start", "typing.stop"}:
            await self.channel_layer.group_send(
                dialog_group(self.dialog_id),
                {
                    "type": "online_chat.event",
                    "event_type": content["type"],
                    "payload": {
                        "dialog_id": self.dialog_id,
                        "speaker": content.get("speaker") or "client",
                    },
                },
            )

    async def online_chat_event(self, event: dict[str, Any]) -> None:
        await self.send_json(
            {
                "type": event.get("event_type"),
                "payload": event.get("payload") or {},
            },
        )
