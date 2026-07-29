"""IV.5 OCR pipeline: upload → queue → recognize → store results."""

from __future__ import annotations

import hashlib
import json
import uuid
from pathlib import PurePosixPath
from typing import Any, BinaryIO

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from ocr.engine import OcrEngineError, recognize_document, resolve_ocr_model
from ocr.models import OcrJob
from ocr.storage import ObjectStoreError, get_object_store

ALLOWED_EXTENSIONS = frozenset(
    {".pdf", ".jpg", ".jpeg", ".png", ".tiff", ".tif"}
)
CONTENT_TYPES = {
    ".pdf": "application/pdf",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".tiff": "image/tiff",
    ".tif": "image/tiff",
}


class OcrPipelineError(ValueError):
    """Invalid OCR upload or job request."""


def _new_ids() -> tuple[str, str]:
    return (
        f"ocrjob-{uuid.uuid4().hex}",
        f"doc-{uuid.uuid4().hex}",
    )


def _normalize_filename(name: str) -> str:
    base = PurePosixPath(name.replace("\\", "/")).name.strip()
    if not base or base in {".", ".."}:
        raise OcrPipelineError("filename is required")
    return base[:240]


def validate_upload(filename: str, size: int) -> tuple[str, str]:
    safe_name = _normalize_filename(filename)
    suffix = PurePosixPath(safe_name).suffix.casefold()
    if suffix not in ALLOWED_EXTENSIONS:
        allowed = ", ".join(sorted(ALLOWED_EXTENSIONS))
        raise OcrPipelineError(
            f"Unsupported format {suffix or '(none)'}; allowed: {allowed}"
        )
    max_bytes = int(getattr(settings, "OCR_MAX_UPLOAD_BYTES", 25 * 1024 * 1024))
    if size <= 0:
        raise OcrPipelineError("empty file")
    if size > max_bytes:
        raise OcrPipelineError(f"file exceeds max size of {max_bytes} bytes")
    return safe_name, CONTENT_TYPES[suffix]


def create_job_from_upload(
    upload: BinaryIO,
    *,
    filename: str,
    content_type: str = "",
    created_by: str = "",
) -> OcrJob:
    """Persist original to object storage and enqueue OCR Celery job."""
    raw = upload.read()
    safe_name, detected_type = validate_upload(filename, len(raw))
    ctype = (content_type or "").strip() or detected_type
    sha256 = hashlib.sha256(raw).hexdigest()
    job_id, document_id = _new_ids()
    original_key = f"originals/{document_id}/{safe_name}"
    result_key = f"results/{job_id}/ocr_result.json"

    try:
        model_info = resolve_ocr_model()
        store = get_object_store()
        store.put_bytes(original_key, raw, content_type=ctype)
    except (OcrEngineError, ObjectStoreError) as exc:
        raise OcrPipelineError(str(exc)) from exc

    with transaction.atomic():
        job = OcrJob.objects.create(
            job_id=job_id,
            document_id=document_id,
            status=OcrJob.STATUS_QUEUED,
            filename=safe_name,
            content_type=ctype,
            sha256=sha256,
            original_object_key=original_key,
            result_object_key=result_key,
            ocr_model=model_info["model"],
            created_by=created_by[:150],
        )

    from ocr.tasks import run_ocr_job

    run_ocr_job.delay(job.job_id)
    return job


def process_job(job_id: str) -> dict[str, Any]:
    """Celery worker entry: OCR + write result JSON to object storage."""
    try:
        job = OcrJob.objects.get(pk=job_id)
    except OcrJob.DoesNotExist as exc:
        raise OcrPipelineError(f"Unknown job_id: {job_id}") from exc

    job.status = OcrJob.STATUS_OCR_PROCESSING
    job.error_message = ""
    job.save(update_fields=["status", "error_message", "updated_at"])

    store = get_object_store()
    try:
        content = store.get_bytes(job.original_object_key)
        result = recognize_document(
            content,
            filename=job.filename,
            content_type=job.content_type,
            document_id=job.document_id,
            job_id=job.job_id,
            sha256=job.sha256,
        )
        payload = json.dumps(result, ensure_ascii=False, indent=2).encode(
            "utf-8"
        )
        store.put_bytes(
            job.result_object_key,
            payload,
            content_type="application/json",
        )
    except (OcrEngineError, ObjectStoreError, OcrPipelineError) as exc:
        job.status = OcrJob.STATUS_ERROR
        job.error_message = str(exc)[:2000]
        job.save(
            update_fields=["status", "error_message", "updated_at"]
        )
        raise

    job.status = OcrJob.STATUS_COMPLETED
    job.completed_at = timezone.now()
    job.ocr_model = result["ocr_engine"]["version"]
    job.save(
        update_fields=[
            "status",
            "completed_at",
            "ocr_model",
            "updated_at",
        ]
    )
    return {
        "job_id": job.job_id,
        "document_id": job.document_id,
        "status": job.status,
        "result_object_key": job.result_object_key,
        "pages": len(result["pages"]),
    }


def job_to_dict(job: OcrJob) -> dict[str, Any]:
    return {
        "job_id": job.job_id,
        "document_id": job.document_id,
        "status": job.status,
        "filename": job.filename,
        "content_type": job.content_type,
        "sha256": job.sha256,
        "ocr_model": job.ocr_model,
        "original_object_key": job.original_object_key,
        "result_object_key": job.result_object_key or None,
        "error_message": job.error_message or None,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "completed_at": (
            job.completed_at.isoformat() if job.completed_at else None
        ),
        "pipeline": "IV.5",
        "fr": ["FR-OCR-04", "FR-OCR-06", "FR-OCR-08"],
    }


def load_result(job: OcrJob) -> dict[str, Any]:
    if job.status != OcrJob.STATUS_COMPLETED:
        raise OcrPipelineError(
            f"Result not ready; status={job.status}"
        )
    if not job.result_object_key:
        raise OcrPipelineError("Result object key missing")
    store = get_object_store()
    try:
        raw = store.get_bytes(job.result_object_key)
    except ObjectStoreError as exc:
        raise OcrPipelineError(str(exc)) from exc
    return json.loads(raw.decode("utf-8"))
