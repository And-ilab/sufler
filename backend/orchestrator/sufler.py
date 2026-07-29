"""Sufler CC pipeline: text → QU → RAG → ModelGateway(sufler_cc) → citations.

Implements FR-CC-03 (LLM hints from ``cc_production``) and FR-CC-14
(operator-visible source title + permalink). Stage latency is logged for
FR-CC / KPI budgets.
"""

from __future__ import annotations

import logging
import time
import uuid
from typing import Any, Mapping, Sequence

from core.model_gateway import ModelGateway
from hub.model_registry_store import get_model_settings
from qu.service import preview_query

logger = logging.getLogger(__name__)

PROFILE = "sufler_cc"
KB_ID = "cc_production"
DEFAULT_HINT_LIMIT = 5
MAX_HINT_LIMIT = 5
SYSTEM_PROMPT = (
    "Ты суфлёр оператора контакт-центра. Отвечай только на основе "
    "переданных фрагментов СУЗ. Текст предназначен оператору, не клиенту. "
    "Кратко, по-деловому, без выдуманных фактов."
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


def _build_messages(
    query: str,
    documents: Sequence[Mapping[str, Any]],
) -> list[dict[str, str]]:
    context_blocks = []
    for document in documents:
        context_blocks.append(
            f"[{document['rank']}] {document['title']}\n"
            f"URL: {document['permalink']}\n"
            f"{document['snippet']}"
        )
    context = "\n\n".join(context_blocks)
    user_content = (
        f"Реплика клиента:\n{query}\n\n"
        f"Фрагменты базы знаний СУЗ ({KB_ID}):\n{context}\n\n"
        "Сформируй подсказку оператору."
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

    qu_started = time.perf_counter()
    qu_result = preview_query(normalized, limit=limit)
    latency_ms["qu"] = _elapsed_ms(qu_started)

    rag_started = time.perf_counter()
    settings = get_model_settings(PROFILE)
    context_threshold = float(settings.context_inclusion_threshold)

    documents = [
        document
        for document in qu_result["documents"]
        if float(document["relevance_score"]) >= context_threshold
    ][:limit]
    latency_ms["rag"] = _elapsed_ms(rag_started)

    if not documents:
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
            "blocked_reason": "no_relevant_knowledge",
            "min_relevance": context_threshold,
            "latency_ms": latency_ms,
            "request_id": correlation_id,
        }

    llm_started = time.perf_counter()
    active_gateway = gateway or ModelGateway.from_registry()
    llm_response = active_gateway.chat(
        PROFILE,
        _build_messages(normalized, documents),
        temperature=float(settings.temperature),
        top_p=float(settings.top_p),
        max_tokens=int(settings.max_tokens),
    )
    llm_text = _extract_llm_text(llm_response)
    if len(llm_text) > int(settings.response_chars_max):
        llm_text = llm_text[: int(settings.response_chars_max)].rstrip()
    latency_ms["llm"] = _elapsed_ms(llm_started)

    citations = [_citation(document) for document in documents]
    hints: list[dict[str, Any]] = []
    for index, document in enumerate(documents):
        hint_text = llm_text if index == 0 else document["snippet"]
        hints.append(
            {
                "rank": index + 1,
                "text": hint_text,
                "relevance_score": document["relevance_score"],
                "relevance_percent": document["relevance_percent"],
                "citations": (
                    citations if index == 0 else [_citation(document)]
                ),
            }
        )

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
        "min_relevance": context_threshold,
        "latency_ms": latency_ms,
        "request_id": correlation_id,
        "gateway_model": active_gateway.get_profile(PROFILE).model,
    }
