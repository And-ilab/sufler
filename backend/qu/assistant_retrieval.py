"""RAG retrieval over ``assistant_production`` (isolated from cc_production)."""

from __future__ import annotations

import math
from typing import Any, Sequence

from django.db import connection
from pgvector.django import CosineDistance

from core.embeddings import embed_query
from hub.model_registry_store import get_model_settings
from ingest.models import AssistantProductionChunk


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


def preview_assistant_query(
    query: str,
    *,
    kb_slugs: Sequence[str] | None = None,
    limit: int = DEFAULT_LIMIT,
) -> dict[str, Any]:
    """Rank active assistant_* chunks, optionally filtered by kb_slug list."""
    normalized_query = query.strip()
    if not normalized_query:
        raise ValueError("query must be a non-empty string")
    if not 1 <= limit <= MAX_LIMIT:
        raise ValueError(f"limit must be between 1 and {MAX_LIMIT}")

    slugs = [
        slug.strip()
        for slug in (kb_slugs or [])
        if isinstance(slug, str) and slug.strip()
    ]

    query_embedding = embed_query(normalized_query)
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
        chunk_query = chunk_query.filter(kb_slug__in=slugs)

    if connection.vendor == "postgresql":
        chunks = list(
            chunk_query.annotate(
                distance=CosineDistance("embedding", query_embedding)
            ).order_by("distance", "article_id")[: limit * 20]
        )
        scored_chunks = [
            (max(0.0, min(1.0, 1.0 - float(chunk.distance))), chunk)
            for chunk in chunks
        ]
    else:
        chunks = list(chunk_query)
        scored_chunks = [
            (
                _cosine_similarity(query_embedding, list(chunk.embedding)),
                chunk,
            )
            for chunk in chunks
        ]

    scored_chunks.sort(
        key=lambda item: (
            -item[0],
            item[1].kb_slug,
            item[1].article_id,
            item[1].chunk_index,
        )
    )
    per_article: dict[tuple[str, int], int] = {}
    ranked: list[tuple[float, AssistantProductionChunk]] = []
    for score, chunk in scored_chunks:
        key = (chunk.kb_slug, chunk.article_id)
        taken = per_article.get(key, 0)
        if taken >= MAX_CHUNKS_PER_ARTICLE:
            continue
        per_article[key] = taken + 1
        ranked.append((score, chunk))
        if len(ranked) >= limit:
            break

    threshold = get_model_settings(
        "assistant_bank"
    ).context_inclusion_threshold
    documents = []
    for rank, (score, chunk) in enumerate(ranked, start=1):
        content = chunk.content or ""
        documents.append(
            {
                "rank": rank,
                "kb_slug": chunk.kb_slug,
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
        )

    return {
        "query": normalized_query,
        "kb_id": "assistant_production",
        "kb_slugs": slugs,
        "min_relevance": threshold,
        "min_relevance_percent": round(threshold * 100),
        "documents": documents,
    }
