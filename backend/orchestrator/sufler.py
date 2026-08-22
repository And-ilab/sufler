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
from core.text_language import safe_ru_en_text
from hub.model_registry_store import get_model_settings
from hub.models import SuflerPolicy
from hub.sufler_policy import get_sufler_policy
from orchestrator.scenario_engine import (
    NO_HINT_REASON,
    ScenarioProgress,
    advance_scenario,
    classify_turn,
)
from qu.service import (
    _tokens,
    complete_sentences,
    extractive_answer,
    focused_snippet,
    ignored_suz_fixtures_exist,
    is_suz_transfer_commission_doc,
    preview_query,
)

logger = logging.getLogger(__name__)

PROFILE = "sufler_cc"
KB_ID = "cc_production"
DEFAULT_HINT_LIMIT = 1
MAX_HINT_LIMIT = 5
# Fallback if policy row is missing: never show hints below 20% relevance.
OPERATOR_MIN_RELEVANCE = 0.20
# Prefer a second hint when it is reasonably close to the best match.
SECOND_HINT_RELATIVE_FLOOR = 0.55

SYSTEM_PROMPT = (
    "Ты суфлёр оператора контакт-центра Беларусбанка. "
    "Пиши ТОЛЬКО на грамотном русском или английском языке. "
    "По умолчанию отвечай по-русски; английский используй только когда он "
    "нужен клиенту. Запрещены китайские иероглифы и любые другие алфавиты, "
    "транслит, смесь языков, опечатки и грамматические ошибки. "
    "Отвечай СТРОГО на основе переданных фрагментов базы знаний. "
    "Не выдумывай факты, цифры, тарифы, сроки и условия, которых нет во фрагментах.\n"
    "Если во фрагментах есть точная цифра или срок — обязательно включи её в ОТВЕТ целиком.\n"
    "Учитывай весь диалог: уточнения клиента (тип карты, продукт и т.п.) "
    "должны влиять на формулировку ответа.\n"
    "Формат ответа СТРОГО (без markdown, без звёздочек *, без жирного):\n"
    "ОТВЕТ:\n"
    "<готовый текст ответа клиенту в изъявительном наклонении; "
    "2–5 законченных предложений, без обрыва на полуслове. ЗАПРЕЩЕНО писать вопросы, в том числе риторические. "
    "Не копируй вопросы из статьи. Без «Уважаемый клиент» и без вводных фраз>\n"
    "СОВЕТ:\n"
    "<одна короткая ремарка оператору только если нужна; иначе оставь пустым>\n"
    "Не пиши заголовки вроде «Подсказка оператору» или «Ответ клиенту». "
    "Не пересказывай историю обращений и не цитируй реплики диалога дословно."
)


class SuflerOrchestratorError(ValueError):
    """Raised when suggest input or pipeline configuration is invalid."""


def _policy_settings() -> SuflerPolicy:
    try:
        return get_sufler_policy()
    except Exception:  # noqa: BLE001 — suggest must not fail if admin table is empty
        logger.exception("sufler_policy_load_failed")
        return SuflerPolicy(
            telephony_min_relevance_percent=20,
            clarify_min_relevance_percent=15,
            max_hints=DEFAULT_HINT_LIMIT,
            default_mode=SuflerPolicy.MODE_CONSULTATION,
        )


def _normalize_channel(channel: str) -> str:
    key = (channel or "").strip().lower()
    if key in {"online_chat", "chat", "widget"}:
        return "online_chat"
    return "telephony"


def _normalize_mode(mode: str, *, default: str) -> str:
    key = (mode or "").strip().lower()
    if key in {SuflerPolicy.MODE_SERVICE, "usluga"}:
        return SuflerPolicy.MODE_SERVICE
    if key in {SuflerPolicy.MODE_CONSULTATION, "consult"}:
        return SuflerPolicy.MODE_CONSULTATION
    return default or SuflerPolicy.MODE_CONSULTATION


def _elapsed_ms(started: float) -> float:
    return round((time.perf_counter() - started) * 1000, 3)


def _citation(document: Mapping[str, Any]) -> dict[str, Any]:
    title = _safe_ru_en_text(str(document.get("title") or ""))
    return {
        "article_id": document["article_id"],
        "chunk_index": document["chunk_index"],
        "title": title or "Документ базы знаний",
        "permalink": document["permalink"],
    }


def _safe_ru_en_text(text: str) -> str:
    return safe_ru_en_text(text)


def _document_is_ru_en(document: Mapping[str, Any]) -> bool:
    title = str(document.get("title") or "")
    body = str(document.get("content") or document.get("snippet") or "")
    return bool(_safe_ru_en_text(title)) and bool(_safe_ru_en_text(body))


def _strip_markup(text: str) -> str:
    cleaned = _safe_ru_en_text(text)
    if not cleaned:
        return ""
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


def _snippet_as_answer(document: Mapping[str, Any], query: str = "") -> str:
    raw = str(document.get("content") or document.get("snippet") or "")
    if not _safe_ru_en_text(raw):
        return ""
    extracted = extractive_answer(raw, query or str(document.get("title") or ""))
    return _clean_answer_text(extracted)


def _llm_misses_source(answer: str, document: Mapping[str, Any]) -> bool:
    source_tokens = _tokens(str(document.get("content") or document.get("snippet") or ""))
    answer_tokens = _tokens(answer)
    if not source_tokens or not answer_tokens:
        return True
    return len(source_tokens & answer_tokens) < 2


_GENERIC_QUERY_TOKENS = {
    "банк",
    "бела",
    "беларус",
    "беларусбанк",
    "вопрос",
    "клиент",
    "надо",
    "нужн",
    "опера",
    "пожал",
    "подскаж",
    "хочу",
}


def _query_specific_tokens(query: str) -> set[str]:
    return {
        token
        for token in _tokens(query)
        if len(token) >= 4 and token not in _GENERIC_QUERY_TOKENS
    }


def _document_supports_query(document: Mapping[str, Any], query: str) -> bool:
    """Require lexical evidence before attributing an answer to a KB file."""
    query_tokens = _query_specific_tokens(query)
    if not query_tokens:
        return False
    source_tokens = _tokens(
        f"{document.get('title') or ''}\n"
        f"{document.get('content') or document.get('snippet') or ''}"
    )
    return bool(query_tokens & source_tokens)


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
    allow_weak: bool = False,
    query: str = "",
    min_relevance: float = OPERATOR_MIN_RELEVANCE,
) -> list[Mapping[str, Any]]:
    """Return 1…limit docs above the operator relevance floor from policy."""
    floor_score = max(float(min_relevance), 0.0)
    pool = [
        document
        for document in documents
        if not is_suz_transfer_commission_doc(document)
        and _document_is_ru_en(document)
    ]
    if not pool:
        return []
    floor = max(float(context_threshold), floor_score)
    ranked = [
        document
        for document in pool
        if float(document["relevance_score"]) >= floor_score
        and float(document["relevance_score"]) >= floor
    ]
    # Soft floor: still allow docs at/above the policy threshold even if below RAG.
    if not ranked:
        ranked = [
            document
            for document in pool
            if float(document["relevance_score"]) >= floor_score
        ]
    if not ranked and allow_weak:
        ranked = sorted(
            pool,
            key=lambda document: -float(document["relevance_score"]),
        )[:limit]
    if not ranked:
        return []
    ranked = _merge_article_chunks(ranked, query=query)
    selected: list[Mapping[str, Any]] = [ranked[0]]
    if limit >= 2:
        best = float(ranked[0]["relevance_score"])
        second_floor = max(
            0.0 if allow_weak else floor_score + 0.01,
            best * SECOND_HINT_RELATIVE_FLOOR,
        )
        selected_ids = {selected[0]["article_id"]}
        for document in ranked[1:]:
            if document["article_id"] in selected_ids:
                continue
            if float(document["relevance_score"]) >= second_floor:
                selected.append(document)
                selected_ids.add(document["article_id"])
            if len(selected) >= limit:
                break
    return selected[:limit]


def _sufler_llm_configured() -> bool:
    if (os.getenv("SUFLER_LLM_BASE_URL") or "").strip():
        return True
    openai = (os.getenv("OPENAI_BASE_URL") or "").strip()
    return bool(openai)


def _allow_ungrounded() -> bool:
    flag = os.getenv("SUFLER_ALLOW_UNGROUNDED", "").strip().lower()
    if flag in {"1", "true", "yes"}:
        return True
    if flag in {"0", "false", "no"}:
        return False
    return _sufler_llm_configured()


def _document_body(document: Mapping[str, Any]) -> str:
    raw = str(document.get("content") or document.get("snippet") or "")
    if not _safe_ru_en_text(raw):
        return ""
    return complete_sentences(_strip_markup(raw), max_chars=6000)


def _merge_article_chunks(
    documents: Sequence[Mapping[str, Any]],
    *,
    query: str = "",
) -> list[dict[str, Any]]:
    """Join chunks of one file so the LLM sees the answering clause, not only the header."""
    merged: dict[int, dict[str, Any]] = {}
    order: list[int] = []
    for document in documents:
        article_id = int(document["article_id"])
        body = str(document.get("content") or document.get("snippet") or "").strip()
        if article_id not in merged:
            order.append(article_id)
            item = dict(document)
            item["content"] = body
            merged[article_id] = item
            continue
        current = merged[article_id]
        if body and body not in current["content"]:
            current["content"] = f"{current['content']}\n{body}".strip()
        current["relevance_score"] = max(
            float(current["relevance_score"]),
            float(document["relevance_score"]),
        )
        current["relevance_percent"] = round(float(current["relevance_score"]) * 100)
        if int(document.get("chunk_index") or 0) < int(current.get("chunk_index") or 0):
            current["chunk_index"] = document["chunk_index"]
    result: list[dict[str, Any]] = []
    for article_id in order:
        item = merged[article_id]
        item["snippet"] = focused_snippet(item["content"], query, 1200)
        result.append(item)
    return result


def _build_messages(
    query: str,
    documents: Sequence[Mapping[str, Any]],
    *,
    client_history: str = "",
    dialog_context: str = "",
    kb_label: str = KB_ID,
) -> list[dict[str, str]]:
    context_blocks = []
    for document in documents:
        context_blocks.append(
            f"[{document['rank']}] {document['title']}\n"
            f"URL: {document['permalink']}\n"
            f"{_document_body(document)}"
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
            "Фрагменты базы знаний сейчас недоступны. Сформируй краткий ответ оператору "
            "по общим правилам розничного банка. В СОВЕТЕ напиши, что формулировку "
            "нужно сверить со статьёй базы знаний перед озвучиванием.\n"
            "Сформируй ответ по шаблону ОТВЕТ:/СОВЕТ:."
        )
        return [
            {
                "role": "system",
                "content": (
                    SYSTEM_PROMPT
                    + "\nЕсли фрагменты базы знаний не переданы, всё равно заполни ОТВЕТ "
                    "осторожной формулировкой и укажи в СОВЕТЕ сверку с базой знаний."
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
        f"Фрагменты выбранных баз знаний ({kb_label}):\n{context}\n\n"
        "Сформируй ответ по шаблону ОТВЕТ:/СОВЕТ: строго по этим фрагментам. "
        "Если клиент уточнил детали (например, тип карты) — отрази это в ОТВЕТЕ. "
        "Пиши естественно и грамотно по-русски."
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


def _normalize_kb_slugs(kb_slugs: Sequence[str] | None) -> list[str] | None:
    if kb_slugs is None:
        return None
    return [
        slug.strip()
        for slug in kb_slugs
        if isinstance(slug, str) and slug.strip()
    ]


def _retrieve_documents(
    retrieval_text: str,
    *,
    limit: int,
    kb_slugs: list[str] | None,
) -> tuple[dict[str, Any], str]:
    """Return QU result and kb label. Selected slugs search the same catalog as AI chat."""
    if kb_slugs is None:
        result = preview_query(retrieval_text, limit=max(limit, 5), snippet_chars=2000)
        return result, KB_ID
    if not kb_slugs:
        return {"documents": []}, "none"
    from qu.assistant_retrieval import preview_assistant_query

    result = preview_assistant_query(
        retrieval_text,
        kb_slugs=kb_slugs,
        limit=max(limit, 5),
    )
    return result, ",".join(kb_slugs)


def _scenario_payload(progress: ScenarioProgress | None) -> dict[str, Any] | None:
    if progress is None:
        return None
    payload = progress.as_dict()
    payload["title"] = _safe_ru_en_text(str(payload.get("title") or ""))
    payload["path"] = [
        safe
        for item in payload.get("path") or []
        if (safe := _safe_ru_en_text(str(item)))
    ]
    payload["next_clarify"] = _safe_ru_en_text(
        str(payload.get("next_clarify") or "")
    )
    return payload


def suggest(
    text: str,
    *,
    limit: int = DEFAULT_HINT_LIMIT,
    gateway: ModelGateway | None = None,
    request_id: str | None = None,
    client_history: str = "",
    dialog_context: str = "",
    kb_slugs: Sequence[str] | None = None,
    channel: str = "",
    mode: str = "",
    session_id: str = "",
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

    policy = _policy_settings()
    channel_key = _normalize_channel(channel)
    resolved_mode = _normalize_mode(mode, default=policy.default_mode)
    min_relevance = float(policy.min_relevance_for_channel(channel_key))
    limit = min(limit, max(1, int(policy.max_hints)))

    correlation_id = request_id or str(uuid.uuid4())
    total_started = time.perf_counter()
    latency_ms = {"qu": 0.0, "rag": 0.0, "llm": 0.0, "total": 0.0}
    retrieval_text = _retrieval_query(normalized, dialog_context)
    selected_slugs = _normalize_kb_slugs(kb_slugs)
    grounded_only = selected_slugs is not None
    kb_label = KB_ID

    if resolved_mode == SuflerPolicy.MODE_SERVICE:
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
            "kb_id": kb_label,
            "kb_slugs": selected_slugs or [],
            "hints": [],
            "citations_enabled": True,
            "blocked_reason": "service_mode",
            "min_relevance": min_relevance,
            "latency_ms": latency_ms,
            "request_id": correlation_id,
            "scenario": None,
        }

    progress: ScenarioProgress | None = None
    try:
        progress = advance_scenario(
            normalized,
            session_key=session_id,
            channel=channel_key,
        )
    except Exception:  # noqa: BLE001 — scenario must never break suggest
        logger.exception("sufler_scenario_failed request_id=%s", correlation_id)
        progress = None

    if progress is None and classify_turn(normalized):
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
            "kb_id": kb_label,
            "kb_slugs": selected_slugs or [],
            "hints": [],
            "citations_enabled": True,
            "blocked_reason": NO_HINT_REASON,
            "min_relevance": min_relevance,
            "latency_ms": latency_ms,
            "request_id": correlation_id,
            "scenario": None,
        }

    scenario_hint = (
        _safe_ru_en_text(progress.hint_text) if progress is not None else ""
    )
    scenario_tip = (
        _safe_ru_en_text(progress.next_clarify) if progress is not None else ""
    )
    if progress and scenario_hint:
        latency_ms["total"] = _elapsed_ms(total_started)
        _log_latency(
            request_id=correlation_id,
            latency_ms=latency_ms,
            hint_count=1,
            document_count=0,
        )
        return {
            "query": normalized,
            "profile": PROFILE,
            "kb_id": kb_label,
            "kb_slugs": selected_slugs or [],
            "hints": [
                {
                    "rank": 1,
                    "text": scenario_hint,
                    "operator_tip": scenario_tip,
                    "source_type": "scenario",
                    "relevance_score": 0.95,
                    "relevance_percent": 95,
                    "citations": [
                        {
                            "article_id": 0,
                            "chunk_index": 0,
                            "title": _safe_ru_en_text(progress.title)
                            or "Сценарий контакт-центра",
                            "permalink": "",
                        }
                    ],
                }
            ],
            "citations_enabled": True,
            "blocked_reason": None,
            "min_relevance": min_relevance,
            "latency_ms": latency_ms,
            "request_id": correlation_id,
            "scenario": _scenario_payload(progress),
        }

    qu_started = time.perf_counter()
    try:
        qu_result, kb_label = _retrieve_documents(
            retrieval_text,
            limit=limit,
            kb_slugs=selected_slugs,
        )
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
        allow_weak=bool(selected_slugs),
        query=retrieval_text,
        min_relevance=min_relevance,
    )
    if documents and not _document_supports_query(documents[0], normalized):
        documents = []
    latency_ms["rag"] = _elapsed_ms(rag_started)

    if not documents:
        # Empty index or nothing above the policy relevance floor.
        empty_reason = (
            "sufler_unavailable"
            if not qu_result.get("documents")
            else "no_relevant_knowledge"
        )
        if len(_query_specific_tokens(normalized)) < 2:
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
                "kb_id": kb_label,
                "kb_slugs": selected_slugs or [],
                "hints": [],
                "citations_enabled": True,
                "blocked_reason": NO_HINT_REASON,
                "min_relevance": min_relevance,
                "latency_ms": latency_ms,
                "request_id": correlation_id,
                "scenario": None,
            }
        skip_ungrounded = grounded_only or (
            not _allow_ungrounded() and not ignored_suz_fixtures_exist()
        )
        if skip_ungrounded:
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
                "kb_id": kb_label,
                "kb_slugs": selected_slugs or [],
                "hints": [],
                "citations_enabled": True,
                "blocked_reason": empty_reason,
                "min_relevance": min_relevance,
                "latency_ms": latency_ms,
                "request_id": correlation_id,
                "scenario": _scenario_payload(progress),
            }

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
                kb_label=kb_label,
            ),
            temperature=float(settings.temperature),
            top_p=float(settings.top_p),
            max_tokens=int(settings.max_tokens),
        )
        llm_text = _extract_llm_text(llm_response)
        char_limit = max(int(settings.response_chars_max), 400)
        answer_text, operator_tip = _parse_llm_hint(llm_text)
        cleaned = _clean_answer_text(answer_text)
        answer_text = complete_sentences(cleaned, max_chars=char_limit)
        operator_tip = _safe_ru_en_text(operator_tip)
        if documents and _llm_misses_source(answer_text, documents[0]):
            grounded = _snippet_as_answer(documents[0], normalized)
            if grounded:
                answer_text = grounded
    except Exception:  # noqa: BLE001 — fall back to KB snippets
        logger.exception("sufler_llm_failed request_id=%s", correlation_id)
        answer_text, operator_tip = "", ""
        latency_ms["llm"] = _elapsed_ms(llm_started)
    else:
        latency_ms["llm"] = _elapsed_ms(llm_started)

    if not answer_text:
        if documents:
            answer_text = _snippet_as_answer(documents[0], normalized)
        if not answer_text:
            answer_text = (
                "В выбранных базах знаний нет подходящей статьи по этой реплике. "
                "Оформите продукт в отделении с паспортом либо через "
                "интернет-банк / мобильное приложение. Перед ответом "
                "сверьте актуальные условия в базе знаний."
            )
            operator_tip = operator_tip or "Сверить формулировку со статьёй базы знаний."

    hints: list[dict[str, Any]] = []
    for index, document in enumerate(documents):
        if float(document["relevance_score"]) < min_relevance and not selected_slugs:
            continue
        if index == 0:
            hint_text = answer_text
            tip = operator_tip
        else:
            hint_text = _snippet_as_answer(document, normalized)
            tip = ""
        hint_text = _safe_ru_en_text(hint_text)
        tip = _safe_ru_en_text(tip)
        if not hint_text:
            continue
        hints.append(
            {
                "rank": len(hints) + 1,
                "text": hint_text,
                "operator_tip": tip,
                "source_type": "knowledge_base",
                "relevance_score": document["relevance_score"],
                "relevance_percent": document["relevance_percent"],
                "citations": [_citation(document)],
            }
        )
    answer_text = _safe_ru_en_text(answer_text)
    operator_tip = _safe_ru_en_text(operator_tip)
    if answer_text and not hints:
        source = documents[0] if documents else None
        source_score = float(source["relevance_score"]) if source else 0.5
        if source is None or source_score >= min_relevance or selected_slugs:
            hints.append(
                {
                    "rank": 1,
                    "text": answer_text,
                    "operator_tip": operator_tip,
                    "source_type": "knowledge_base",
                    "relevance_score": source_score,
                    "relevance_percent": (
                        int(source["relevance_percent"]) if source else 50
                    ),
                    "citations": [_citation(source)] if source else [],
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
            "kb_id": kb_label,
            "kb_slugs": selected_slugs or [],
            "hints": [],
            "citations_enabled": True,
            "blocked_reason": "no_relevant_knowledge",
            "min_relevance": min_relevance,
            "latency_ms": latency_ms,
            "request_id": correlation_id,
            "scenario": _scenario_payload(progress),
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
        "kb_id": kb_label,
        "kb_slugs": selected_slugs or [],
        "hints": hints,
        "citations_enabled": True,
        "blocked_reason": None,
        "min_relevance": min_relevance,
        "latency_ms": latency_ms,
        "request_id": correlation_id,
        "gateway_model": active_gateway.get_runtime_model(PROFILE),
        "scenario": _scenario_payload(progress),
    }
