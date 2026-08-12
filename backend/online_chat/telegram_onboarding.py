"""Telegram intake FSM: greeting → question → FIO → phone → ARM queue."""

from __future__ import annotations

import re
import uuid
from typing import Any, Mapping

from online_chat.channel_delivery import send_telegram_text
from online_chat.models import (
    Dialog,
    DialogMessage,
    TelegramOnboardingSession,
    format_phone_e164,
    is_plausible_phone,
)
from online_chat.services import append_message, create_dialog_with_message

GREETING = (
    "Здравствуйте! Вы написали в службу поддержки Беларусбанка.\n\n"
    "Опишите, пожалуйста, ваш вопрос одним сообщением."
)
ASK_FIO = "Спасибо. Укажите, пожалуйста, ваше ФИО (фамилия и имя)."
ASK_PHONE = (
    "Укажите номер телефона для связи (можно с кодом страны).\n"
    "Примеры: +375291234567, 80291234567, +491701234567"
)
INVALID_FIO = "Не удалось разобрать ФИО. Укажите фамилию и имя, например: Иванов Иван."
INVALID_PHONE = (
    "Не удалось распознать номер. Введите телефон цифрами, "
    "можно с «+» и кодом страны."
)
QUEUED = (
    "Спасибо! Ваше обращение передано оператору. "
    "Ожидайте ответа в этом чате."
)


def _parse_fio(raw: str) -> tuple[str, str] | None:
    cleaned = re.sub(r"\s+", " ", (raw or "").strip())
    if len(cleaned) < 3:
        return None
    parts = cleaned.split(" ")
    if len(parts) < 2:
        return None
    last_name = parts[0][:100]
    first_name = " ".join(parts[1:])[:100]
    if not first_name or not last_name:
        return None
    return first_name, last_name


def _active_dialog(chat_id: str) -> Dialog | None:
    return (
        Dialog.objects.filter(
            channel="telegram",
            client_external_id=str(chat_id),
            status__in=(Dialog.Status.WAITING, Dialog.Status.ACTIVE),
        )
        .order_by("-updated_at")
        .first()
    )


def _reply(chat_id: str, text: str, **extra: Any) -> dict[str, Any]:
    send_telegram_text(chat_id, text)
    return {
        "ok": True,
        "channel": "telegram",
        "reply": {"method": "sendMessage", "chat_id": chat_id, "text": text},
        **extra,
    }


def handle_telegram_client_text(
    *,
    chat_id: str,
    text: str,
    raw: Mapping[str, Any],
) -> dict[str, Any]:
    """Process one inbound Telegram text update through onboarding or live dialog."""
    chat_id = str(chat_id)
    cleaned = (text or "").strip()
    if not cleaned:
        return _reply(chat_id, GREETING, routed_to="ignored")

    existing = _active_dialog(chat_id)
    if existing:
        external_message_id = str(raw.get("update_id") or "")
        message = append_message(
            existing,
            speaker=DialogMessage.Speaker.CLIENT,
            text=cleaned,
            external_message_id=external_message_id,
        )
        # No Telegram ack — client already sees their own message in the chat.
        return {
            "ok": True,
            "channel": "telegram",
            "routed_to": "arm_queue",
            "event_id": str(uuid.uuid4()),
            "dialog_id": str(existing.id),
            "message_id": str(message.id),
        }

    session, created = TelegramOnboardingSession.objects.get_or_create(
        chat_id=chat_id,
        defaults={"step": TelegramOnboardingSession.Step.AWAIT_QUESTION},
    )

    is_start = cleaned.casefold() in {"/start", "start", "начать"}
    if is_start or session.step == TelegramOnboardingSession.Step.DONE:
        # Keep last phone/FIO for identity continuity across repeat contacts.
        # Only the question is cleared — phone is re-confirmed later.
        last_dialog = (
            Dialog.objects.filter(
                channel="telegram",
                client_external_id=chat_id,
            )
            .order_by("-created_at")
            .first()
        )
        if last_dialog:
            if not session.phone and last_dialog.client_phone:
                session.phone = last_dialog.client_phone
            if not session.first_name and last_dialog.client_first_name:
                session.first_name = last_dialog.client_first_name
            if not session.last_name and last_dialog.client_last_name:
                session.last_name = last_dialog.client_last_name
        session.step = TelegramOnboardingSession.Step.AWAIT_QUESTION
        session.question = ""
        session.save(
            update_fields=[
                "step",
                "question",
                "first_name",
                "last_name",
                "phone",
                "updated_at",
            ]
        )
        return _reply(chat_id, GREETING, routed_to="onboarding", step=session.step)

    if created:
        # First contact without /start: greet, then treat this message as the question.
        send_telegram_text(chat_id, GREETING)

    if session.step == TelegramOnboardingSession.Step.AWAIT_QUESTION:
        session.question = cleaned[:4000]
        session.step = TelegramOnboardingSession.Step.AWAIT_FIO
        session.save(update_fields=["question", "step", "updated_at"])
        return _reply(chat_id, ASK_FIO, routed_to="onboarding", step=session.step)

    if session.step == TelegramOnboardingSession.Step.AWAIT_FIO:
        parsed = _parse_fio(cleaned)
        if not parsed:
            return _reply(chat_id, INVALID_FIO, routed_to="onboarding", step=session.step)
        first_name, last_name = parsed
        session.first_name = first_name
        session.last_name = last_name
        session.step = TelegramOnboardingSession.Step.AWAIT_PHONE
        session.save(
            update_fields=["first_name", "last_name", "step", "updated_at"]
        )
        return _reply(chat_id, ASK_PHONE, routed_to="onboarding", step=session.step)

    if session.step == TelegramOnboardingSession.Step.AWAIT_PHONE:
        if not is_plausible_phone(cleaned):
            return _reply(
                chat_id, INVALID_PHONE, routed_to="onboarding", step=session.step
            )
        phone = format_phone_e164(cleaned)
        session.phone = phone
        session.step = TelegramOnboardingSession.Step.DONE
        session.save(update_fields=["phone", "step", "updated_at"])
        question = session.question.strip() or "Обращение из Telegram"
        try:
            dialog, message = create_dialog_with_message(
                text=question,
                channel="telegram",
                widget_id="",
                placement="telegram",
                client_first_name=session.first_name,
                client_last_name=session.last_name,
                client_phone=phone,
                client_external_id=chat_id,
            )
        except PermissionError:
            return _reply(
                chat_id,
                "Ваш номер находится в списке блокировок. Обратитесь в отделение банка.",
                routed_to="blocked",
            )
        return _reply(
            chat_id,
            QUEUED,
            routed_to="arm_queue",
            dialog_id=str(dialog.id),
            message_id=str(message.id),
            step=session.step,
        )

    session.step = TelegramOnboardingSession.Step.AWAIT_QUESTION
    session.save(update_fields=["step", "updated_at"])
    return _reply(chat_id, GREETING, routed_to="onboarding")
