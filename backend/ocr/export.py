"""Export validated OCR payloads as JSON/CSV (IV.8 / FR-OCR-23 / DOC-T-08)."""

from __future__ import annotations

import csv
import io
import json
from typing import Any, Mapping

from ocr.validation import (
    STATUS_VALID,
    ValidationRequestError,
    ValidationResult,
    assert_downstream_ready,
)

EXPORT_JSON = "json"
EXPORT_CSV = "csv"
EXPORT_FORMATS = frozenset({EXPORT_JSON, EXPORT_CSV})


def normalize_export_format(value: str | None) -> str:
    fmt = (value or EXPORT_JSON).strip().lower()
    if fmt not in EXPORT_FORMATS:
        raise ValidationRequestError("format must be json|csv")
    return fmt


def export_filename(result: ValidationResult, export_format: str) -> str:
    doc = result.document_id or "document"
    job = result.job_id or "adhoc"
    return f"ocr-validated_{result.document_type}_{doc}_{job}.{export_format}"


def build_json_export(
    result: ValidationResult,
    *,
    require_valid: bool = True,
) -> bytes:
    if require_valid:
        assert_downstream_ready(result)
    payload = result.as_dict()
    return json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")


def build_csv_export(
    result: ValidationResult,
    *,
    require_valid: bool = True,
) -> bytes:
    if require_valid:
        assert_downstream_ready(result)
    buffer = io.StringIO()
    buffer.write("\ufeff")
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "document_type",
            "status",
            "field",
            "value",
            "job_id",
            "document_id",
            "template_version",
            "validator_version",
        ]
    )
    for name, value in result.normalized_fields.items():
        writer.writerow(
            [
                result.document_type,
                result.status,
                name,
                value,
                result.job_id or "",
                result.document_id or "",
                result.template_version,
                result.validator_version,
            ]
        )
    return buffer.getvalue().encode("utf-8")


def build_export(
    result: ValidationResult,
    export_format: str,
    *,
    require_valid: bool = True,
) -> tuple[bytes, str]:
    fmt = normalize_export_format(export_format)
    if fmt == EXPORT_CSV:
        payload = build_csv_export(result, require_valid=require_valid)
        content_type = "text/csv; charset=utf-8"
    else:
        payload = build_json_export(result, require_valid=require_valid)
        content_type = "application/json; charset=utf-8"
    return payload, content_type


def validation_result_from_mapping(payload: Mapping[str, Any]) -> ValidationResult:
    """Rebuild ValidationResult from a previously validated dict (tests/API)."""
    from ocr.validation import FieldAnomaly

    validation = payload.get("validation") or {}
    anomalies = [
        FieldAnomaly(
            str(item.get("field") or ""),
            str(item.get("code") or ""),
            str(item.get("message") or ""),
        )
        for item in (validation.get("anomalies") or [])
        if isinstance(item, Mapping)
    ]
    return ValidationResult(
        document_type=str(payload.get("document_type") or ""),
        status=str(payload.get("status") or STATUS_VALID),
        fields=dict(payload.get("raw_fields") or payload.get("fields") or {}),
        normalized_fields=dict(payload.get("fields") or {}),
        missing_required_fields=list(
            validation.get("missing_required_fields") or []
        ),
        anomalies=anomalies,
        rejected_fields=list(payload.get("rejected_fields") or []),
        template_version=str(validation.get("template_version") or "1"),
        validator_version=str(validation.get("validator_version") or "1.0"),
        job_id=payload.get("job_id"),
        document_id=payload.get("document_id"),
        document_sha256=payload.get("document_sha256"),
    )
