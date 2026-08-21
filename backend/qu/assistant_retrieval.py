"""RAG retrieval over ``assistant_production`` (+ optional ``cc_production`` / SUZ)."""

from __future__ import annotations

import math
from typing import Any, Sequence

from django.db import connection
from django.db.models import QuerySet
from pgvector.django import CosineDistance

from core.embeddings import embed_query_with_backend
from hub.kb_admin import ARTICLE_ID_BASE, SUZ_KB_SLUG
from hub.model_registry_store import get_model_settings
from hub.models import ContactCenterKnowledgeBase, KnowledgeBaseDocument
from ingest.models import AssistantProductionChunk, CCProductionChunk
from qu.models import QuReferenceExample
from qu.service import (
    EXAMPLE_MATCH_FLOOR,
    _lexical_score,
    boost_chunks_with_examples,
    extractive_answer,
    focused_snippet,
    matching_training_examples,
    training_example_score,
)


DEFAULT_LIMIT = 5
MAX_LIMIT = 8
# Keep a short preview for UI citations; LLM must see the full chunk text.
SNIPPET_PREVIEW_CHARS = 1200
# Header-only first chunk often drops the answering clause («до 23 лет»).
MAX_CHUNKS_PER_ARTICLE = 3


def _joined_article_content(article_id: int) -> str:
    """All chunks of one file, in order — preview must see the answering clause."""
    parts = list(
        CCProductionChunk.objects.filter(is_active=True, article_id=article_id)
        .order_by("chunk_index")
        .values_list("content", flat=True)
    )
    if not parts:
        parts = list(
            AssistantProductionChunk.objects.filter(
                is_active=True,
                article_id=article_id,
            )
            .order_by("chunk_index")
            .values_list("content", flat=True)
        )
    return "\n".join(part for part in parts if part)


def _cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    dot = sum(a * b for a, b in zip(left, right, strict=False))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if not left_norm or not right_norm:
        return 0.0
    return max(0.0, min(1.0, dot / (left_norm * right_norm)))


def _normalize_slugs(kb_slugs: Sequence[str] | None) -> list[str]:
    return [
        slug.strip()
        for slug in (kb_slugs or [])
        if isinstance(slug, str) and slug.strip()
    ]


def _split_slugs(slugs: Sequence[str]) -> tuple[list[str], bool, list[int]]:
    """Return (assistant_slugs, include_suz, cc_manual_article_ids)."""
    from hub.models import AssistantKnowledgeBase

    assistant_slugs: list[str] = []
    include_suz = False
    cc_article_ids: list[int] = []
    for slug in slugs:
        if slug == SUZ_KB_SLUG:
            include_suz = True
            continue
        if slug.startswith("assistant:"):
            pk = slug.split(":", 1)[1]
            kb = AssistantKnowledgeBase.objects.filter(pk=pk).only("slug").first()
            if kb is not None:
                assistant_slugs.append(kb.slug)
            continue
        if slug.startswith("cc:"):
            pk = slug.split(":", 1)[1]
            kb = (
                ContactCenterKnowledgeBase.objects.filter(pk=pk)
                .only("id", "source", "slug")
                .first()
            )
            if kb is None:
                continue
            if kb.source == ContactCenterKnowledgeBase.SOURCE_SUZ_BITRIX or kb.slug == SUZ_KB_SLUG:
                include_suz = True
            else:
                ids = list(
                    KnowledgeBaseDocument.objects.filter(knowledge_base_id=kb.pk).values_list(
                        "article_id",
                        flat=True,
                    )
                )
                cc_article_ids.extend(int(value) for value in ids)
            continue
        if slug.startswith("assistant_"):
            assistant_slugs.append(slug)
            continue
        kb = (
            ContactCenterKnowledgeBase.objects.filter(slug=slug)
            .only("id", "source", "slug")
            .first()
        )
        if kb is None:
            # Unknown slug: keep as assistant filter for backward compatibility.
            assistant_slugs.append(slug)
            continue
        if kb.source == ContactCenterKnowledgeBase.SOURCE_SUZ_BITRIX:
            include_suz = True
            continue
        ids = list(
            KnowledgeBaseDocument.objects.filter(knowledge_base_id=kb.pk).values_list(
                "article_id",
                flat=True,
            )
        )
        cc_article_ids.extend(int(value) for value in ids)

    return assistant_slugs, include_suz, cc_article_ids


def _score_queryset(
    chunk_query: QuerySet,
    query_embedding: list[float],
    *,
    limit: int,
) -> list[tuple[float, Any]]:
    if connection.vendor == "postgresql":
        chunks = list(
            chunk_query.annotate(
                distance=CosineDistance("embedding", query_embedding)
            ).order_by("distance", "article_id")[: limit * 20]
        )
        return [
            (max(0.0, min(1.0, 1.0 - float(chunk.distance))), chunk)
            for chunk in chunks
        ]
    chunks = list(chunk_query)
    return [
        (
            _cosine_similarity(query_embedding, list(chunk.embedding)),
            chunk,
        )
        for chunk in chunks
    ]


def _rank_chunks_hybrid(
    chunk_query: QuerySet,
    query_text: str,
    query_embedding: list[float],
    *,
    backend: str,
    limit: int,
) -> list[tuple[float, Any]]:
    """Blend vector similarity with keyword overlap so short RU questions still hit."""
    if backend == "http-fallback":
        scored = []
        for chunk in chunk_query:
            score = _lexical_score(query_text, chunk.title, chunk.content)
            if score > 0:
                scored.append((score, chunk))
        scored.sort(key=lambda item: (-item[0], item[1].article_id))
        return scored[: limit * 20]

    vector_scored = _score_queryset(
        chunk_query, query_embedding, limit=limit
    )
    combined: dict[tuple[int, int], tuple[float, Any]] = {}
    for vector_score, chunk in vector_scored:
        lexical = _lexical_score(query_text, chunk.title, chunk.content)
        combined[(int(chunk.article_id), int(chunk.chunk_index))] = (
            max(float(vector_score), lexical),
            chunk,
        )
    best = max((score for score, _ in combined.values()), default=0.0)
    if best < 0.25:
        for chunk in list(chunk_query[:1500]):
            key = (int(chunk.article_id), int(chunk.chunk_index))
            lexical = _lexical_score(query_text, chunk.title, chunk.content)
            if lexical <= 0:
                continue
            previous = combined.get(key)
            if previous is None or lexical > previous[0]:
                combined[key] = (lexical, chunk)
    ranked = sorted(
        combined.values(),
        key=lambda item: (-item[0], item[1].article_id, item[1].chunk_index),
    )
    return ranked[: limit * 20]


def _document_from_chunk(
    *,
    rank: int,
    score: float,
    chunk: Any,
    kb_slug: str,
    threshold: float,
    query: str,
    content: str | None = None,
) -> dict[str, Any]:
    text = content if content is not None else (chunk.content or "")
    return {
        "rank": rank,
        "kb_slug": kb_slug,
        "article_id": chunk.article_id,
        "chunk_index": chunk.chunk_index,
        "title": chunk.title,
        "permalink": chunk.permalink,
        "content": text,
        "snippet": focused_snippet(text, query, SNIPPET_PREVIEW_CHARS),
        "relevance_score": round(score, 4),
        "relevance_percent": round(score * 100),
        "meets_min_relevance": score >= threshold,
    }


def preview_assistant_query(
    query: str,
    *,
    kb_slugs: Sequence[str] | None = None,
    limit: int = DEFAULT_LIMIT,
    search_all: bool = False,
    group_articles: bool = False,
) -> dict[str, Any]:
    """Rank active chunks; assistant_* plus optional SUZ/CC when selected."""
    normalized_query = query.strip()
    if not normalized_query:
        raise ValueError("query must be a non-empty string")
    if not 1 <= limit <= MAX_LIMIT:
        raise ValueError(f"limit must be between 1 and {MAX_LIMIT}")

    slugs = _normalize_slugs(kb_slugs)
    if search_all:
        assistant_slugs: list[str] = []
        include_suz = True
        cc_article_ids: list[int] = []
        search_assistant = True
        search_cc = True
    else:
        assistant_slugs, include_suz, cc_article_ids = _split_slugs(slugs)
        # Empty selection → previous behavior: all assistant_* only.
        search_assistant = not slugs or bool(assistant_slugs)
        search_cc = bool(include_suz or cc_article_ids)

    query_embedding, backend = embed_query_with_backend(normalized_query)
    scored_chunks: list[tuple[float, Any, str]] = []
    article_slug_map: dict[int, str] = {}

    if search_assistant:
        chunk_query = AssistantProductionChunk.objects.filter(is_active=True).only(
            "kb_slug",
            "article_id",
            "chunk_index",
            "title",
            "content",
            "permalink",
            "embedding",
        )
        if slugs and not search_all:
            chunk_query = chunk_query.filter(kb_slug__in=assistant_slugs or ["__none__"])
        for score, chunk in _rank_chunks_hybrid(
            chunk_query,
            normalized_query,
            query_embedding,
            backend=backend,
            limit=limit,
        ):
            scored_chunks.append((score, chunk, chunk.kb_slug))

    if search_cc:
        cc_query = CCProductionChunk.objects.filter(is_active=True).only(
            "article_id",
            "chunk_index",
            "title",
            "content",
            "permalink",
            "embedding",
        )
        if not search_all:
            if include_suz and cc_article_ids:
                from django.db.models import Q

                cc_query = cc_query.filter(
                    Q(article_id__lt=ARTICLE_ID_BASE) | Q(article_id__in=cc_article_ids)
                )
            elif include_suz:
                cc_query = cc_query.filter(article_id__lt=ARTICLE_ID_BASE)
            else:
                cc_query = cc_query.filter(article_id__in=cc_article_ids or [-1])
        article_slug_map = {
            int(article_id): slug
            for article_id, slug in KnowledgeBaseDocument.objects.filter(
                **({} if search_all else {"article_id__in": cc_article_ids or []})
            ).values_list("article_id", "knowledge_base__slug")
        }
        for score, chunk in _rank_chunks_hybrid(
            cc_query,
            normalized_query,
            query_embedding,
            backend=backend,
            limit=limit,
        ):
            article_id = int(chunk.article_id)
            kb_slug = (
                SUZ_KB_SLUG
                if article_id < ARTICLE_ID_BASE
                else article_slug_map.get(article_id, "cc_manual")
            )
            scored_chunks.append((score, chunk, kb_slug))

    matches = matching_training_examples(normalized_query)
    pin_ids = [int(matches[0][1].article_id)] if matches else []
    extra_pairs: list[tuple[Any, str]] = []
    if pin_ids and search_cc:
        cc_extra = CCProductionChunk.objects.filter(
            is_active=True,
            article_id__in=pin_ids,
        )
        if not search_all:
            if include_suz and cc_article_ids:
                from django.db.models import Q

                cc_extra = cc_extra.filter(
                    Q(article_id__lt=ARTICLE_ID_BASE) | Q(article_id__in=cc_article_ids)
                )
            elif include_suz:
                cc_extra = cc_extra.filter(article_id__lt=ARTICLE_ID_BASE)
            elif cc_article_ids:
                cc_extra = cc_extra.filter(article_id__in=cc_article_ids)
        for chunk in cc_extra:
            article_id = int(chunk.article_id)
            extra_pairs.append(
                (
                    chunk,
                    SUZ_KB_SLUG
                    if article_id < ARTICLE_ID_BASE
                    else article_slug_map.get(article_id, "cc_manual"),
                )
            )
    if pin_ids and search_assistant:
        assistant_extra = AssistantProductionChunk.objects.filter(
            is_active=True,
            article_id__in=pin_ids,
        )
        if slugs and not search_all:
            assistant_extra = assistant_extra.filter(
                kb_slug__in=assistant_slugs or ["__none__"]
            )
        for chunk in assistant_extra:
            extra_pairs.append((chunk, chunk.kb_slug))
    if pin_ids:
        boosted = boost_chunks_with_examples(
            [(score, chunk) for score, chunk, _kb in scored_chunks],
            normalized_query,
            [chunk for chunk, _kb in extra_pairs],
        )
        slug_by_key = {
            (int(chunk.article_id), int(chunk.chunk_index)): kb_slug
            for _score, chunk, kb_slug in scored_chunks
        }
        for chunk, kb_slug in extra_pairs:
            slug_by_key.setdefault(
                (int(chunk.article_id), int(chunk.chunk_index)),
                kb_slug,
            )
        scored_chunks = [
            (
                score,
                chunk,
                slug_by_key.get(
                    (int(chunk.article_id), int(getattr(chunk, "chunk_index", 0))),
                    "cc_manual",
                ),
            )
            for score, chunk in boosted
        ]

    scored_chunks.sort(
        key=lambda item: (
            -item[0],
            item[2],
            item[1].article_id,
            item[1].chunk_index,
        )
    )
    threshold = get_model_settings(
        "assistant_bank"
    ).context_inclusion_threshold
    if group_articles:
        grouped: dict[tuple[str, int], list[tuple[float, Any, str]]] = {}
        for score, chunk, kb_slug in scored_chunks:
            grouped.setdefault((kb_slug, int(chunk.article_id)), []).append(
                (score, chunk, kb_slug)
            )
        ranked_articles: list[tuple[float, Any, str, str]] = []
        for items in grouped.values():
            items.sort(key=lambda item: item[1].chunk_index)
            score = max(item[0] for item in items)
            content = "\n".join(item[1].content or "" for item in items)
            best = max(
                items,
                key=lambda item: (
                    _lexical_score(
                        normalized_query,
                        item[1].title,
                        item[1].content,
                    ),
                    item[0],
                ),
            )
            ranked_articles.append((score, best[1], best[2], content))
        ranked_articles.sort(
            key=lambda item: (-item[0], item[2], item[1].article_id)
        )
        documents = [
            _document_from_chunk(
                rank=rank,
                score=score,
                chunk=chunk,
                kb_slug=kb_slug,
                threshold=threshold,
                query=normalized_query,
                content=content,
            )
            for rank, (score, chunk, kb_slug, content) in enumerate(
                ranked_articles[:limit], start=1
            )
        ]
    else:
        per_article: dict[tuple[str, int], int] = {}
        ranked: list[tuple[float, Any, str]] = []
        for score, chunk, kb_slug in scored_chunks:
            key = (kb_slug, chunk.article_id)
            taken = per_article.get(key, 0)
            if taken >= MAX_CHUNKS_PER_ARTICLE:
                continue
            per_article[key] = taken + 1
            ranked.append((score, chunk, kb_slug))
            if len(ranked) >= limit:
                break
        documents = [
            _document_from_chunk(
                rank=rank,
                score=score,
                chunk=chunk,
                kb_slug=kb_slug,
                threshold=threshold,
                query=normalized_query,
            )
            for rank, (score, chunk, kb_slug) in enumerate(ranked, start=1)
        ]

    return {
        "query": normalized_query,
        "kb_id": "assistant_production+cc_production",
        "kb_slugs": slugs,
        "min_relevance": threshold,
        "min_relevance_percent": round(threshold * 100),
        "documents": documents,
    }


def preview_admin_query(
    query: str,
    *,
    limit: int = DEFAULT_LIMIT,
) -> dict[str, Any]:
    """Hub QU preview: every indexed file, with training pins and an extractive hint."""
    result = preview_assistant_query(
        query,
        search_all=True,
        group_articles=True,
        limit=limit,
    )
    normalized_query = str(result.get("query") or query).strip()
    examples = list(QuReferenceExample.objects.filter(is_active=True))
    examples_by_article: dict[int, list[QuReferenceExample]] = {}
    for example in examples:
        if example.article_id is None:
            continue
        examples_by_article.setdefault(int(example.article_id), []).append(example)

    documents = list(result.get("documents") or [])
    for document in documents:
        article_examples = examples_by_article.get(int(document["article_id"]), [])
        pinned = max(
            article_examples,
            key=lambda example: training_example_score(normalized_query, example),
            default=None,
        )
        if (
            pinned is not None
            and training_example_score(normalized_query, pinned) >= EXAMPLE_MATCH_FLOOR
        ):
            document["matched_example_id"] = pinned.pk
            document["matched_example"] = pinned.question
        else:
            document["matched_example_id"] = None
            document["matched_example"] = document.get("title") or ""

    hint = None
    if documents:
        top = documents[0]
        source = _joined_article_content(int(top["article_id"])) or str(
            top.get("content") or ""
        )
        if source:
            top["content"] = source
            top["snippet"] = focused_snippet(
                source,
                normalized_query,
                SNIPPET_PREVIEW_CHARS,
            )
        hint_text = extractive_answer(source, normalized_query)
        if hint_text:
            hint = {
                "text": hint_text,
                "title": top["title"],
                "permalink": top.get("permalink") or "",
                "article_id": top["article_id"],
                "kb_slug": top.get("kb_slug") or "",
                "relevance_percent": top["relevance_percent"],
            }

    result["kb_id"] = "all_knowledge_bases"
    result["hint"] = hint
    result["documents"] = documents
    return result
