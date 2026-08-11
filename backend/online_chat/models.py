from __future__ import annotations

import re
import uuid

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone


def normalize_phone(phone: str) -> str:
    """Canonical digit-only phone for cross-channel matching (widget ↔ Telegram).

    Supports BY (80… / 29… → 375…), RU (8… → 7…), and other international
    numbers as raw digits (E.164 without '+').
    """
    digits = re.sub(r"\D+", "", phone or "")
    if not digits:
        return ""
    # Belarus: 80XXXXXXXXX → 375XXXXXXXXX
    if digits.startswith("80") and len(digits) == 11:
        digits = "375" + digits[2:]
    # Belarus mobile without country code: 29/25/33/44 + 7 digits
    if len(digits) == 9 and digits[:2] in {"25", "29", "33", "44"}:
        digits = "375" + digits
    # Russia / common CIS: 8XXXXXXXXXX → 7XXXXXXXXXX
    if digits.startswith("8") and len(digits) == 11:
        digits = "7" + digits[1:]
    return digits


def format_phone_e164(phone: str) -> str:
    """Store/display form with leading '+' when digits are present."""
    digits = normalize_phone(phone)
    return f"+{digits}" if digits else ""


def is_plausible_phone(phone: str) -> bool:
    digits = normalize_phone(phone)
    return 10 <= len(digits) <= 15


def short_dialog_ref(dialog_id: uuid.UUID | str) -> str:
    raw = str(dialog_id).replace("-", "")
    return raw[:6].upper()


class Department(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.SlugField(max_length=64, unique=True)
    name = models.CharField(max_length=160)
    description = models.TextField(blank=True, default="")
    is_active = models.BooleanField(default=True, db_index=True)
    priority = models.IntegerField(default=100, db_index=True)
    max_queue_size = models.PositiveIntegerField(default=100)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("priority", "name")

    def __str__(self) -> str:
        return self.name


class OperatorProfile(models.Model):
    class Role(models.TextChoices):
        OPERATOR = "operator", "Operator"
        SUPERVISOR = "supervisor", "Supervisor"
        ADMIN = "admin", "Admin"

    class Presence(models.TextChoices):
        ONLINE = "online", "Online"
        BUSY = "busy", "Busy"
        BREAK = "break", "Break"
        TRAINING = "training", "Training"
        LUNCH = "lunch", "Lunch"
        MEETING = "meeting", "Meeting"
        TECH_ISSUE = "tech_issue", "Technical issue"
        OFFLINE = "offline", "Offline"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    external_id = models.CharField(max_length=128, unique=True)
    display_name = models.CharField(max_length=160)
    email = models.EmailField(blank=True, default="")
    role = models.CharField(max_length=16, choices=Role.choices, default=Role.OPERATOR)
    presence = models.CharField(
        max_length=16, choices=Presence.choices, default=Presence.OFFLINE, db_index=True
    )
    departments = models.ManyToManyField(Department, related_name="operators", blank=True)
    max_active_dialogs = models.PositiveIntegerField(default=3)
    auto_assign = models.BooleanField(default=True)
    last_seen_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("display_name",)

    def __str__(self) -> str:
        return self.display_name


class WidgetPlacement(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    widget_id = models.CharField(max_length=128, unique=True)
    name = models.CharField(max_length=160)
    site_url = models.URLField(blank=True, default="")
    allowed_domains = models.JSONField(default=list, blank=True)
    department = models.ForeignKey(
        Department, null=True, blank=True, on_delete=models.SET_NULL, related_name="placements"
    )
    is_active = models.BooleanField(default=True, db_index=True)
    theme = models.JSONField(default=dict, blank=True)
    config = models.JSONField(default=dict, blank=True)
    welcome_message = models.TextField(blank=True, default="")
    queue_message = models.TextField(blank=True, default="")
    offline_message = models.TextField(blank=True, default="")
    require_phone = models.BooleanField(default=False)
    form_fields = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return self.name


class ChannelConnection(models.Model):
    class Channel(models.TextChoices):
        WIDGET = "widget", "Widget"
        TELEGRAM = "telegram", "Telegram"
        VIBER = "viber", "Viber"
        VK = "vk", "VK"
        OK = "ok", "OK"
        API = "api", "API"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    channel = models.CharField(max_length=16, choices=Channel.choices)
    name = models.CharField(max_length=160)
    external_id = models.CharField(max_length=128, blank=True, default="")
    department = models.ForeignKey(
        Department, null=True, blank=True, on_delete=models.SET_NULL, related_name="channels"
    )
    is_active = models.BooleanField(default=True, db_index=True)
    config = models.JSONField(default=dict, blank=True)
    health_status = models.CharField(max_length=32, default="unknown")
    last_health_check_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return self.name


class RoutingRule(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=160)
    priority = models.IntegerField(default=100, db_index=True)
    channel = models.CharField(max_length=16, blank=True, default="")
    placement = models.ForeignKey(
        WidgetPlacement, null=True, blank=True, on_delete=models.CASCADE, related_name="routing_rules"
    )
    department = models.ForeignKey(
        Department, on_delete=models.CASCADE, related_name="routing_rules"
    )
    conditions = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("priority", "created_at")


class BotConfiguration(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=160)
    department = models.ForeignKey(
        Department,
        on_delete=models.CASCADE,
        related_name="bots",
    )
    is_active = models.BooleanField(default=False, db_index=True)
    welcome_message = models.TextField(blank=True, default="")
    fallback_message = models.TextField(
        blank=True,
        default="Передаю обращение оператору.",
    )
    trigger_responses = models.JSONField(default=dict, blank=True)
    max_bot_turns = models.PositiveIntegerField(default=3)
    handoff_message = models.TextField(
        blank=True,
        default="Подключаю оператора. Пожалуйста, ожидайте.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("name",)


class Dialog(models.Model):
    """Operator ARM dialog started from the site widget (or other channels)."""

    class Status(models.TextChoices):
        WAITING = "waiting", "Ожидает ответа"
        ACTIVE = "active", "В диалоге"
        CLOSED = "closed", "Закрыт"
        BLOCKED = "blocked", "Заблокирован"

    class InitiatedBy(models.TextChoices):
        CLIENT = "client", "Клиент"
        OPERATOR = "operator", "Оператор"

    class Outcome(models.TextChoices):
        RESOLVED = "resolved", "Resolved"
        REJECTED = "rejected", "Rejected"
        LOST = "lost", "Lost"
        OFFLINE = "offline", "Offline"
        ESCALATED = "escalated", "Escalated"

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
    initiated_by = models.CharField(
        max_length=16,
        choices=InitiatedBy.choices,
        default=InitiatedBy.CLIENT,
        db_index=True,
    )
    client_first_name = models.CharField(max_length=100, blank=True, default="")
    client_last_name = models.CharField(max_length=100, blank=True, default="")
    client_phone = models.CharField(max_length=40, blank=True, default="")
    client_external_id = models.CharField(max_length=160, blank=True, default="", db_index=True)
    entry_url = models.URLField(blank=True, default="")
    locale = models.CharField(max_length=16, blank=True, default="ru")
    operator_name = models.CharField(max_length=120, blank=True, default="")
    department = models.ForeignKey(
        Department, null=True, blank=True, on_delete=models.SET_NULL, related_name="dialogs"
    )
    operator = models.ForeignKey(
        OperatorProfile, null=True, blank=True, on_delete=models.SET_NULL, related_name="dialogs"
    )
    routing_reason = models.CharField(max_length=255, blank=True, default="")
    outcome = models.CharField(max_length=16, choices=Outcome.choices, blank=True, default="")
    last_client_message_at = models.DateTimeField(null=True, blank=True)
    first_response_at = models.DateTimeField(null=True, blank=True)
    sla_deadline_at = models.DateTimeField(null=True, blank=True)
    bot_active = models.BooleanField(default=False, db_index=True)
    bot_turns = models.PositiveIntegerField(default=0)
    preview = models.CharField(max_length=500, blank=True, default="")
    close_topic = models.CharField(max_length=120, blank=True, default="")
    client_online = models.BooleanField(default=True, db_index=True)
    client_last_seen_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-updated_at",)
        indexes = (
            models.Index(fields=["status", "-updated_at"]),
        )

    def __str__(self) -> str:
        return f"{self.client_display_name()} · {self.status}"

    def client_display_name(self) -> str:
        full = f"{self.client_first_name} {self.client_last_name}".strip()
        return full or "Клиент"

    def ref_code(self) -> str:
        return short_dialog_ref(self.id)

    def mark_accepted(self, operator_name: str) -> None:
        self.status = self.Status.ACTIVE
        self.operator_name = operator_name
        self.accepted_at = timezone.now()
        self.save(
            update_fields=["status", "operator_name", "accepted_at", "updated_at"],
        )

    def mark_closed(self, topic: str = "") -> None:
        self.status = self.Status.CLOSED
        self.close_topic = topic.strip()
        self.closed_at = timezone.now()
        self.save(
            update_fields=["status", "close_topic", "closed_at", "updated_at"],
        )

    def mark_blocked(self) -> None:
        self.status = self.Status.BLOCKED
        self.closed_at = timezone.now()
        self.save(update_fields=["status", "closed_at", "updated_at"])


class DialogMessage(models.Model):
    class Speaker(models.TextChoices):
        CLIENT = "client", "Клиент"
        OPERATOR = "operator", "Оператор"
        BOT = "bot", "Бот"
        SYSTEM = "system", "Система"

    class ReceiptStatus(models.TextChoices):
        DELIVERED = "delivered", "Доставлено"
        READ = "read", "Прочитано"

    class ChannelDeliveryStatus(models.TextChoices):
        NOT_REQUIRED = "not_required", "Не требуется"
        PENDING = "pending", "Ожидает отправки"
        SENT = "sent", "Отправлено в канал"
        FAILED = "failed", "Ошибка доставки"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    dialog = models.ForeignKey(
        Dialog,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    speaker = models.CharField(max_length=16, choices=Speaker.choices)
    text = models.TextField()
    receipt_status = models.CharField(
        max_length=16,
        choices=ReceiptStatus.choices,
        default=ReceiptStatus.DELIVERED,
        db_index=True,
    )
    reply_to = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="replies",
    )
    quoted_text = models.CharField(max_length=500, blank=True, default="")
    edited_at = models.DateTimeField(null=True, blank=True)
    is_deleted = models.BooleanField(default=False)
    attachment_name = models.CharField(max_length=255, blank=True, default="")
    attachment_key = models.CharField(max_length=500, blank=True, default="")
    attachment_content_type = models.CharField(max_length=120, blank=True, default="")
    attachment_size = models.PositiveBigIntegerField(default=0)
    attachment_scan_status = models.CharField(
        max_length=16,
        default="not_required",
        db_index=True,
    )
    external_message_id = models.CharField(max_length=160, blank=True, default="", db_index=True)
    channel_delivery_status = models.CharField(
        max_length=16,
        choices=ChannelDeliveryStatus.choices,
        default=ChannelDeliveryStatus.NOT_REQUIRED,
        db_index=True,
    )
    channel_delivery_error = models.TextField(blank=True, default="")
    response_origin = models.CharField(max_length=32, blank=True, default="")
    sufler_suggestion_text = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ("created_at",)

    def __str__(self) -> str:
        return f"{self.speaker}: {self.text[:40]}"

    def display_text(self) -> str:
        if self.is_deleted:
            return "Сообщение удалено"
        return self.text


class ClientBlock(models.Model):
    """Blocked client identifiers (phone) — reject new widget dialogs."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    phone = models.CharField(max_length=40, blank=True, default="")
    phone_normalized = models.CharField(max_length=40, db_index=True)
    reason = models.CharField(max_length=255, blank=True, default="")
    blocked_by = models.CharField(max_length=120, blank=True, default="")
    dialog = models.ForeignKey(
        Dialog,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="client_blocks",
    )
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    lifted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"{self.phone_normalized} · {'active' if self.is_active else 'lifted'}"


class DialogFeedback(models.Model):
    """Post-chat CSAT from the client widget (§4.4.26–27)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    dialog = models.OneToOneField(
        Dialog,
        on_delete=models.CASCADE,
        related_name="feedback",
    )
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    comment = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"feedback {self.rating}/5 · {self.dialog_id}"


class DialogTranscriptEmail(models.Model):
    """Log of transcript e-mail sends (§4.4.28)."""

    class Status(models.TextChoices):
        PENDING = "pending", "Ожидает"
        SENT = "sent", "Отправлено"
        FAILED = "failed", "Ошибка"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    dialog = models.ForeignKey(
        Dialog,
        on_delete=models.CASCADE,
        related_name="transcript_emails",
    )
    email = models.EmailField()
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    error_detail = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"{self.email} · {self.status}"


class InternalMessage(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sender = models.ForeignKey(
        OperatorProfile, on_delete=models.CASCADE, related_name="internal_messages_sent"
    )
    recipient = models.ForeignKey(
        OperatorProfile, on_delete=models.CASCADE, related_name="internal_messages_received"
    )
    dialog = models.ForeignKey(
        Dialog, null=True, blank=True, on_delete=models.SET_NULL, related_name="internal_messages"
    )
    text = models.TextField()
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ("-created_at",)


class DialogEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    dialog = models.ForeignKey(Dialog, on_delete=models.CASCADE, related_name="events")
    type = models.CharField(max_length=64, db_index=True)
    actor_name = models.CharField(max_length=160, blank=True, default="")
    payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ("created_at",)


class AssignmentSettings(models.Model):
    """Global dialog distribution mode (singleton row pk=1)."""

    class Mode(models.TextChoices):
        STRICT_AUTO = "strict_auto", "Только автоназначение"
        MANUAL_PLUS_AUTO = "manual_plus_auto", "Ручной выбор + авто (5 сек)"

    GRACE_SECONDS = 5

    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    mode = models.CharField(
        max_length=32,
        choices=Mode.choices,
        default=Mode.MANUAL_PLUS_AUTO,
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Assignment settings"
        verbose_name_plural = "Assignment settings"

    def __str__(self) -> str:
        return f"assignment:{self.mode}"

    @classmethod
    def get_solo(cls) -> AssignmentSettings:
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class OperatorAssignmentHold(models.Model):
    """Blocks auto-assign to an operator until ``until`` (manual+auto grace)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    operator = models.ForeignKey(
        OperatorProfile,
        on_delete=models.CASCADE,
        related_name="assignment_holds",
    )
    until = models.DateTimeField(db_index=True)
    reason = models.CharField(max_length=64, blank=True, default="post_close_grace")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-until",)
        indexes = (models.Index(fields=["operator", "until"]),)


class TelegramOnboardingSession(models.Model):
    """FSM state for Telegram intake: greeting → question → FIO → phone → queue."""

    class Step(models.TextChoices):
        AWAIT_QUESTION = "await_question", "Await question"
        AWAIT_FIO = "await_fio", "Await FIO"
        AWAIT_PHONE = "await_phone", "Await phone"
        DONE = "done", "Done"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    chat_id = models.CharField(max_length=64, unique=True, db_index=True)
    step = models.CharField(
        max_length=32,
        choices=Step.choices,
        default=Step.AWAIT_QUESTION,
    )
    question = models.TextField(blank=True, default="")
    first_name = models.CharField(max_length=100, blank=True, default="")
    last_name = models.CharField(max_length=100, blank=True, default="")
    phone = models.CharField(max_length=40, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-updated_at",)

    def __str__(self) -> str:
        return f"tg:{self.chat_id} · {self.step}"


class SuflerHintFeedback(models.Model):
    """Operator rating of a sufler hint (analytics later; persist now)."""

    class Choice(models.TextChoices):
        USED = "used", "Использовал"
        NOT_USED = "not_used", "Не использовал"
        PARTIAL = "partial", "Частично"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    dialog = models.ForeignKey(
        Dialog,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="sufler_hint_feedback",
    )
    operator_name = models.CharField(max_length=160, blank=True, default="")
    query = models.TextField(blank=True, default="")
    hint_rank = models.PositiveSmallIntegerField(default=1)
    hint_text = models.TextField(blank=True, default="")
    choice = models.CharField(max_length=16, choices=Choice.choices)
    relevance_percent = models.PositiveSmallIntegerField(null=True, blank=True)
    citation_title = models.CharField(max_length=255, blank=True, default="")
    request_id = models.CharField(max_length=64, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ("-created_at",)
