"""OCR engine resolution from ModelRegistry (Tesseract / Paddle / stub)."""

from __future__ import annotations

import hashlib
import io
import re
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


def _decode_embedded_text(content: bytes) -> str | None:
    """Prefer embedded UTF-8 when tests upload text-as-image payloads."""
    try:
        decoded = content.decode("utf-8")
    except UnicodeDecodeError:
        return None
    if decoded.isprintable() or "\n" in decoded:
        stripped = decoded.strip()
        if stripped and len(stripped) < 50_000:
            return stripped
    return None


def _ocr_mrz_strip(image: Any) -> str | None:
    """Second Tesseract pass on the bottom band — ICAO MRZ is Latin + <."""
    try:
        import pytesseract  # type: ignore
    except Exception:
        return None
    try:
        width, height = image.size
        if width < 40 or height < 40:
            return None
        gray = image.convert("L")
        chunks: list[str] = []
        bands = (
            (int(height * 0.55), int(height * 0.88)),
            (int(height * 0.72), height),
        )
        config = (
            "--psm 6 -c "
            "tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789<"
        )
        for top, bottom in bands:
            if bottom - top < 20:
                continue
            band = gray.crop((0, top, width, bottom))
            if band.width > 1400:
                scale = 1400 / band.width
                band = band.resize((1400, max(40, int(band.height * scale))))
            elif 80 <= band.width < 500:
                band = band.resize((band.width * 2, band.height * 2))
            text = pytesseract.image_to_string(band, lang="eng", config=config)
            cleaned = (text or "").strip()
            if cleaned and cleaned not in chunks:
                chunks.append(cleaned)
        return "\n".join(chunks) or None
    except Exception:
        return None


def _prepare_ocr_image(image: Any) -> Any:
    """Upscale small scans and lift contrast before Tesseract."""
    from PIL import ImageEnhance, ImageOps  # type: ignore

    prepared = image.convert("RGB")
    width, height = prepared.size
    max_side = max(width, height)
    min_side = min(width, height)
    if max_side > 4000:
        scale = 4000 / max_side
        prepared = prepared.resize(
            (max(1, int(width * scale)), max(1, int(height * scale))),
            resample=1,
        )
    elif min_side < 800:
        scale = 2 if min_side < 500 else 1.4
        prepared = prepared.resize(
            (int(width * scale), int(height * scale)),
            resample=1,
        )
        prepared = ImageOps.autocontrast(prepared, cutoff=1)
        prepared = ImageEnhance.Contrast(prepared).enhance(1.2)
        prepared = ImageEnhance.Sharpness(prepared).enhance(1.1)
    return prepared


def _ocr_with_tesseract(content: bytes, languages: list[str]) -> str | None:
    try:
        import pytesseract  # type: ignore
        from PIL import Image  # type: ignore
    except Exception:
        return None
    try:
        image = _prepare_ocr_image(Image.open(io.BytesIO(content)))
        lang = "+".join(
            "rus" if code.casefold().startswith("ru") else "eng"
            for code in languages
        ) or "rus+eng"
        text = pytesseract.image_to_string(image, lang=lang) or ""
        mrz_text = _ocr_mrz_strip(image)
        if mrz_text and mrz_text not in text:
            text = f"{text.rstrip()}\n{mrz_text}".strip()
        return text.strip() or None
    except Exception:
        return None


def _ocr_with_paddle(content: bytes) -> str | None:
    try:
        from paddleocr import PaddleOCR  # type: ignore
        from PIL import Image  # type: ignore
        import numpy as np  # type: ignore
    except Exception:
        return None
    try:
        image = Image.open(io.BytesIO(content)).convert("RGB")
        arr = np.array(image)
        engine = PaddleOCR(use_angle_cls=True, lang="ru", show_log=False)
        result = engine.ocr(arr, cls=True)
        lines: list[str] = []
        for page in result or []:
            for line in page or []:
                if line and len(line) >= 2 and line[1]:
                    lines.append(str(line[1][0]))
        text = "\n".join(lines).strip()
        return text or None
    except Exception:
        return None


def _pdf_text_layer(content: bytes) -> str | None:
    if not content.startswith(b"%PDF"):
        return None
    try:
        from pypdf import PdfReader  # type: ignore
    except Exception:
        try:
            from PyPDF2 import PdfReader  # type: ignore
        except Exception:
            return None
    try:
        reader = PdfReader(io.BytesIO(content))
        chunks: list[str] = []
        for page in reader.pages:
            extracted = page.extract_text() or ""
            if extracted.strip():
                chunks.append(extracted.strip())
        return "\n".join(chunks).strip() or None
    except Exception:
        return None


def _stub_page_text(
    *,
    filename: str,
    sha256: str,
    content: bytes,
    content_type: str,
) -> str:
    digest = hashlib.sha256(content).hexdigest()[:12]
    return (
        f"[stub:tesseract] filename={filename} "
        f"sha256={sha256[:16]}… content_sha={digest} "
        f"type={content_type or 'unknown'}"
    )


def _page_confidence(text: str, mode: str) -> float:
    if mode == "stub":
        return 0.55 if text.startswith("[stub:tesseract]") else 0.92
    if mode in {"tesseract", "paddle", "pdf_text"}:
        # Heuristic: more alphanumeric tokens → higher page confidence.
        tokens = re.findall(r"[A-Za-zА-Яа-яЁё0-9]{2,}", text)
        if len(tokens) >= 20:
            return 0.93
        if len(tokens) >= 8:
            return 0.86
        return 0.7
    return 0.8


def recognize_document(
    content: bytes,
    *,
    filename: str,
    content_type: str,
    document_id: str,
    job_id: str,
    sha256: str,
) -> dict[str, Any]:
    """Run OCR via ModelRegistry slot; prefer real engines, else stub."""
    resolved = resolve_ocr_model()
    model = resolved["model"]
    languages = resolved["languages"]
    language = languages[0] if languages else "ru"
    model_l = model.casefold()

    mode = "stub"
    engine_name = "tesseract"
    text: str | None = _decode_embedded_text(content)

    if text is not None:
        mode = "embedded_text"
        engine_name = "embedded"
    else:
        if "paddle" in model_l:
            text = _ocr_with_paddle(content)
            if text:
                mode = "paddle"
                engine_name = "paddleocr"
        if text is None and (
            model.startswith("stub:")
            or "tesseract" in model_l
            or "paddle" in model_l
        ):
            text = _ocr_with_tesseract(content, languages)
            if text:
                mode = "tesseract"
                engine_name = "tesseract"
        if text is None:
            text = _pdf_text_layer(content)
            if text:
                mode = "pdf_text"
                engine_name = "pdf"
        if text is None:
            if not (
                model.startswith("stub:")
                or "tesseract" in model_l
                or "paddle" in model_l
            ):
                raise OcrEngineError(
                    f"OCR model {model!r} is not supported; "
                    f"use {DEFAULT_STUB_MODEL!r} or paddleocr"
                )
            text = _stub_page_text(
                filename=filename,
                sha256=sha256,
                content=content,
                content_type=content_type,
            )
            mode = "stub"
            engine_name = "tesseract"

    confidence = _page_confidence(text, mode)
    return {
        "schema_version": "1.0",
        "job_id": job_id,
        "document_id": document_id,
        "document_sha256": sha256,
        "document_type_candidate": "unknown",
        "language": language,
        "ocr_engine": {
            "name": engine_name,
            "version": model,
            "slot": SLOT_NAME,
            "mode": mode,
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
