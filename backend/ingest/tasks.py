"""Celery orchestration for FR-UND-08 knowledge-base updates."""

from __future__ import annotations

from typing import Any, Mapping

from celery import chain, shared_task
from celery.result import AsyncResult

from ingest.pipeline import INDEX_NAME, ingest_payload
from ingest.schema import SuzPayload
from qu.tasks import (
    QU_RETRAIN_DEBOUNCE_SECONDS,
    REINDEX_COMPLETED_EVENT,
    build_retrain_task_id,
    qu_retrain,
)


@shared_task(name="ingest.reindex_kb")
def reindex_kb(payload_data: Mapping[str, Any]) -> dict[str, Any]:
    """Normalize, embed, and commit one SUZ article event to the KB index."""
    payload = SuzPayload.from_mapping(payload_data)
    result = ingest_payload(payload)
    return {
        "status": result.status,
        "outcome": result.outcome,
        "chunks_indexed": result.chunks_indexed,
        "kb_id": INDEX_NAME,
        "reindex_job_id": str(payload.event_id),
        "content_version": str(payload.version_id or payload.event_id),
        "trigger": REINDEX_COMPLETED_EVENT,
    }


def enqueue_ingest_chain(payload_data: Mapping[str, Any]) -> AsyncResult:
    """Enqueue reindexing followed by debounced QU retraining."""
    payload = SuzPayload.from_mapping(payload_data)
    retrain_task_id = build_retrain_task_id(
        INDEX_NAME,
        str(payload.event_id),
        str(payload.version_id or payload.event_id),
    )
    workflow = chain(
        reindex_kb.s(dict(payload_data)),
        qu_retrain.s().set(
            countdown=QU_RETRAIN_DEBOUNCE_SECONDS,
            task_id=retrain_task_id,
        ),
    )
    return workflow.apply_async()
