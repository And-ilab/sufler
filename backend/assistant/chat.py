"""Assistant chat orchestration via ModelGateway ``assistant_bank`` (Part III.7)."""

from __future__ import annotations

import uuid
from typing import Any, Iterator, Mapping, Sequence

from core.model_gateway import ModelGateway, ModelGatewayConfigurationError
from hub.model_registry_store import get_model_settings

PROFILE = "assistant_bank"
DEFAULT_SYSTEM_PROMPT = (
    "Ты внутренний ИИ-ассистент банка. Отвечай по подтверждённым "
    "корпоративным источникам, кратко и по делу."
)


class AssistantChatError(ValueError):
    """Invalid assistant chat request."""


def _as_messages(payload: Mapping[str, Any]) -> list[dict[str, str]]:
    raw_messages = payload.get("messages")
    single = payload.get("message")

    messages: list[dict[str, str]] = []
    if raw_messages is not None:
        if not isinstance(raw_messages, Sequence) or isinstance(
            raw_messages, (str, bytes)
        ):
            raise AssistantChatError("messages must be an array")
        for index, item in enumerate(raw_messages):
            if not isinstance(item, Mapping):
                raise AssistantChatError(
                    f"messages[{index}] must be an object"
                )
            role = item.get("role")
            content = item.get("content")
            if role not in {"system", "user", "assistant", "tool"}:
                raise AssistantChatError(
                    f"messages[{index}].role is invalid"
                )
            if not isinstance(content, str):
                raise AssistantChatError(
                    f"messages[{index}].content must be a string"
                )
            messages.append({"role": str(role), "content": content})

    if isinstance(single, str) and single.strip():
        messages.append({"role": "user", "content": single.strip()})

    if not messages:
        raise AssistantChatError(
            "Provide non-empty message or messages[]"
        )

    has_user = any(
        item["role"] == "user" and item["content"].strip()
        for item in messages
    )
    if not has_user:
        raise AssistantChatError("At least one user message is required")

    if not any(item["role"] == "system" for item in messages):
        messages = [
            {"role": "system", "content": DEFAULT_SYSTEM_PROMPT},
            *messages,
        ]
    return messages


def parse_chat_request(payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise AssistantChatError("Request body must be a JSON object")

    messages = _as_messages(payload)
    attachments = payload.get("attachments")
    if attachments is not None:
        messages = _apply_attachments(messages, attachments)

    session_id = payload.get("session_id")
    if session_id is None:
        session_id = str(uuid.uuid4())
    elif not isinstance(session_id, str) or not session_id.strip():
        raise AssistantChatError("session_id must be a non-empty string")

    stream = payload.get("stream", True)
    if not isinstance(stream, bool):
        raise AssistantChatError("stream must be a boolean")
    if not stream:
        raise AssistantChatError(
            "Only stream=true is supported on POST /chat (SSE)"
        )

    return {
        "messages": messages,
        "session_id": session_id.strip(),
        "stream": True,
    }


def _apply_attachments(
    messages: list[dict[str, str]],
    attachments: Any,
) -> list[dict[str, str]]:
    """ASS-T-04/04a: fold attachment text into the last user message."""
    if not isinstance(attachments, Sequence) or isinstance(
        attachments, (str, bytes)
    ):
        raise AssistantChatError("attachments must be an array")
    parts: list[str] = []
    for index, item in enumerate(attachments):
        if not isinstance(item, Mapping):
            raise AssistantChatError(f"attachments[{index}] must be an object")
        kind = str(item.get("type") or item.get("content_type") or "").lower()
        name = str(item.get("name") or item.get("filename") or f"file-{index}")
        text = item.get("text") or item.get("extracted_text") or ""
        if not isinstance(text, str) or not text.strip():
            raise AssistantChatError(
                f"attachments[{index}] requires text/extracted_text "
                "(smoke path for summarization)"
            )
        if kind in {"pdf", "application/pdf"}:
            parts.append(
                f"[Вложение PDF «{name}» — саммаризируй содержимое]\n"
                f"{text.strip()}"
            )
        elif kind.startswith("audio") or kind.startswith("video") or kind in {
            "audio",
            "video",
        }:
            parts.append(
                f"[Вложение {kind} «{name}» — саммаризируй содержимое]\n"
                f"{text.strip()}"
            )
        else:
            parts.append(f"[Вложение «{name}»]\n{text.strip()}")
    if not parts:
        return messages
    appendix = "\n\n".join(parts)
    for index in range(len(messages) - 1, -1, -1):
        if messages[index]["role"] == "user":
            messages[index] = {
                "role": "user",
                "content": f"{messages[index]['content']}\n\n{appendix}".strip(),
            }
            return messages
    messages.append({"role": "user", "content": appendix})
    return messages


def iter_chat_sse(
    messages: Sequence[Mapping[str, str]],
    *,
    gateway: ModelGateway | None = None,
    request_id: str | None = None,
) -> Iterator[str]:
    """Yield OpenAI-compatible SSE frames from ``assistant_bank``."""
    active = gateway or ModelGateway.from_registry()
    try:
        settings = get_model_settings(PROFILE)
        parameters: dict[str, Any] = {
            "temperature": float(settings.temperature),
            "top_p": float(settings.top_p),
            "max_tokens": int(settings.max_tokens),
        }
    except Exception:
        parameters = {}

    # Prefix optional correlation as a comment frame for clients/tests.
    if request_id:
        yield f": request_id {request_id}\n\n"

    try:
        yield from active.stream(PROFILE, messages, **parameters)
    except ModelGatewayConfigurationError as exc:
        raise AssistantChatError(str(exc)) from exc
