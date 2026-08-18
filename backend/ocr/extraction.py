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


_NAME_TOKEN = r"[A-ZА-ЯЁ][A-ZА-ЯЁa-zа-яё\-']{1,40}"
_GEO_WORDS = frozenset(
    {
        "ГОРОД",
        "Г",
        "ОБЛ",
        "ОБЛАСТЬ",
        "РЕСП",
        "РЕСПУБЛИКА",
        "КРАЙ",
        "РАЙОН",
        "СЕЛО",
        "ДЕР",
        "ДЕРЕВНЯ",
        "ПОС",
        "ПОСЁЛОК",
        "ПОСЕЛОК",
        "СТАНЦИЯ",
        "МОСКВА",
        "САНКТ",
        "ПЕТЕРБУРГ",
        "РОССИЯ",
        "РОССИЙСКАЯ",
        "ФЕДЕРАЦИЯ",
        "PASSPORT",
        "ПАСПОРТ",
        "МУЖ",
        "ЖЕН",
        "MALE",
        "FEMALE",
    }
)


def _label_value(
    text: str,
    labels: tuple[str, ...],
    *,
    pattern: str,
    confidence: float = 0.9,
) -> FieldValue | None:
    """Match `Label: value` on one line or `Label` / value on the next line."""
    for label in labels:
        same_line = re.compile(
            rf"(?im)(?:^|\n)\s*{re.escape(label)}\s*[:\-–]?\s*({pattern})\s*(?:\n|$)",
        )
        match = same_line.search(text)
        if match:
            return _field(match.group(1), confidence, source=f"label:{label}")
        next_line = re.compile(
            rf"(?im)(?:^|\n)\s*{re.escape(label)}\s*[:\-–]?\s*\n\s*({pattern})\s*(?:\n|$)",
        )
        match = next_line.search(text)
        if match:
            return _field(
                match.group(1),
                confidence - 0.03,
                source=f"label_nl:{label}",
            )
    return None


def _is_geo_or_junk_name(value: str) -> bool:
    tokens = [part for part in re.split(r"\s+", value.strip()) if part]
    if not tokens:
        return True
    upper = [token.casefold().replace("ё", "е").upper() for token in tokens]
    if any(token in _GEO_WORDS for token in upper):
        return True
    if len(tokens) == 1 and tokens[0].upper() in _GEO_WORDS:
        return True
    return False


def _normalize_date(raw: str) -> str:
    return raw.replace("/", ".").replace("-", ".")


def extract_passport_fields(text: str) -> dict[str, FieldValue]:
    fields: dict[str, FieldValue] = {}
    normalized = text.replace("\r\n", "\n")

    surname = _label_value(
        normalized,
        ("Фамилия", "Surname", "Family name"),
        pattern=_NAME_TOKEN,
        confidence=0.94,
    )
    name = _label_value(
        normalized,
        ("Имя", "Name", "Given name"),
        pattern=_NAME_TOKEN,
        confidence=0.93,
    )
    patronymic = _label_value(
        normalized,
        ("Отчество", "Patronymic", "Middle name"),
        pattern=_NAME_TOKEN,
        confidence=0.91,
    )

    # Drop OCR garbage that matched labels incorrectly.
    if surname and _is_geo_or_junk_name(str(surname["value"])):
        surname = None
    if name and _is_geo_or_junk_name(str(name["value"])):
        name = None
    if patronymic and _is_geo_or_junk_name(str(patronymic["value"])):
        patronymic = None

    fio = _label_value(
        normalized,
        ("ФИО", "Full name", "Ф.И.О."),
        pattern=rf"{_NAME_TOKEN}(?:\s+{_NAME_TOKEN}){{1,2}}",
        confidence=0.96,
    )
    if fio and _is_geo_or_junk_name(str(fio["value"])):
        fio = None

    if fio:
        fields["full_name"] = fio
    elif surname and name:
        parts = [str(surname["value"]), str(name["value"])]
        if patronymic:
            parts.append(str(patronymic["value"]))
        conf = min(
            float(surname["confidence"]),
            float(name["confidence"]),
            float(patronymic["confidence"]) if patronymic else 1.0,
        )
        fields["full_name"] = _field(" ".join(parts), conf, source="compose")

    if surname:
        fields["surname"] = surname
    if name:
        fields["given_name"] = name
    if patronymic:
        fields["patronymic"] = patronymic

    # RF passport: "45 11 532704" / "4511 532704"; BY: "PD 0000000"
    rf_id = re.search(
        r"(?m)(?<![\d])(\d{2})\s*(\d{2})\s+(\d{6})(?!\d)",
        normalized,
    )
    by_id = re.search(
        r"(?i)\b([A-ZА-Я]{2})\s*[-–]?\s*(\d{7})\b",
        normalized,
    )
    series = _label_value(
        normalized,
        ("Серия", "Series", "Серия паспорта"),
        pattern=r"(?:\d{2}\s*\d{2}|[A-ZА-Я]{2})",
        confidence=0.92,
    )
    number = _label_value(
        normalized,
        ("Номер", "Number", "№", "N"),
        pattern=r"\d{6,7}",
        confidence=0.9,
    )
    if rf_id:
        series = series or _field(
            f"{rf_id.group(1)} {rf_id.group(2)}",
            0.9,
            source="rf_id",
        )
        number = number or _field(rf_id.group(3), 0.9, source="rf_id")
    elif by_id:
        series = series or _field(by_id.group(1).upper(), 0.8, source="by_id")
        number = number or _field(by_id.group(2), 0.8, source="by_id")
    if series:
        # Normalize RF series to "45 11"
        series_val = re.sub(r"\s+", " ", str(series["value"]).strip())
        compact = series_val.replace(" ", "")
        if re.fullmatch(r"\d{4}", compact):
            series = _field(
                f"{compact[:2]} {compact[2:]}",
                float(series["confidence"]),
                source=str(series.get("source") or "regex"),
            )
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
            issue_date = _field(
                _normalize_date(date_match.group(1)),
                0.72,
                source="proximity",
            )
    birth_date = _label_value(
        normalized,
        ("Дата рождения", "Date of birth", "Birth", "Рождения"),
        pattern=r"\d{2}[./-]\d{2}[./-]\d{4}|\d{4}-\d{2}-\d{2}",
        confidence=0.9,
    )
    if birth_date:
        fields["birth_date"] = _field(
            _normalize_date(str(birth_date["value"])),
            float(birth_date["confidence"]),
            source=str(birth_date.get("source") or "regex"),
        )
    if issue_date:
        fields["issue_date"] = _field(
            _normalize_date(str(issue_date["value"])),
            float(issue_date["confidence"]),
            source=str(issue_date.get("source") or "regex"),
        )

    # Free-form FIO only when labels failed — never take geo lines.
    if "full_name" not in fields:
        for match in re.finditer(
            rf"(?m)^\s*({_NAME_TOKEN}(?:\s+{_NAME_TOKEN}){{1,2}})\s*$",
            normalized,
        ):
            candidate = match.group(1)
            if _is_geo_or_junk_name(candidate):
                continue
            # Prefer 3-token FIO (surname + name + patronymic).
            token_count = len(candidate.split())
            conf = 0.7 if token_count >= 3 else 0.58
            fields["full_name"] = _field(candidate, conf, source="caps_line")
            if token_count >= 3:
                break

    if "issue_date" not in fields and "birth_date" not in fields:
        any_date = re.search(
            r"\b(\d{2})[./-](\d{2})[./-](\d{4})\b",
            normalized,
        )
        if any_date:
            fields["issue_date"] = _field(
                f"{any_date.group(1)}.{any_date.group(2)}.{any_date.group(3)}",
                0.45,
                source="any_date",
            )

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
