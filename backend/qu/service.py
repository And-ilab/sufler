"""Read-only Query Understanding preview service for FR-UND-12."""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
from typing import Any

from django.db import connection
from pgvector.django import CosineDistance

from hub.model_registry_store import get_model_settings
from ingest.models import CCProductionChunk
from ingest.pipeline import deterministic_embedding
from qu.models import QuReferenceExample


DEFAULT_LIMIT = 5
MAX_LIMIT = 5


def _cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    dot = sum(a * b for a, b in zip(left, right, strict=False))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if not left_norm or not right_norm:
        return 0.0
    return max(0.0, min(1.0, dot / (left_norm * right_norm)))


def _best_example(
    query_embedding: Sequence[float],
    examples: Iterable[QuReferenceExample],
    *,
    fallback: str,
) -> tuple[int | None, str]:
    ranked = [
        (
            _cosine_similarity(
                query_embedding,
                deterministic_embedding(example.question),
            ),
            example,
        )
        for example in examples
    ]
    if not ranked:
        return None, fallback
    _, best = max(ranked, key=lambda item: item[0])
    return best.pk, best.question


def preview_query(query: str, *, limit: int = DEFAULT_LIMIT) -> dict[str, Any]:
    """Rank active KB documents and attach the source QU example."""
    normalized_query = query.strip()
    if not normalized_query:
        raise ValueError("query must be a non-empty string")
    if not 1 <= limit <= MAX_LIMIT:
        raise ValueError(f"limit must be between 1 and {MAX_LIMIT}")

    query_embedding = deterministic_embedding(normalized_query)
    chunk_query = CCProductionChunk.objects.filter(is_active=True).only(
        "article_id",
        "chunk_index",
        "title",
        "content",
        "permalink",
        "embedding",
    )
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
    examples = list(QuReferenceExample.objects.filter(is_active=True))
    examples_by_article: dict[int, list[QuReferenceExample]] = {}
    global_examples: list[QuReferenceExample] = []
    for example in examples:
        if example.article_id is None:
            global_examples.append(example)
        else:
            examples_by_article.setdefault(example.article_id, []).append(
                example
            )

    best_chunks: dict[int, tuple[float, CCProductionChunk]] = {}
    for score, chunk in scored_chunks:
        current = best_chunks.get(chunk.article_id)
        if current is None or score > current[0]:
            best_chunks[chunk.article_id] = (score, chunk)

    ranked = sorted(
        best_chunks.values(),
        key=lambda item: (-item[0], item[1].article_id),
    )[:limit]
    threshold = get_model_settings(
        "assistant_bank"
    ).context_inclusion_threshold
    documents = []
    for rank, (score, chunk) in enumerate(ranked, start=1):
        matched_example_id, matched_example = _best_example(
            query_embedding,
            examples_by_article.get(chunk.article_id, global_examples),
            fallback=chunk.title,
        )
        documents.append(
            {
                "rank": rank,
                "article_id": chunk.article_id,
                "chunk_index": chunk.chunk_index,
                "title": chunk.title,
                "permalink": chunk.permalink,
                "snippet": chunk.content[:240],
                "relevance_score": round(score, 4),
                "relevance_percent": round(score * 100),
                "meets_min_relevance": score >= threshold,
                "matched_example_id": matched_example_id,
                "matched_example": matched_example,
            }
        )

    return {
        "query": normalized_query,
        "kb_id": "cc_production",
        "min_relevance": threshold,
        "min_relevance_percent": round(threshold * 100),
        "documents": documents,
    }
