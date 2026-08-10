"""RAG retrieval over ``assistant_production`` (+ optional ``cc_production`` / SUZ)."""

from __future__ import annotations

import math
from typing import Any, Sequence

from django.db import connection
from django.db.models import QuerySet
from pgvector.django import CosineDistance

from core.embeddings import embed_query
from hub.kb_admin import ARTICLE_ID_BASE, SUZ_KB_SLUG
from hub.model_registry_store import get_model_settings
from hub.models import ContactCenterKnowledgeBase, KnowledgeBaseDocument
from ingest.models import AssistantProductionChunk, CCProductionChunk


DEFAULT_LIMIT = 5
MAX_LIMIT = 8
# Keep a short preview for UI citations; LLM must see the full chunk text.
SNIPPET_PREVIEW_CHARS = 800
# One chunk per document often drops the clause that answers the question
# (e.g. «сроком на 5 лет» deeper in the form). Keep up to two per article.
MAX_CHUNKS_PER_ARTICLE = 2


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
    assistant_slugs: list[str] = []
    include_suz = False
    cc_article_ids: list[int] = []
    for slug in slugs:
        if slug == SUZ_KB_SLUG:
            include_suz = True
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


def _document_from_chunk(
    *,
    rank: int,
    score: float,
    chunk: Any,
    kb_slug: str,
    threshold: float,
) -> dict[str, Any]:
    content = chunk.content or ""
    return {
        "rank": rank,
        "kb_slug": kb_slug,
        "article_id": chunk.article_id,
        "chunk_index": chunk.chunk_index,
        "title": chunk.title,
        "permalink": chunk.permalink,
        "content": content,
        "snippet": content[:SNIPPET_PREVIEW_CHARS],
        "relevance_score": round(score, 4),
        "relevance_percent": round(score * 100),
        "meets_min_relevance": score >= threshold,
    }


def preview_assistant_query(
    query: str,
    *,
    kb_slugs: Sequence[str] | None = None,
    limit: int = DEFAULT_LIMIT,
) -> dict[str, Any]:
    """Rank active chunks; assistant_* plus optional SUZ/CC when selected."""
    normalized_query = query.strip()
    if not normalized_query:
        raise ValueError("query must be a non-empty string")
    if not 1 <= limit <= MAX_LIMIT:
        raise ValueError(f"limit must be between 1 and {MAX_LIMIT}")

    slugs = _normalize_slugs(kb_slugs)
    assistant_slugs, include_suz, cc_article_ids = _split_slugs(slugs)
    # Empty selection → previous behavior: all assistant_* only.
    search_assistant = not slugs or bool(assistant_slugs)
    search_cc = bool(include_suz or cc_article_ids)

    query_embedding = embed_query(normalized_query)
    scored_chunks: list[tuple[float, Any, str]] = []

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
        if slugs:
            chunk_query = chunk_query.filter(kb_slug__in=assistant_slugs or ["__none__"])
        for score, chunk in _score_queryset(
            chunk_query, query_embedding, limit=limit
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
                article_id__in=cc_article_ids or []
            ).values_list("article_id", "knowledge_base__slug")
        }
        for score, chunk in _score_queryset(cc_query, query_embedding, limit=limit):
            article_id = int(chunk.article_id)
            kb_slug = (
                SUZ_KB_SLUG
                if article_id < ARTICLE_ID_BASE
                else article_slug_map.get(article_id, "cc_manual")
            )
            scored_chunks.append((score, chunk, kb_slug))

    scored_chunks.sort(
        key=lambda item: (
            -item[0],
            item[2],
            item[1].article_id,
            item[1].chunk_index,
        )
    )
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

    threshold = get_model_settings(
        "assistant_bank"
    ).context_inclusion_threshold
    documents = [
        _document_from_chunk(
            rank=rank,
            score=score,
            chunk=chunk,
            kb_slug=kb_slug,
            threshold=threshold,
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
