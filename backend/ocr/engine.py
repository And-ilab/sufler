"""OCR engine resolution from ModelRegistry (Tesseract stub)."""

from __future__ import annotations

import hashlib
from typing import Any

from core.model_registry import ModelRegistry, ModelRegistryError

SLOT_NAME = "ocr"
DEFAULT_STUB_MODEL = "stub:tesseract"


class OcrEngineError(RuntimeError):
    """OCR engine failure."""


def resolve_ocr_model() -> dict[str, Any]:
    """Read ModelRegistry `ocr` slot; fall back to Tesseract stub."""
    try:
        slot = ModelRegistry.load().get_slot(SLOT_NAME)
    except ModelRegistryError as exc:
        raise OcrEngineError(str(exc)) from exc

    model = slot.dev_model or DEFAULT_STUB_MODEL
    return {
        "slot": SLOT_NAME,
        "model": model,
        "status": slot.status,
        "kpi": dict(slot.kpi),
        "languages": list(slot.kpi.get("languages") or ["ru", "en"]),
    }


def _stub_page_text(
    *,
    filename: str,
    sha256: str,
    content: bytes,
    content_type: str,
) -> str:
    """Deterministic stub recognition without native Tesseract binary."""
    # Prefer embedded UTF-8 when tests upload text-as-image payloads.
    try:
        decoded = content.decode("utf-8")
        if decoded.isprintable() or "\n" in decoded:
            stripped = decoded.strip()
            if stripped and len(stripped) < 50_000:
                return stripped
    except UnicodeDecodeError:
        pass

    digest = hashlib.sha256(content).hexdigest()[:12]
    return (
        f"[stub:tesseract] filename={filename} "
        f"sha256={sha256[:16]}… content_sha={digest} "
        f"type={content_type or 'unknown'}"
    )


def recognize_document(
    content: bytes,
    *,
    filename: str,
    content_type: str,
    document_id: str,
    job_id: str,
    sha256: str,
) -> dict[str, Any]:
    """Run OCR via ModelRegistry slot (stub:tesseract)."""
    resolved = resolve_ocr_model()
    model = resolved["model"]
    if not (
        model.startswith("stub:")
        or "tesseract" in model.casefold()
    ):
        raise OcrEngineError(
            f"OCR model {model!r} is not supported in this foundation build; "
            f"use {DEFAULT_STUB_MODEL!r}"
        )

    text = _stub_page_text(
        filename=filename,
        sha256=sha256,
        content=content,
        content_type=content_type,
    )
    confidence = 0.92
    languages = resolved["languages"]
    language = languages[0] if languages else "ru"

    return {
        "schema_version": "1.0",
        "job_id": job_id,
        "document_id": document_id,
        "document_sha256": sha256,
        "document_type_candidate": "unknown",
        "language": language,
        "ocr_engine": {
            "name": "tesseract",
            "version": model,
            "slot": SLOT_NAME,
            "mode": "stub",
        },
        "pages": [
            {
                "page": 1,
                "text": text,
                "confidence": confidence,
                "blocks_ref": None,
            }
        ],
        "template": {
            "id": None,
            "version": None,
        },
        "status": "ocr_completed",
    }
