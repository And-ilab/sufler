from __future__ import annotations

import uuid

from django.db import models
from django.utils import timezone


class Dialog(models.Model):
    """Operator ARM dialog started from the site widget (or other channels)."""

    class Status(models.TextChoices):
        WAITING = "waiting", "Ожидает ответа"
        ACTIVE = "active", "В диалоге"
        CLOSED = "closed", "Закрыт"
        BLOCKED = "blocked", "Заблокирован"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    widget_id = models.CharField(max_length=128, blank=True, default="")
    placement = models.CharField(max_length=64, blank=True, default="website")
    channel = models.CharField(max_length=32, default="widget")
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.WAITING,
        db_index=True,
    )
    client_first_name = models.CharField(max_length=100, blank=True, default="")
    client_last_name = models.CharField(max_length=100, blank=True, default="")
    client_phone = models.CharField(max_length=40, blank=True, default="")
    operator_name = models.CharField(max_length=120, blank=True, default="")
    preview = models.CharField(max_length=500, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-updated_at"]
        indexes = [
            models.Index(fields=["status", "-updated_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.client_display_name()} · {self.status}"

    def client_display_name(self) -> str:
        full = f"{self.client_first_name} {self.client_last_name}".strip()
        return full or "Клиент"

    def mark_accepted(self, operator_name: str) -> None:
        self.status = self.Status.ACTIVE
        self.operator_name = operator_name
        self.accepted_at = timezone.now()
        self.save(
            update_fields=["status", "operator_name", "accepted_at", "updated_at"],
        )

    def mark_closed(self) -> None:
        self.status = self.Status.CLOSED
        self.closed_at = timezone.now()
        self.save(update_fields=["status", "closed_at", "updated_at"])

    def mark_blocked(self) -> None:
        self.status = self.Status.BLOCKED
        self.save(update_fields=["status", "updated_at"])


class DialogMessage(models.Model):
    class Speaker(models.TextChoices):
        CLIENT = "client", "Клиент"
        OPERATOR = "operator", "Оператор"
        SYSTEM = "system", "Система"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    dialog = models.ForeignKey(
        Dialog,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    speaker = models.CharField(max_length=16, choices=Speaker.choices)
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self) -> str:
        return f"{self.speaker}: {self.text[:40]}"
