"""CPU embedding HTTP service for Sufler RAG (E5 multilingual, 1024-d)."""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

DEFAULT_MODEL = os.environ.get(
    "EMBEDDING_MODEL",
    "intfloat/multilingual-e5-large",
)
EXPECTED_DIMS = int(os.environ.get("EMBEDDING_DIMENSIONS", "1024"))

app = FastAPI(title="Sufler Embedding Service", version="0.1.0")


class EmbedRequest(BaseModel):
    texts: list[str] = Field(min_length=1)
    is_query: bool = False
    model: str | None = None


class EmbedResponse(BaseModel):
    embeddings: list[list[float]]
    model: str
    dimensions: int


def _prefix(text: str, *, is_query: bool) -> str:
    stripped = text.strip()
    lowered = stripped.casefold()
    if lowered.startswith("query:") or lowered.startswith("passage:"):
        return stripped
    return f"{'query' if is_query else 'passage'}: {stripped}"


@lru_cache(maxsize=1)
def _load_model(model_name: str):
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(model_name)


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "model": DEFAULT_MODEL,
        "dimensions": EXPECTED_DIMS,
    }


@app.post("/embed", response_model=EmbedResponse)
def embed(request: EmbedRequest) -> EmbedResponse:
    model_name = (request.model or DEFAULT_MODEL).strip() or DEFAULT_MODEL
    try:
        model = _load_model(model_name)
        vectors = model.encode(
            [_prefix(text, is_query=request.is_query) for text in request.texts],
            normalize_embeddings=True,
            show_progress_bar=False,
        )
    except Exception as exc:  # noqa: BLE001 — surface load/encode errors
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    embeddings = [[float(value) for value in row] for row in vectors]
    if embeddings and len(embeddings[0]) != EXPECTED_DIMS:
        raise HTTPException(
            status_code=500,
            detail=(
                f"Model returned dim={len(embeddings[0])}, "
                f"expected {EXPECTED_DIMS}"
            ),
        )
    return EmbedResponse(
        embeddings=embeddings,
        model=model_name,
        dimensions=EXPECTED_DIMS,
    )
