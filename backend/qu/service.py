"""Read-only Query Understanding preview service for FR-UND-12."""

from __future__ import annotations

import math
import re
from collections.abc import Iterable, Sequence
from typing import Any

from django.db import connection
from pgvector.django import CosineDistance

from hub.model_registry_store import get_model_settings
from ingest.models import CCProductionChunk
from core.embeddings import embed_query, embed_query_with_backend
from qu.models import QuReferenceExample


DEFAULT_LIMIT = 5
MAX_LIMIT = 5
_TOKEN_RE = re.compile(r"[а-яёa-z0-9]{3,}", re.IGNORECASE)
_STOPWORDS = frozenset(
    {
        "как",
        "что",
        "это",
        "для",
        "при",
        "или",
        "чем",
        "его",
        "они",
        "мы",
        "вы",
        "на",
        "по",
        "со",
        "из",
        "от",
        "до",
        "не",
        "ни",
        "же",
        "ли",
        "бы",
        "то",
        "да",
        "за",
        "без",
        "про",
        "между",
    }
)


def _tokens(text: str) -> set[str]:
    return {
        token
        for token in _TOKEN_RE.findall((text or "").casefold())
        if token not in _STOPWORDS
    }


def _lexical_score(query: str, title: str, content: str) -> float:
    query_tokens = _tokens(query)
    if not query_tokens:
        return 0.0
    title_tokens = _tokens(title)
    doc_tokens = title_tokens | _tokens(content)
    if not doc_tokens:
        return 0.0
    overlap = query_tokens & doc_tokens
    if not overlap:
        return 0.0
    recall = len(overlap) / len(query_tokens)
    title_hits = query_tokens & title_tokens
    title_bonus = 0.2 * (len(title_hits) / len(query_tokens))
    return min(1.0, recall + title_bonus)


def _score_lexical(
    chunks: Iterable[CCProductionChunk],
    query: str,
) -> list[tuple[float, CCProductionChunk]]:
    scored: list[tuple[float, CCProductionChunk]] = []
    for chunk in chunks:
        score = _lexical_score(query, chunk.title, chunk.content)
        if score > 0:
            scored.append((score, chunk))
    scored.sort(key=lambda item: (-item[0], item[1].article_id))
    return scored


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
                embed_query(example.question),
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

    query_embedding, backend = embed_query_with_backend(normalized_query)
    chunk_query = CCProductionChunk.objects.filter(is_active=True).only(
        "article_id",
        "chunk_index",
        "title",
        "content",
        "permalink",
        "embedding",
    )
    if backend == "http-fallback":
        scored_chunks = _score_lexical(chunk_query, normalized_query)[: limit * 20]
    elif connection.vendor == "postgresql":
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
        if backend == "http-fallback":
            matched_example_id, matched_example = None, chunk.title
        else:
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
