"""Stub CC analytics and export for FR-RPT-CC / II.6 (UI workflow)."""

from __future__ import annotations

import csv
import io
import zipfile
from datetime import date, datetime, timedelta, timezone
from typing import Any
from xml.sax.saxutils import escape

CHANNEL_ALL = ""
CHANNEL_TELEPHONY = "telephony"
CHANNEL_ONLINE_CHAT = "online_chat"
CHANNELS = frozenset({CHANNEL_TELEPHONY, CHANNEL_ONLINE_CHAT})

EXPORT_CSV = "csv"
EXPORT_XLSX = "xlsx"
EXPORT_PDF = "pdf"
EXPORT_FORMATS = frozenset({EXPORT_CSV, EXPORT_XLSX, EXPORT_PDF})


class CcAnalyticsError(ValueError):
    """Invalid analytics filter or export request."""


def _parse_date(value: str | None, field: str) -> date | None:
    if value in (None, ""):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise CcAnalyticsError(f"{field} must be YYYY-MM-DD") from exc


def parse_analytics_filters(query: Any) -> dict[str, Any]:
    today = datetime.now(timezone.utc).date()
    date_from = _parse_date(query.get("date_from"), "date_from") or (
        today - timedelta(days=13)
    )
    date_to = _parse_date(query.get("date_to"), "date_to") or today
    if date_from > date_to:
        raise CcAnalyticsError("date_from must be <= date_to")

    channel = (query.get("channel") or CHANNEL_ALL).strip()
    if channel and channel not in CHANNELS:
        raise CcAnalyticsError("channel must be telephony|online_chat")

    export_format = (query.get("format") or EXPORT_CSV).strip().lower()
    if export_format not in EXPORT_FORMATS:
        raise CcAnalyticsError("format must be csv|xlsx|pdf")

    return {
        "date_from": date_from.isoformat(),
        "date_to": date_to.isoformat(),
        "channel": channel,
        "format": export_format,
    }


def _chat_overlay_rows(
    date_from: date, date_to: date, channel: str
) -> list[dict[str, Any]]:
    """Fold online_chat dialogs into daily analytics when present."""
    if channel and channel != CHANNEL_ONLINE_CHAT:
        return []
    try:
        from online_chat.models import Dialog as ChatDialog
    except Exception:
        return []

    qs = ChatDialog.objects.filter(
        created_at__date__gte=date_from,
        created_at__date__lte=date_to,
    )
    by_day: dict[str, list[Any]] = {}
    for dialog in qs.iterator():
        key = dialog.created_at.date().isoformat()
        by_day.setdefault(key, []).append(dialog)

    rows: list[dict[str, Any]] = []
    for day, dialogs in sorted(by_day.items()):
        operators = {d.operator_name or "—" for d in dialogs}
        closed = sum(1 for d in dialogs if d.status == ChatDialog.Status.CLOSED)
        rows.append(
            {
                "date": day,
                "channel": CHANNEL_ONLINE_CHAT,
                "operator": ", ".join(sorted(operators))[:80] or "—",
                "sessions": len(dialogs),
                "recognized_pct": 100.0,
                "avg_confidence": 1.0,
                "useful_pct": 70.0 if closed else 50.0,
                "incomplete_pct": 15.0,
                "unused_pct": 15.0,
                "incorrect_llm": 0,
                "hint_latency_p95_ms": 900,
                "aht_sec": 240,
            }
        )
    return rows


def _seed_rows(date_from: date, date_to: date, channel: str) -> list[dict[str, Any]]:
    """Deterministic stub rows for the selected period."""
    rows: list[dict[str, Any]] = []
    day = date_from
    index = 0
    while day <= date_to:
        for ch, operator in (
            (CHANNEL_TELEPHONY, "Иванова А."),
            (CHANNEL_ONLINE_CHAT, "Петров С."),
        ):
            if channel and ch != channel:
                continue
            recognized = 88 + (index % 8)
            useful = 62 + (index % 12)
            incomplete = 18 + (index % 5)
            unused = max(0, 100 - useful - incomplete)
            latency_p95 = 420 + (index % 9) * 15
            aht_sec = 210 + (index % 7) * 12
            rows.append(
                {
                    "date": day.isoformat(),
                    "channel": ch,
                    "operator": operator,
                    "sessions": 40 + (index % 20),
                    "recognized_pct": recognized,
                    "avg_confidence": round(0.78 + (index % 10) * 0.015, 3),
                    "useful_pct": useful,
                    "incomplete_pct": incomplete,
                    "unused_pct": unused,
                    "incorrect_llm": 2 + (index % 4),
                    "hint_latency_p95_ms": latency_p95,
                    "aht_sec": aht_sec,
                }
            )
            index += 1
        day += timedelta(days=1)
    return rows


def _asr_series(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_date: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_date.setdefault(row["date"], []).append(row)
    series: list[dict[str, Any]] = []
    for day, group in sorted(by_date.items()):
        sessions = sum(item["sessions"] for item in group)
        recognized = round(
            sum(item["recognized_pct"] * item["sessions"] for item in group) / sessions,
            1,
        )
        confidence = round(
            sum(item["avg_confidence"] * item["sessions"] for item in group) / sessions,
            3,
        )
        series.append(
            {
                "date": day,
                "recognized_pct": recognized,
                "avg_confidence": confidence,
                "sessions": sessions,
            }
        )
    return series


def build_analytics(filters: dict[str, Any]) -> dict[str, Any]:
    date_from = date.fromisoformat(filters["date_from"])
    date_to = date.fromisoformat(filters["date_to"])
    rows = _seed_rows(date_from, date_to, filters["channel"])
    chat_rows = _chat_overlay_rows(date_from, date_to, filters["channel"])
    if chat_rows:
        # Prefer live chat counts for overlapping online_chat days.
        chat_dates = {row["date"] for row in chat_rows}
        rows = [
            row
            for row in rows
            if not (row["channel"] == CHANNEL_ONLINE_CHAT and row["date"] in chat_dates)
        ]
        rows.extend(chat_rows)
        rows.sort(key=lambda item: (item["date"], item["channel"]))
    asr_quality = _asr_series(rows)

    total_sessions = sum(row["sessions"] for row in rows) or 1
    summary = {
        "sessions": sum(row["sessions"] for row in rows),
        "recognized_pct": round(
            sum(row["recognized_pct"] * row["sessions"] for row in rows) / total_sessions,
            1,
        ),
        "avg_confidence": round(
            sum(row["avg_confidence"] * row["sessions"] for row in rows) / total_sessions,
            3,
        ),
        "useful_pct": round(
            sum(row["useful_pct"] * row["sessions"] for row in rows) / total_sessions,
            1,
        ),
        "incorrect_llm": sum(row["incorrect_llm"] for row in rows),
        "hint_latency_p95_ms": max(
            (row["hint_latency_p95_ms"] for row in rows), default=0
        ),
    }

    usefulness = [
        {
            "channel": ch,
            "label": "Телефония" if ch == CHANNEL_TELEPHONY else "Онлайн-чат",
            "useful_pct": round(
                sum(r["useful_pct"] * r["sessions"] for r in group) / sessions,
                1,
            ),
            "incomplete_pct": round(
                sum(r["incomplete_pct"] * r["sessions"] for r in group) / sessions,
                1,
            ),
            "unused_pct": round(
                sum(r["unused_pct"] * r["sessions"] for r in group) / sessions,
                1,
            ),
            "sessions": sessions,
        }
        for ch in (CHANNEL_TELEPHONY, CHANNEL_ONLINE_CHAT)
        for group in [[r for r in rows if r["channel"] == ch]]
        for sessions in [sum(r["sessions"] for r in group) or 0]
        if sessions
    ]

    return {
        "filters": {
            "date_from": filters["date_from"],
            "date_to": filters["date_to"],
            "channel": filters["channel"],
        },
        "summary": summary,
        "rows": rows,
        "usefulness": usefulness,
        "asr_quality": asr_quality,
        "stub": not bool(chat_rows),
        "source": (
            "FR-RPT-CC · demo + online_chat overlay"
            if chat_rows
            else "FR-RPT-CC · II.6 demo analytics (нет LLM/КЦ)"
        ),
    }


_EXPORT_HEADERS = [
    "date",
    "channel",
    "operator",
    "sessions",
    "recognized_pct",
    "avg_confidence",
    "useful_pct",
    "incomplete_pct",
    "unused_pct",
    "incorrect_llm",
    "hint_latency_p95_ms",
    "aht_sec",
]


def build_csv_export(analytics: dict[str, Any]) -> bytes:
    buffer = io.StringIO()
    buffer.write("\ufeff")
    writer = csv.DictWriter(buffer, fieldnames=_EXPORT_HEADERS, extrasaction="ignore")
    writer.writeheader()
    for row in analytics["rows"]:
        writer.writerow(row)
    return buffer.getvalue().encode("utf-8")


def _sheet_xml(rows: list[list[str]]) -> str:
    lines = [
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">',
        "<sheetData>",
    ]
    for r_idx, row in enumerate(rows, start=1):
        lines.append(f'<row r="{r_idx}">')
        for c_idx, value in enumerate(row):
            col = chr(ord("A") + c_idx)
            cell_ref = f"{col}{r_idx}"
            safe = escape(value)
            lines.append(
                f'<c r="{cell_ref}" t="inlineStr"><is><t>{safe}</t></is></c>'
            )
        lines.append("</row>")
    lines.extend(["</sheetData>", "</worksheet>"])
    return "\n".join(lines)


def build_xlsx_export(analytics: dict[str, Any]) -> bytes:
    sheet_rows = [[header for header in _EXPORT_HEADERS]]
    for row in analytics["rows"]:
        sheet_rows.append([str(row.get(header, "")) for header in _EXPORT_HEADERS])

    content_types = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
</Types>
"""
    rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>
"""
    workbook = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
 xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets>
    <sheet name="CC analytics" sheetId="1" r:id="rId1"/>
  </sheets>
</workbook>
"""
    workbook_rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
</Relationships>
"""

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("_rels/.rels", rels)
        archive.writestr("xl/workbook.xml", workbook)
        archive.writestr("xl/_rels/workbook.xml.rels", workbook_rels)
        archive.writestr("xl/worksheets/sheet1.xml", _sheet_xml(sheet_rows))
    return buffer.getvalue()


def export_filename(filters: dict[str, Any], export_format: str) -> str:
    channel = filters["channel"] or "all"
    return (
        f"cc-analytics_{filters['date_from']}_{filters['date_to']}"
        f"_{channel}.{export_format}"
    )
