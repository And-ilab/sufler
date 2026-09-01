"""Assistant chat orchestration: RAG over assistant_* → ModelGateway stream."""

from __future__ import annotations

import json
import os
import uuid
from typing import Any, Iterator, Mapping, Sequence

from core.embeddings import embedding_backend_info
from core.model_gateway import ModelGateway, ModelGatewayConfigurationError
from hub.model_registry_store import get_model_settings
from assistant.idp import (
    build_attachment_prompt,
    has_attachment_marker,
    wants_summary,
)
from qu.assistant_retrieval import preview_assistant_query

PROFILE = "assistant_bank"
_ANSWER_STYLE = (
    "Пиши обычным текстом, без markdown (без **, *, заголовков #). "
    "Не перечисляй источники в тексте, не пиши «Источники:», номера [1] "
    "и фразы вроде «по предоставленным фрагментам» или «в базе знаний "
    "найдено» — источники уже показаны отдельно."
)
DEFAULT_SYSTEM_PROMPT = (
    "Ты внутренний ИИ-ассистент банка. Отвечай по подтверждённым "
    "корпоративным источникам, по делу. "
    "Заканчивай законченным предложением и законченной мыслью. "
    + _ANSWER_STYLE
)
GROUNDED_SYSTEM_PROMPT = (
    "Ты внутренний ИИ-ассистент банка. Отвечай ТОЛЬКО фактами из "
    "переданных фрагментов базы знаний. Внимательно читай каждый фрагмент "
    "целиком: числа, сроки и условия уже есть в тексте — перенеси их "
    "в ответ дословно (например «сроком на 5 лет», «3 месяца»). "
    "Не утверждай, что данных нет, если они явно указаны во фрагментах. "
    "Не выводи сроки и даты из названий файлов или URL. "
    "Если во фрагментах несколько разных сроков — ответь по документу, "
    "который прямо отвечает на вопрос пользователя, и не смешивай "
    "чужие условия. "
    "Если действительно нет нужных фактов — скажи об этом. "
    "Ответ по делу: закончи законченным предложением и законченной "
    "мыслью, не обрывай фразу, список или абзац на середине. "
    + _ANSWER_STYLE
)
EXPAND_SYSTEM_PROMPT = (
    "Ты внутренний ИИ-ассистент банка. Дай полный ответ по фактам "
    "из переданных фрагментов: все условия, кому подходит, как оформить, "
    "лимиты и документы. Не обрывай текст на середине предложения. "
    "Числа и сроки бери дословно из фрагментов. "
    + _ANSWER_STYLE
)
# Local llama often runs with -c 4096; five full .doc chunks overflow (~10k tokens).
DEFAULT_RAG_LIMIT = 3
# Per-chunk budget for the LLM (UI citations still use short snippet).
LLM_CHUNK_CHARS = 2800
# Soft cap for all RAG bodies combined (leaves room for system + question + answer).
LLM_RAG_TOTAL_CHARS = 7200
_DURATION_MARKERS = (
    "сроком на",
    "срок",
    "бессрочн",
    "месяц",
    "календарн",
    "дней",
    " лет",
    "года",
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


def _parse_kb_slugs(payload: Mapping[str, Any]) -> list[str]:
    raw = payload.get("kb_slugs")
    if raw is None:
        single = payload.get("kb_slug")
        if isinstance(single, str) and single.strip():
            return [single.strip()]
        return []
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
        raise AssistantChatError("kb_slugs must be an array of strings")
    slugs: list[str] = []
    for index, item in enumerate(raw):
        if not isinstance(item, str) or not item.strip():
            raise AssistantChatError(
                f"kb_slugs[{index}] must be a non-empty string"
            )
        slugs.append(item.strip())
    return slugs


def parse_chat_request(payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise AssistantChatError("Request body must be a JSON object")

    attachments = payload.get("attachments")
    has_attachments = (
        isinstance(attachments, Sequence)
        and not isinstance(attachments, (str, bytes))
        and len(attachments) > 0
    )
    working: dict[str, Any] = dict(payload)
    message = working.get("message")
    if (
        has_attachments
        and (not isinstance(message, str) or not message.strip())
        and not working.get("messages")
    ):
        # Attachment-only send: still need a user turn for the LLM.
        working["message"] = "Суммаризируй вложение."

    messages = _as_messages(working)
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

    expand = payload.get("expand", False)
    if not isinstance(expand, bool):
        raise AssistantChatError("expand must be a boolean")

    return {
        "messages": messages,
        "session_id": session_id.strip(),
        "stream": True,
        "kb_slugs": _parse_kb_slugs(payload),
        "expand": expand,
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
    for index, item in enumerate(attachments):
        if not isinstance(item, Mapping):
            raise AssistantChatError(f"attachments[{index}] must be an object")
        text = item.get("text") or item.get("extracted_text") or ""
        if not isinstance(text, str) or not text.strip():
            raise AssistantChatError(
                f"attachments[{index}] requires text/extracted_text "
                "(IDP summarization path)"
            )
    query = _last_user_text(messages)
    appendix = build_attachment_prompt(attachments, query)
    if not appendix:
        return messages
    for index in range(len(messages) - 1, -1, -1):
        if messages[index]["role"] == "user":
            messages[index] = {
                "role": "user",
                "content": f"{messages[index]['content']}\n\n{appendix}".strip(),
            }
            return messages
    messages.append({"role": "user", "content": appendix})
    return messages


def _last_user_text(messages: Sequence[Mapping[str, str]]) -> str:
    for item in reversed(messages):
        if item.get("role") == "user":
            return str(item.get("content") or "").strip()
    return ""


def _citation(document: Mapping[str, Any]) -> dict[str, Any]:
    kb_slug = str(document.get("kb_slug") or "")
    article_id = document.get("article_id")
    permalink = str(document.get("permalink") or "")
    # Always prefer download API so chat sources open the file, not admin UI.
    if kb_slug and article_id is not None:
        try:
            from hub.assistant_admin import assistant_source_download_url

            permalink = assistant_source_download_url(
                kb_slug=kb_slug,
                article_id=article_id,
            )
        except Exception:
            pass
    return {
        "id": (
            f"{kb_slug}:{article_id}:"
            f"{document.get('chunk_index')}"
        ),
        "kb_slug": kb_slug or document.get("kb_slug"),
        "article_id": article_id,
        "chunk_index": document["chunk_index"],
        "title": document["title"],
        "permalink": permalink,
        "snippet": document.get("snippet") or "",
        "relevance_percent": document.get("relevance_percent"),
    }


def _trim_text_for_llm(text: str, max_chars: int) -> str:
    """Fit chunk into local context; keep a window around duration clauses."""
    cleaned = text.strip()
    if max_chars <= 0 or not cleaned:
        return ""
    if len(cleaned) <= max_chars:
        return cleaned

    lower = cleaned.lower()
    marker_at = -1
    for marker in _DURATION_MARKERS:
        index = lower.find(marker)
        if index >= 0 and (marker_at < 0 or index < marker_at):
            marker_at = index

    if marker_at >= 0:
        # Keep ~1/3 before the marker so «Настоящее согласие дается сроком…» stays intact.
        start = max(0, marker_at - max_chars // 3)
        end = min(len(cleaned), start + max_chars)
        if end - start < max_chars:
            start = max(0, end - max_chars)
        piece = cleaned[start:end]
        prefix = "…" if start else ""
        suffix = "…" if end < len(cleaned) else ""
        return f"{prefix}{piece}{suffix}"

    return cleaned[:max_chars] + "…"


def _document_raw_text(document: Mapping[str, Any]) -> str:
    content = document.get("content")
    if isinstance(content, str) and content.strip():
        return content
    snippet = document.get("snippet")
    return snippet if isinstance(snippet, str) else ""


def _document_context_text(document: Mapping[str, Any], max_chars: int) -> str:
    """Chunk text for the LLM, capped to fit local llama context."""
    return _trim_text_for_llm(_document_raw_text(document), max_chars)


def _inject_rag_context(
    messages: Sequence[Mapping[str, str]],
    documents: Sequence[Mapping[str, Any]],
    *,
    expand: bool = False,
) -> list[dict[str, str]]:
    context_blocks = []
    remaining = 16000 if expand else LLM_RAG_TOTAL_CHARS
    chunk_budget = 6000 if expand else LLM_CHUNK_CHARS
    for document in documents:
        if remaining <= 200:
            break
        per_doc = min(chunk_budget, remaining)
        body = _document_context_text(document, per_doc)
        if not body:
            continue
        remaining -= len(body)
        context_blocks.append(
            f"[{document['rank']}] {document['title']} "
            f"(БЗ: {document.get('kb_slug', '')})\n"
            f"URL: {document['permalink']}\n"
            f"{body}"
        )
    context = "\n\n".join(context_blocks)
    query = _last_user_text(messages)
    system_prompt = EXPAND_SYSTEM_PROMPT if expand else GROUNDED_SYSTEM_PROMPT
    grounded = [
        {"role": "system", "content": system_prompt},
        *[
            {"role": item["role"], "content": item["content"]}
            for item in messages
            if item.get("role") != "system"
        ],
    ]
    # Replace last user turn with query + retrieved fragments.
    for index in range(len(grounded) - 1, -1, -1):
        if grounded[index]["role"] == "user":
            grounded[index] = {
                "role": "user",
                "content": (
                    f"Вопрос пользователя:\n{query}\n\n"
                    f"Фрагменты базы знаний:\n{context}\n\n"
                    + (
                        "Разверни полный ответ только по тексту фрагментов: "
                        "все условия, кому подходит, как оформить. "
                        "Допиши ответ до конца, не обрывай предложение. "
                        if expand
                        else "Сформулируй полный ответ только по тексту фрагментов. "
                        "Закончи законченным предложением и законченной мыслью: "
                        "не обрывай фразу, список или абзац на середине. "
                    )
                    + "Числа и сроки бери дословно из тела фрагмента, "
                    "не из имени файла. Если срока в тексте нет — так и скажи. "
                    "Без markdown и без списка источников в тексте."
                ),
            }
            break
    return grounded


def retrieve_assistant_context(
    messages: Sequence[Mapping[str, str]],
    *,
    kb_slugs: Sequence[str] | None = None,
    limit: int = DEFAULT_RAG_LIMIT,
) -> tuple[list[dict[str, Any]], float]:
    """Return documents above the context-inclusion threshold."""
    query = _last_user_text(messages)
    if not query:
        return [], 0.0
    settings = get_model_settings(PROFILE)
    threshold = float(settings.context_inclusion_threshold)
    # Hash stub embeddings yield low absolute cosine scores; keep RAG usable locally.
    if embedding_backend_info()["mode"] == "stub":
        threshold = min(threshold, 0.05)
    result = preview_assistant_query(
        query,
        kb_slugs=kb_slugs,
        limit=limit,
    )
    documents = [
        document
        for document in result["documents"]
        if float(document["relevance_score"]) >= threshold
    ][:limit]
    return documents, threshold


# +18% on the default (non-expand) cap so the last sentence can finish.
_DEFAULT_TOKEN_HEADROOM = 1.18
_EXPAND_TOKEN_FLOOR = 4096


def _generation_parameters(*, expand: bool = False) -> dict[str, Any]:
    """Sampling params. Cloud DeepSeek keeps a high ceiling so answers are not cut."""
    try:
        settings = get_model_settings(PROFILE)
        parameters: dict[str, Any] = {
            "temperature": float(settings.temperature),
            "top_p": float(settings.top_p),
            "max_tokens": int(settings.max_tokens),
        }
    except Exception:
        parameters = {"max_tokens": 2048}

    raw_cap = os.environ.get("ASSISTANT_MAX_TOKENS") or os.environ.get(
        "LLM_MAX_TOKENS"
    )
    if raw_cap:
        try:
            parameters["max_tokens"] = max(32, int(raw_cap))
        except ValueError:
            pass
    else:
        current = int(parameters.get("max_tokens") or 2048)
        try:
            from assistant.local_llm import is_deepseek_assistant

            cloud = is_deepseek_assistant()
        except Exception:
            cloud = False
        if cloud:
            parameters["max_tokens"] = max(current, 4096)
        else:
            parameters["max_tokens"] = max(current, 1024)
    base = int(parameters.get("max_tokens") or 2048)
    if expand:
        parameters["max_tokens"] = max(base, _EXPAND_TOKEN_FLOOR)
    elif base < _EXPAND_TOKEN_FLOOR:
        parameters["max_tokens"] = max(32, int(round(base * _DEFAULT_TOKEN_HEADROOM)))
    return parameters


def iter_chat_sse(
    messages: Sequence[Mapping[str, str]],
    *,
    kb_slugs: Sequence[str] | None = None,
    gateway: ModelGateway | None = None,
    request_id: str | None = None,
    expand: bool = False,
) -> Iterator[str]:
    """Yield OpenAI-compatible SSE frames from ``assistant_bank`` with RAG."""
    active = gateway or ModelGateway.from_registry()
    parameters = _generation_parameters(expand=expand)

    if request_id:
        yield f": request_id {request_id}\n\n"

    # Immediate SSE frame so proxies/UI know the stream is alive while we embed.
    yield (
        "data: "
        + json.dumps(
            {
                "status": "retrieving",
                "choices": [{"index": 0, "delta": {}, "finish_reason": None}],
            },
            ensure_ascii=False,
        )
        + "\n\n"
    )

    documents: list[dict[str, Any]] = []
    attachment_mode = has_attachment_marker(messages)
    try:
        if not attachment_mode:
            documents, _threshold = retrieve_assistant_context(
                messages,
                kb_slugs=kb_slugs,
            )
    except Exception:
        documents = []

    sources = [_citation(document) for document in documents]
    yield (
        "data: "
        + json.dumps(
            {
                "status": "generating",
                "sources": sources,
                "choices": [{"index": 0, "delta": {}, "finish_reason": None}],
            },
            ensure_ascii=False,
        )
        + "\n\n"
    )

    outbound = (
        _inject_rag_context(messages, documents, expand=expand)
        if documents
        else list(messages)
    )
    if not documents:
        if attachment_mode:
            empty_system = (
                "Ты внутренний ИИ-ассистент банка. Пользователь загрузил "
                "документ. "
                + (
                    "Сделай полное резюме по фрагментам вложения. "
                    if wants_summary(_last_user_text(messages))
                    else "Ответь на вопрос только по фрагментам вложения. "
                )
                + "Заканчивай законченным предложением и законченной мыслью. "
                + _ANSWER_STYLE
            )
        else:
            empty_system = (
                (EXPAND_SYSTEM_PROMPT if expand else DEFAULT_SYSTEM_PROMPT)
                + " В выбранных базах знаний релевантных фрагментов "
                "не найдено — сообщи об этом пользователю."
            )
        outbound = [
            {
                "role": "system",
                "content": empty_system,
            },
            *[
                {"role": item["role"], "content": item["content"]}
                for item in outbound
                if item.get("role") != "system"
            ],
        ]

    try:
        yield from active.stream(PROFILE, outbound, **parameters)
    except ModelGatewayConfigurationError as exc:
        raise AssistantChatError(str(exc)) from exc
    except Exception as exc:
        # Surface gateway/network errors into the SSE so the UI stops spinning.
        err = str(exc) or exc.__class__.__name__
        yield (
            "data: "
            + json.dumps(
                {
                    "error": "llm_error",
                    "details": err,
                    "choices": [
                        {
                            "index": 0,
                            "delta": {
                                "content": (
                                    "Не удалось получить ответ от модели: "
                                    f"{err}"
                                )
                            },
                            "finish_reason": "stop",
                        }
                    ],
                },
                ensure_ascii=False,
            )
            + "\n\n"
        )
        yield "data: [DONE]\n\n"
