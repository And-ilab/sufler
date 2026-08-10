"""Ready-made report catalogue for II.6 FR-RPT-CC (demo datasets)."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any

from reports.cc_analytics import CHANNEL_ONLINE_CHAT, CHANNEL_TELEPHONY, parse_analytics_filters


REPORT_TYPES = (
    {
        "id": "usefulness",
        "fr": "FR-RPT-CC-08",
        "label": "Полезность подсказок LLM",
        "default_view": "table",
    },
    {
        "id": "relevance",
        "fr": "FR-RPT-CC-07",
        "label": "Релевантность по каналам и тематикам",
        "default_view": "bar",
    },
    {
        "id": "correctness",
        "fr": "FR-RPT-CC-04",
        "label": "Корректность: LLM vs ответ оператора",
        "default_view": "bar",
    },
    {
        "id": "performance",
        "fr": "FR-RPT-CC-05",
        "label": "Производительность (p95, AHT)",
        "default_view": "bar",
    },
    {
        "id": "errors",
        "fr": "FR-RPT-CC-09",
        "label": "Ошибки LLM: причины и примеры",
        "default_view": "table",
    },
    {
        "id": "topics",
        "fr": "FR-RPT-CC-13",
        "label": "Закономерности по тематике",
        "default_view": "table",
    },
    {
        "id": "repeats",
        "fr": "FR-RPT-CC-12",
        "label": "Повторные обращения",
        "default_view": "table",
    },
    {
        "id": "executive",
        "fr": "FR-RPT-CC-11",
        "label": "Сводка для руководства",
        "default_view": "table",
    },
    {
        "id": "chat_history",
        "fr": "FR-RPT-CC-15",
        "label": "Диалоги онлайн-чата (из АРМ)",
        "default_view": "table",
    },
)


def _parse_filters(query: Any) -> dict[str, Any]:
    filters = parse_analytics_filters(query)
    report_id = (query.get("report") or "usefulness").strip()
    known = {item["id"] for item in REPORT_TYPES}
    if report_id not in known:
        report_id = "usefulness"
    filters["report"] = report_id
    return filters


def _chat_rows(date_from: date, date_to: date) -> list[dict[str, Any]]:
    try:
        from online_chat.models import Dialog
    except Exception:
        return []

    qs = Dialog.objects.filter(created_at__date__gte=date_from, created_at__date__lte=date_to)
    rows: list[dict[str, Any]] = []
    for dialog in qs.order_by("-updated_at")[:100]:
        rows.append(
            {
                "ref": dialog.ref_code(),
                "client": dialog.client_display_name(),
                "phone": dialog.client_phone or "—",
                "operator": dialog.operator_name or "—",
                "status": dialog.status,
                "topic": dialog.close_topic or "—",
                "channel": "online_chat",
                "created_at": dialog.created_at.isoformat(),
                "messages": dialog.messages.count(),
            }
        )
    return rows


def build_report_payload(query: Any) -> dict[str, Any]:
    filters = _parse_filters(query)
    date_from = date.fromisoformat(filters["date_from"])
    date_to = date.fromisoformat(filters["date_to"])
    report_id = filters["report"]
    meta = next(item for item in REPORT_TYPES if item["id"] == report_id)
    now = datetime.now(timezone.utc)

    relevance = [
        {"channel": "telephony", "topic": "Карты", "avg_relevance": 86.2, "answers": 420},
        {"channel": "telephony", "topic": "Кредиты", "avg_relevance": 79.4, "answers": 310},
        {"channel": "online_chat", "topic": "ЕРИП", "avg_relevance": 91.1, "answers": 280},
        {"channel": "online_chat", "topic": "Лимиты ATM", "avg_relevance": 72.5, "answers": 190},
        {"channel": "online_chat", "topic": "Карты и счета", "avg_relevance": 88.0, "answers": 240},
    ]
    if filters["channel"] == CHANNEL_TELEPHONY:
        relevance = [row for row in relevance if row["channel"] == CHANNEL_TELEPHONY]
    elif filters["channel"] == CHANNEL_ONLINE_CHAT:
        relevance = [row for row in relevance if row["channel"] == CHANNEL_ONLINE_CHAT]

    correctness = [
        {"label": "Совпало с ответом оператора", "value": 61, "pct": 61.0},
        {"label": "Частично использовано", "value": 22, "pct": 22.0},
        {"label": "Не использовано", "value": 12, "pct": 12.0},
        {"label": "Оценено как неверно", "value": 5, "pct": 5.0},
    ]
    performance = [
        {"date": (date_to - timedelta(days=i)).isoformat(), "p95_ms": 420 + i * 35, "aht_sec": 210 + i * 8}
        for i in range(6, -1, -1)
        if date_from <= date_to - timedelta(days=i) <= date_to
    ]
    errors = [
        {
            "reason": "Нет статьи СУЗ",
            "count": 18,
            "example": "Клиент: «как повысить лимит ATM ночью?»",
            "channel": "online_chat",
        },
        {
            "reason": "Неполный сценарий",
            "count": 11,
            "example": "Клиент: «блокировка карты через приложение»",
            "channel": "telephony",
        },
        {
            "reason": "Низкая релевантность RAG",
            "count": 9,
            "example": "Клиент: «комиссия за перевод юрлицу»",
            "channel": "online_chat",
        },
    ]
    topics = [
        {"topic": "Лимиты ATM", "dialogs": 96, "growth_pct": 18.0},
        {"topic": "Карты и счета", "dialogs": 84, "growth_pct": 4.2},
        {"topic": "ЕРИП", "dialogs": 71, "growth_pct": -2.1},
        {"topic": "Кредиты", "dialogs": 55, "growth_pct": 7.5},
    ]
    repeats = [
        {"client": "+37529***12", "topic": "Лимиты ATM", "repeats": 3, "channels": "чат→телефон"},
        {"client": "+37533***88", "topic": "Карты", "repeats": 2, "channels": "чат"},
        {"client": "+37544***01", "topic": "Кредиты", "repeats": 2, "channels": "телефон→чат"},
    ]
    executive = [
        {"metric": "Обращений всего", "telephony": 1240, "online_chat": 980, "total": 2220},
        {"metric": "Средняя релевантность LLM, %", "telephony": 84.1, "online_chat": 87.6, "total": 85.7},
        {"metric": "Полезность «воспользовался», %", "telephony": 68.0, "online_chat": 71.5, "total": 69.6},
        {"metric": "p95 подсказки, мс", "telephony": 1450, "online_chat": 920, "total": 1380},
        {"metric": "CSAT (демо)", "telephony": 4.3, "online_chat": 4.5, "total": 4.4},
    ]
    chat_rows = _chat_rows(date_from, date_to)

    usefulness = [
        {
            "channel": CHANNEL_TELEPHONY,
            "label": "Телефония",
            "useful_pct": 68.0,
            "incomplete_pct": 19.0,
            "unused_pct": 13.0,
            "sessions": 1240,
        },
        {
            "channel": CHANNEL_ONLINE_CHAT,
            "label": "Онлайн-чат",
            "useful_pct": 71.5,
            "incomplete_pct": 16.0,
            "unused_pct": 12.5,
            "sessions": 980,
        },
    ]

    tables: dict[str, list[dict[str, Any]]] = {
        "usefulness": usefulness,
        "relevance": relevance,
        "correctness": correctness,
        "performance": performance,
        "errors": errors,
        "topics": topics,
        "repeats": repeats,
        "executive": executive,
        "chat_history": chat_rows
        or [
            {
                "ref": "DEMO01",
                "client": "Анна К.",
                "phone": "+375291112233",
                "operator": "Иванов И.И.",
                "status": "closed",
                "topic": "Карты и счета",
                "channel": "online_chat",
                "created_at": now.isoformat(),
                "messages": 8,
            }
        ],
    }

    charts = {
        "relevance": [
            {"label": row["topic"], "value": row["avg_relevance"]} for row in relevance
        ],
        "correctness": [
            {"label": row["label"], "value": row["pct"]} for row in correctness
        ],
        "performance": [
            {"label": row["date"][5:], "value": row["p95_ms"]} for row in performance
        ],
        "topics": [{"label": row["topic"], "value": row["dialogs"]} for row in topics],
        "usefulness": [
            {"label": row["label"], "value": row["useful_pct"]} for row in usefulness
        ],
    }

    return {
        "filters": filters,
        "catalog": list(REPORT_TYPES),
        "report": meta,
        "rows": tables.get(report_id, []),
        "chart": charts.get(report_id, []),
        "summary": {
            "report_id": report_id,
            "rows": len(tables.get(report_id, [])),
            "period": f"{filters['date_from']} — {filters['date_to']}",
            "note": "Демо-данные LLM/КЦ; диалоги чата подмешиваются при наличии.",
        },
        "stub": report_id != "chat_history" or not chat_rows,
        "source": "II.6 demo catalogue",
        "alerts": [
            {
                "id": "sch-1",
                "title": "Ежедневный отчёт 08:00",
                "detail": "xlsx → аналитик КЦ",
                "enabled": True,
            },
            {
                "id": "sch-2",
                "title": "Порог релевантности < 75%",
                "detail": "email + дашборд",
                "enabled": True,
            },
        ],
    }


def list_builder_templates() -> dict[str, Any]:
    return {
        "templates": [
            {
                "id": "tpl-month",
                "name": "Сводка КЦ — месяц",
                "metrics": ["dialogs_total", "sla_pct", "useful_pct", "p95_ms"],
                "filters": {"channel": "all", "period": "month"},
                "view_mode": "table",
            },
            {
                "id": "tpl-chat",
                "name": "Онлайн-чат — качество",
                "metrics": ["dialogs_total", "csat", "topics_top"],
                "filters": {"channel": "online_chat", "period": "week"},
                "view_mode": "bar",
            },
            {
                "id": "tpl-llm",
                "name": "LLM подсказки",
                "metrics": ["useful_pct", "relevance_avg", "incorrect_llm"],
                "filters": {"channel": "all", "period": "week"},
                "view_mode": "pie",
            },
        ],
        "metric_catalog": [
            {"id": "dialogs_total", "label": "Число диалогов"},
            {"id": "sla_pct", "label": "SLA, %"},
            {"id": "csat", "label": "CSAT"},
            {"id": "useful_pct", "label": "Полезность, %"},
            {"id": "relevance_avg", "label": "Средняя релевантность"},
            {"id": "incorrect_llm", "label": "Ошибки LLM"},
            {"id": "p95_ms", "label": "p95 подсказки, мс"},
            {"id": "topics_top", "label": "Топ тематик"},
            {"id": "aht_sec", "label": "AHT, с"},
        ],
        "stub": True,
    }


def preview_builder(body: dict[str, Any]) -> dict[str, Any]:
    metrics = body.get("metrics") or ["dialogs_total", "useful_pct"]
    view_mode = body.get("view_mode") or "table"
    name = body.get("name") or "Черновик отчёта"
    rows = [
        {"metric": metric, "value": 40 + idx * 7, "unit": "%"}
        for idx, metric in enumerate(metrics)
    ]
    return {
        "name": name,
        "view_mode": view_mode,
        "rows": rows,
        "chart": [{"label": str(row["metric"]), "value": row["value"]} for row in rows],
        "stub": True,
        "message": "Конструктор в демо-режиме: шаблон можно «сохранить» локально в UI.",
    }
