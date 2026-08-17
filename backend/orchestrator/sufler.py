"""Sufler CC pipeline: text → QU → RAG → ModelGateway(sufler_cc) → citations.

Implements FR-CC-03 (LLM hints from ``cc_production``) and FR-CC-14
(operator-visible source title + permalink). Stage latency is logged for
FR-CC / KPI budgets.
"""

from __future__ import annotations

import logging
import os
import re
import time
import uuid
from typing import Any, Mapping, Sequence

from core.model_gateway import ModelGateway
from hub.model_registry_store import get_model_settings
from qu.service import (
    ignored_suz_fixtures_exist,
    is_suz_transfer_commission_doc,
    preview_query,
)

logger = logging.getLogger(__name__)

PROFILE = "sufler_cc"
KB_ID = "cc_production"
DEFAULT_HINT_LIMIT = 3
MAX_HINT_LIMIT = 5
# Operator-facing floor: never show hints below 20% relevance.
OPERATOR_MIN_RELEVANCE = 0.20
# Prefer a second hint when it is reasonably close to the best match.
SECOND_HINT_RELATIVE_FLOOR = 0.55

SYSTEM_PROMPT = (
    "Ты суфлёр оператора контакт-центра Беларусбанка. "
    "Отвечай ТОЛЬКО на основе переданных фрагментов СУЗ и контекста переписки. "
    "Не выдумывай факты, цифры и условия.\n"
    "Учитывай весь диалог: уточнения клиента (тип карты, продукт и т.п.) "
    "должны влиять на формулировку ответа.\n"
    "Формат ответа СТРОГО (без markdown, без звёздочек *, без жирного):\n"
    "ОТВЕТ:\n"
    "<готовый текст ответа клиенту в изъявительном наклонении; "
    "2–5 предложений. ЗАПРЕЩЕНО писать вопросы, в том числе риторические. "
    "Не копируй вопросы из статьи. Без «Уважаемый клиент» и без вводных фраз>\n"
    "СОВЕТ:\n"
    "<одна короткая ремарка оператору только если нужна; иначе оставь пустым>\n"
    "Не пиши заголовки вроде «Подсказка оператору» или «Ответ клиенту». "
    "Не пересказывай историю обращений и не цитируй реплики диалога дословно."
)


class SuflerOrchestratorError(ValueError):
    """Raised when suggest input or pipeline configuration is invalid."""


def _elapsed_ms(started: float) -> float:
    return round((time.perf_counter() - started) * 1000, 3)


def _citation(document: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "article_id": document["article_id"],
        "chunk_index": document["chunk_index"],
        "title": document["title"],
        "permalink": document["permalink"],
    }


def _strip_markup(text: str) -> str:
    cleaned = (text or "").strip()
    cleaned = cleaned.replace("**", "").replace("__", "")
    cleaned = re.sub(r"[*_`]+", "", cleaned)
    cleaned = re.sub(
        r"^\s*(подсказка оператору|ответ клиенту|совет оператору)\s*:?\s*",
        "",
        cleaned,
        flags=re.IGNORECASE | re.MULTILINE,
    )
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def _parse_llm_hint(raw: str) -> tuple[str, str]:
    """Return (client_answer, optional_operator_tip)."""
    text = _strip_markup(raw)
    if not text:
        return "", ""
    answer = text
    tip = ""
    answer_match = re.search(
        r"ответ\s*:\s*(.*?)(?:\n\s*совет\s*:|$)",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    tip_match = re.search(
        r"совет\s*:\s*(.*)$",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if answer_match:
        answer = answer_match.group(1).strip()
    if tip_match:
        tip = tip_match.group(1).strip()
        tip_lower = tip.casefold()
        if tip_lower in {"", "-", "нет", "не нужен", "не требуется", "пусто"}:
            tip = ""
    if not answer_match:
        answer = re.sub(
            r"(?is)^\s*совет\s*:.*$",
            "",
            answer,
        ).strip()
    return _strip_markup(answer), _strip_markup(tip)


def _clean_answer_text(text: str) -> str:
    """Keep only declarative sentences suitable to paste to the client."""
    cleaned = _strip_markup(text)
    if not cleaned:
        return ""
    sentences = re.split(r"(?<=[.!?…])\s+", cleaned)
    kept: list[str] = []
    for sentence in sentences:
        piece = sentence.strip()
        if not piece:
            continue
        # Drop interrogatives and seed "title. Question?" prefixes.
        if "?" in piece:
            continue
        if re.match(
            r"^(какой|какая|какие|как|где|когда|зачем|почему|что|сколько)\b",
            piece,
            flags=re.IGNORECASE,
        ):
            continue
        kept.append(piece)
    result = " ".join(kept).strip()
    return result or cleaned


def _snippet_as_answer(document: Mapping[str, Any]) -> str:
    snippet = _strip_markup(str(document.get("snippet") or document.get("content") or ""))
    return _clean_answer_text(snippet)


def _retrieval_query(text: str, dialog_context: str = "") -> str:
    """Build RAG query from latest client line + recent dialog turns."""
    latest = (text or "").strip()
    context = (dialog_context or "").strip()
    if not context:
        return latest
    # Keep the latest utterance first for lexical overlap, then prior turns.
    combined = f"{latest}\n{context}"
    return combined[:1200].strip()


def _select_documents(
    documents: Sequence[Mapping[str, Any]],
    *,
    limit: int,
    context_threshold: float,
) -> list[Mapping[str, Any]]:
    """Return 1…limit docs, never below OPERATOR_MIN_RELEVANCE (20%)."""
    pool = [
        document
        for document in documents
        if not is_suz_transfer_commission_doc(document)
    ]
    if not pool:
        return []
    floor = max(float(context_threshold), OPERATOR_MIN_RELEVANCE)
    ranked = [
        document
        for document in pool
        if float(document["relevance_score"]) > OPERATOR_MIN_RELEVANCE
        and float(document["relevance_score"]) >= floor
    ]
    # Soft floor: still allow docs above 20% even if below registry threshold.
    if not ranked:
        ranked = [
            document
            for document in pool
            if float(document["relevance_score"]) > OPERATOR_MIN_RELEVANCE
        ]
    if not ranked:
        return []
    selected: list[Mapping[str, Any]] = [ranked[0]]
    if limit >= 2:
        best = float(ranked[0]["relevance_score"])
        second_floor = max(
            OPERATOR_MIN_RELEVANCE + 0.01,
            best * SECOND_HINT_RELATIVE_FLOOR,
        )
        for document in ranked[1:]:
            if document["article_id"] == selected[0]["article_id"]:
                continue
            if float(document["relevance_score"]) >= second_floor:
                selected.append(document)
                break
    return selected[:limit]


def _allow_ungrounded() -> bool:
    return os.getenv("SUFLER_ALLOW_UNGROUNDED", "").strip().lower() in {
        "1",
        "true",
        "yes",
    }


def _build_messages(
    query: str,
    documents: Sequence[Mapping[str, Any]],
    *,
    client_history: str = "",
    dialog_context: str = "",
) -> list[dict[str, str]]:
    context_blocks = []
    for document in documents:
        context_blocks.append(
            f"[{document['rank']}] {document['title']}\n"
            f"URL: {document['permalink']}\n"
            f"{document['snippet']}"
        )
    context = "\n\n".join(context_blocks)
    history_block = ""
    cleaned_history = client_history.strip() if isinstance(client_history, str) else ""
    if cleaned_history:
        history_block = (
            "Служебный контекст прошлых обращений "
            "(не включать в текст ответа клиенту):\n"
            f"{cleaned_history[:800]}\n\n"
        )
    dialog_block = ""
    cleaned_dialog = dialog_context.strip() if isinstance(dialog_context, str) else ""
    if cleaned_dialog:
        dialog_block = (
            "Текущая переписка (учитывай уточнения клиента):\n"
            f"{cleaned_dialog[:2000]}\n\n"
        )
    if not documents:
        user_content = (
            f"{history_block}"
            f"{dialog_block}"
            f"Последняя реплика клиента:\n{query}\n\n"
            "Фрагменты СУЗ сейчас недоступны. Сформируй краткий ответ оператору "
            "по общим правилам розничного банка. В СОВЕТЕ напиши, что формулировку "
            "нужно сверить со статьёй СУЗ перед озвучиванием.\n"
            "Сформируй ответ по шаблону ОТВЕТ:/СОВЕТ:."
        )
        return [
            {
                "role": "system",
                "content": (
                    SYSTEM_PROMPT
                    + "\nЕсли фрагменты СУЗ не переданы, всё равно заполни ОТВЕТ "
                    "осторожной формулировкой и укажи в СОВЕТЕ сверку с СУЗ."
                ),
            },
            {"role": "user", "content": user_content},
        ]
    primary = documents[0]
    user_content = (
        f"{history_block}"
        f"{dialog_block}"
        f"Последняя реплика клиента:\n{query}\n\n"
        f"Основная статья для ответа: [{primary['rank']}] {primary['title']}\n\n"
        f"Фрагменты базы знаний СУЗ ({KB_ID}):\n{context}\n\n"
        "Сформируй ответ по шаблону ОТВЕТ:/СОВЕТ: с учётом переписки. "
        "Если клиент уточнил детали (например, тип карты) — отрази это в ОТВЕТЕ."
    )
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]


def _extract_llm_text(response: Mapping[str, Any]) -> str:
    try:
        choices = response["choices"]
        message = choices[0]["message"]
        content = message["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise SuflerOrchestratorError(
            "ModelGateway returned an unexpected response shape"
        ) from exc
    if not isinstance(content, str) or not content.strip():
        raise SuflerOrchestratorError("ModelGateway returned empty content")
    return content.strip()


def _log_latency(
    *,
    request_id: str,
    latency_ms: Mapping[str, float],
    hint_count: int,
    document_count: int,
) -> None:
    logger.info(
        "sufler_suggest_latency request_id=%s profile=%s kb_id=%s "
        "qu_ms=%.3f rag_ms=%.3f llm_ms=%.3f total_ms=%.3f "
        "documents=%s hints=%s",
        request_id,
        PROFILE,
        KB_ID,
        latency_ms["qu"],
        latency_ms["rag"],
        latency_ms["llm"],
        latency_ms["total"],
        document_count,
        hint_count,
    )


def suggest(
    text: str,
    *,
    limit: int = DEFAULT_HINT_LIMIT,
    gateway: ModelGateway | None = None,
    request_id: str | None = None,
    client_history: str = "",
    dialog_context: str = "",
) -> dict[str, Any]:
    """Run text → QU → RAG → ModelGateway(sufler_cc) → citations."""
    normalized = text.strip() if isinstance(text, str) else ""
    if not normalized:
        raise SuflerOrchestratorError("text must be a non-empty string")
    if isinstance(limit, bool) or not isinstance(limit, int):
        raise SuflerOrchestratorError("limit must be an integer")
    if not 1 <= limit <= MAX_HINT_LIMIT:
        raise SuflerOrchestratorError(
            f"limit must be between 1 and {MAX_HINT_LIMIT}"
        )

    correlation_id = request_id or str(uuid.uuid4())
    total_started = time.perf_counter()
    latency_ms = {"qu": 0.0, "rag": 0.0, "llm": 0.0, "total": 0.0}
    retrieval_text = _retrieval_query(normalized, dialog_context)

    qu_started = time.perf_counter()
    try:
        qu_result = preview_query(retrieval_text, limit=max(limit, 5))
    except Exception:
        logger.exception(
            "sufler_qu_failed request_id=%s",
            correlation_id,
        )
        qu_result = {"documents": []}
    latency_ms["qu"] = _elapsed_ms(qu_started)

    rag_started = time.perf_counter()
    settings = get_model_settings(PROFILE)
    context_threshold = float(settings.context_inclusion_threshold)

    documents = _select_documents(
        qu_result["documents"],
        limit=limit,
        context_threshold=context_threshold,
    )
    latency_ms["rag"] = _elapsed_ms(rag_started)

    if not documents:
        # Empty index or nothing above 20% relevance.
        empty_reason = (
            "sufler_unavailable"
            if not qu_result["documents"]
            else "no_relevant_knowledge"
        )
        if not _allow_ungrounded() and not ignored_suz_fixtures_exist():
            latency_ms["total"] = _elapsed_ms(total_started)
            _log_latency(
                request_id=correlation_id,
                latency_ms=latency_ms,
                hint_count=0,
                document_count=0,
            )
            return {
                "query": normalized,
                "profile": PROFILE,
                "kb_id": KB_ID,
                "hints": [],
                "citations_enabled": True,
                "blocked_reason": empty_reason,
                "min_relevance": OPERATOR_MIN_RELEVANCE,
                "latency_ms": latency_ms,
                "request_id": correlation_id,
            }
        documents = []
        ungrounded = True
    else:
        ungrounded = False

    llm_started = time.perf_counter()
    active_gateway = gateway or ModelGateway.from_registry()
    try:
        llm_response = active_gateway.chat(
            PROFILE,
            _build_messages(
                normalized,
                documents,
                client_history=client_history,
                dialog_context=dialog_context,
            ),
            temperature=float(settings.temperature),
            top_p=float(settings.top_p),
            max_tokens=int(settings.max_tokens),
        )
        llm_text = _extract_llm_text(llm_response)
        if len(llm_text) > int(settings.response_chars_max):
            llm_text = llm_text[: int(settings.response_chars_max)].rstrip()
        answer_text, operator_tip = _parse_llm_hint(llm_text)
        answer_text = _clean_answer_text(answer_text)
    except Exception:  # noqa: BLE001 — fall back to KB snippets
        logger.exception("sufler_llm_failed request_id=%s", correlation_id)
        answer_text, operator_tip = "", ""
        latency_ms["llm"] = _elapsed_ms(llm_started)
    else:
        latency_ms["llm"] = _elapsed_ms(llm_started)

    if not answer_text:
        if documents:
            answer_text = _snippet_as_answer(documents[0])
        elif ungrounded:
            answer_text = ""

    hints: list[dict[str, Any]] = []
    for index, document in enumerate(documents):
        if float(document["relevance_score"]) <= OPERATOR_MIN_RELEVANCE:
            continue
        if index == 0:
            hint_text = answer_text
            tip = operator_tip
        else:
            hint_text = _snippet_as_answer(document)
            tip = ""
        if not hint_text:
            continue
        hints.append(
            {
                "rank": len(hints) + 1,
                "text": hint_text,
                "operator_tip": tip,
                "relevance_score": document["relevance_score"],
                "relevance_percent": document["relevance_percent"],
                "citations": [_citation(document)],
            }
        )
    if ungrounded and answer_text and not hints:
        hints.append(
            {
                "rank": 1,
                "text": answer_text,
                "operator_tip": operator_tip,
                "relevance_score": 0.5,
                "relevance_percent": 50,
                "citations": [],
            }
        )
    if not hints:
        latency_ms["total"] = _elapsed_ms(total_started)
        _log_latency(
            request_id=correlation_id,
            latency_ms=latency_ms,
            hint_count=0,
            document_count=len(documents),
        )
        return {
            "query": normalized,
            "profile": PROFILE,
            "kb_id": KB_ID,
            "hints": [],
            "citations_enabled": True,
            "blocked_reason": "no_relevant_knowledge",
            "min_relevance": OPERATOR_MIN_RELEVANCE,
            "latency_ms": latency_ms,
            "request_id": correlation_id,
        }

    latency_ms["total"] = _elapsed_ms(total_started)
    _log_latency(
        request_id=correlation_id,
        latency_ms=latency_ms,
        hint_count=len(hints),
        document_count=len(documents),
    )
    return {
        "query": normalized,
        "profile": PROFILE,
        "kb_id": KB_ID,
        "hints": hints,
        "citations_enabled": True,
        "blocked_reason": None,
        "min_relevance": OPERATOR_MIN_RELEVANCE,
        "latency_ms": latency_ms,
        "request_id": correlation_id,
        "gateway_model": active_gateway.get_profile(PROFILE).model,
    }
