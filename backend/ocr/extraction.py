"""Deterministic field extraction from OCR text (FR-OCR-13).

Works without an LLM: regex + label heuristics per document type.
Confidence is estimated from match strength / label proximity.
"""

from __future__ import annotations

import re
from typing import Any, Mapping

FieldValue = dict[str, Any]


def _field(value: str, confidence: float, *, source: str = "regex") -> FieldValue:
    return {
        "value": value.strip(),
        "confidence": round(max(0.0, min(1.0, confidence)), 4),
        "source": source,
    }


def _label_value(
    text: str,
    labels: tuple[str, ...],
    *,
    pattern: str,
    confidence: float = 0.9,
) -> FieldValue | None:
    for label in labels:
        rx = re.compile(
            rf"(?im)(?:^|\n)\s*{re.escape(label)}\s*[:\-–]?\s*({pattern})\s*(?:\n|$)",
        )
        match = rx.search(text)
        if match:
            return _field(match.group(1), confidence, source=f"label:{label}")
    return None


def extract_passport_fields(text: str) -> dict[str, FieldValue]:
    fields: dict[str, FieldValue] = {}
    normalized = text.replace("\r\n", "\n")

    surname = _label_value(
        normalized,
        ("Фамилия", "Surname", "Family name"),
        pattern=r"[A-ZА-ЯЁ][A-ZА-ЯЁa-zа-яё\-']{1,60}",
        confidence=0.94,
    )
    name = _label_value(
        normalized,
        ("Имя", "Name", "Given name"),
        pattern=r"[A-ZА-ЯЁ][A-ZА-ЯЁa-zа-яё\-']{1,60}",
        confidence=0.93,
    )
    patronymic = _label_value(
        normalized,
        ("Отчество", "Patronymic", "Middle name"),
        pattern=r"[A-ZА-ЯЁ][A-ZА-ЯЁa-zа-яё\-']{1,60}",
        confidence=0.91,
    )

    fio = _label_value(
        normalized,
        ("ФИО", "Full name", "Ф.И.О."),
        pattern=r"[A-ZА-ЯЁ][A-ZА-ЯЁa-zа-яё\-\s']{5,180}",
        confidence=0.96,
    )
    if fio:
        fields["full_name"] = fio
    elif surname and name:
        parts = [surname["value"], name["value"]]
        if patronymic:
            parts.append(patronymic["value"])
        conf = min(
            float(surname["confidence"]),
            float(name["confidence"]),
            float(patronymic["confidence"]) if patronymic else 1.0,
        )
        fields["full_name"] = _field(" ".join(parts), conf, source="compose")
    else:
        # Free-form line after PASSPORT marker.
        match = re.search(
            r"(?im)(?:паспорт|passport).{0,40}\n\s*([A-ZА-ЯЁ][A-ZА-ЯЁa-zа-яё\-]+"
            r"(?:\s+[A-ZА-ЯЁ][A-ZА-ЯЁa-zа-яё\-]+){1,3})\s*$",
            normalized,
        )
        if match:
            fields["full_name"] = _field(match.group(1), 0.78, source="proximity")

    if surname:
        fields["surname"] = surname
    if name:
        fields["given_name"] = name
    if patronymic:
        fields["patronymic"] = patronymic

    series = _label_value(
        normalized,
        ("Серия", "Series", "Серия паспорта"),
        pattern=r"[A-ZА-Я]{2}",
        confidence=0.92,
    )
    number = _label_value(
        normalized,
        ("Номер", "Number", "№", "N"),
        pattern=r"\d{7}",
        confidence=0.9,
    )
    if not series or not number:
        combo = re.search(
            r"(?im)(?:серия|series)?\s*([A-ZА-Я]{2})\s*[№#N]?\s*(\d{7})\b",
            normalized,
        )
        if combo:
            series = series or _field(combo.group(1), 0.86, source="combo")
            number = number or _field(combo.group(2), 0.86, source="combo")
    if series:
        fields["series"] = series
    if number:
        fields["number"] = number

    issue_date = _label_value(
        normalized,
        ("Дата выдачи", "Date of issue", "Issued", "Выдан"),
        pattern=r"\d{2}[./-]\d{2}[./-]\d{4}|\d{4}-\d{2}-\d{2}",
        confidence=0.9,
    )
    if not issue_date:
        date_match = re.search(
            r"(?im)(?:выдач|issued).{0,40}?(\d{2}[./-]\d{2}[./-]\d{4})",
            normalized,
        )
        if date_match:
            raw = date_match.group(1)
            issue_date = _field(
                raw.replace("/", ".").replace("-", "."),
                0.72,
                source="proximity",
            )
    if issue_date:
        value = str(issue_date["value"])
        if re.fullmatch(r"\d{2}[./-]\d{2}[./-]\d{4}", value):
            issue_date = _field(
                value.replace("/", ".").replace("-", "."),
                float(issue_date["confidence"]),
                source=str(issue_date.get("source") or "regex"),
            )
        fields["issue_date"] = issue_date

    return fields


def extract_payment_order_fields(text: str) -> dict[str, FieldValue]:
    fields: dict[str, FieldValue] = {}
    normalized = text.replace("\r\n", "\n")

    doc_no = _label_value(
        normalized,
        ("Номер", "№", "Document number", "Платёжное поручение"),
        pattern=r"\d{1,10}",
        confidence=0.88,
    )
    if not doc_no:
        match = re.search(r"(?im)payment order\s*#?\s*(\d{1,10})", normalized)
        if match:
            doc_no = _field(match.group(1), 0.8, source="proximity")
    if doc_no:
        fields["document_number"] = doc_no

    date = _label_value(
        normalized,
        ("Дата", "Date"),
        pattern=r"\d{2}[./-]\d{2}[./-]\d{4}|\d{4}-\d{2}-\d{2}",
        confidence=0.85,
    )
    if date:
        fields["date"] = date

    payer = _label_value(
        normalized,
        ("Плательщик", "Payer"),
        pattern=r".{2,120}",
        confidence=0.84,
    )
    if payer:
        fields["payer"] = payer

    beneficiary = _label_value(
        normalized,
        ("Получатель", "Beneficiary"),
        pattern=r".{2,120}",
        confidence=0.84,
    )
    if beneficiary:
        fields["beneficiary"] = beneficiary

    amount = _label_value(
        normalized,
        ("Сумма", "Amount"),
        pattern=r"[\d\s]+[.,]\d{2}",
        confidence=0.9,
    )
    if not amount:
        match = re.search(r"(?im)amount\s*:\s*([\d\s]+[.,]\d{2})", normalized)
        if match:
            amount = _field(match.group(1), 0.82, source="proximity")
    if amount:
        fields["amount"] = amount

    purpose = _label_value(
        normalized,
        ("Назначение", "Purpose"),
        pattern=r".{3,200}",
        confidence=0.8,
    )
    if purpose:
        fields["purpose"] = purpose

    currency = _label_value(
        normalized,
        ("Валюта", "Currency"),
        pattern=r"BYN|USD|EUR|RUB",
        confidence=0.95,
    )
    if not currency:
        match = re.search(r"\b(BYN|USD|EUR|RUB)\b", normalized, re.I)
        if match:
            currency = _field(match.group(1).upper(), 0.88, source="token")
    if currency:
        fields["currency"] = currency

    return fields


_EXTRACTORS = {
    "passport": extract_passport_fields,
    "payment_order": extract_payment_order_fields,
}


def detect_document_type(text: str, filename: str = "") -> str:
    hay = f"{filename}\n{text}".casefold()
    if any(token in hay for token in ("паспорт", "passport", "удостоверени")):
        return "passport"
    if any(
        token in hay
        for token in ("платёжн", "платежн", "payment order", "поручен")
    ):
        return "payment_order"
    if any(token in hay for token in ("выписк", "statement", "account")):
        return "account_statement"
    if any(token in hay for token in ("кредитн", "loan agreement")):
        return "loan_agreement"
    if any(token in hay for token in ("квитанц", "receipt")):
        return "payment_receipt"
    if any(token in hay for token in ("заявлен", "application", "анкет")):
        return "banking_application"
    return "unknown"


def extract_fields(
    text: str,
    *,
    document_type: str | None = None,
    filename: str = "",
) -> tuple[str, dict[str, FieldValue]]:
    doc_type = document_type or detect_document_type(text, filename)
    if doc_type == "unknown":
        doc_type = detect_document_type(text, filename)
    extractor = _EXTRACTORS.get(doc_type)
    if extractor is None:
        return doc_type, {}
    return doc_type, extractor(text)


def fields_as_plain(fields: Mapping[str, FieldValue]) -> dict[str, Any]:
    """Flatten `{value, confidence}` for validators that accept either form."""
    plain: dict[str, Any] = {}
    for key, payload in fields.items():
        if isinstance(payload, Mapping) and "value" in payload:
            plain[key] = payload
        else:
            plain[key] = payload
    return dict(plain)
