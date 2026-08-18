"""OCR text → structured fields via extractor + ModelGateway docs_ocr."""

from __future__ import annotations

import json
import re
from typing import Any, Mapping

from ocr.extraction import extract_fields, fields_as_plain


def _parse_json_content(content: str) -> dict[str, Any] | None:
    text = (content or "").strip()
    if not text:
        return None
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.S)
        if not match:
            return None
        try:
            payload = json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
    return payload if isinstance(payload, dict) else None


def _merge_field_maps(
    primary: Mapping[str, Any],
    secondary: Mapping[str, Any],
) -> dict[str, Any]:
    merged = dict(primary)
    for key, value in secondary.items():
        if key not in merged:
            merged[key] = value
            continue
        left = merged[key]
        right = value
        left_conf = (
            float(left.get("confidence") or 0)
            if isinstance(left, Mapping)
            else 0.0
        )
        right_conf = (
            float(right.get("confidence") or 0)
            if isinstance(right, Mapping)
            else 0.0
        )
        if right_conf > left_conf:
            merged[key] = right
    return merged


def structure_document(
    ocr_text: str,
    *,
    filename: str = "",
    document_type_hint: str | None = None,
    field_schema: Mapping[str, Any] | None = None,
    use_gateway: bool = True,
) -> dict[str, Any]:
    """Return document_type + fields(+confidence) + optional LLM proposal."""
    doc_type, extracted = extract_fields(
        ocr_text,
        document_type=document_type_hint,
        filename=filename,
    )
    llm_proposal: dict[str, Any] | None = None
    llm_fields: dict[str, Any] = {}

    if use_gateway:
        try:
            from core.model_gateway import ModelGateway

            schema_hint = field_schema or {}
            user_payload = {
                "filename": filename,
                "document_type_hint": doc_type,
                "ocr_text": ocr_text,
                "field_schema": schema_hint,
            }
            gateway = ModelGateway.from_registry()
            completion = gateway.chat(
                "docs_ocr",
                [
                    {
                        "role": "system",
                        "content": (
                            "Extract structured document fields as JSON with "
                            "document_type and fields map of "
                            "{value, confidence}."
                        ),
                    },
                    {
                        "role": "user",
                        "content": json.dumps(
                            user_payload,
                            ensure_ascii=False,
                        ),
                    },
                ],
            )
            content = (
                completion.get("choices", [{}])[0]
                .get("message", {})
                .get("content")
            )
            if isinstance(content, str):
                llm_proposal = _parse_json_content(content)
                if llm_proposal:
                    proposed_type = str(
                        llm_proposal.get("document_type") or ""
                    ).strip()
                    if proposed_type and proposed_type != "unknown":
                        doc_type = proposed_type
                    raw_fields = llm_proposal.get("fields") or {}
                    if isinstance(raw_fields, Mapping):
                        llm_fields = dict(raw_fields)
        except Exception:
            # Structuring must degrade to deterministic extractor.
            llm_proposal = None

    fields = _merge_field_maps(fields_as_plain(extracted), llm_fields)
    return {
        "document_type": doc_type,
        "fields": fields,
        "extractor_fields": fields_as_plain(extracted),
        "llm_proposal": llm_proposal,
    }
