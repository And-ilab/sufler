"""Ready-made report catalogue for II.6 FR-RPT-CC (online-chat production data)."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable

from reports.cc_analytics import CHANNEL_ONLINE_CHAT, CcAnalyticsError, parse_analytics_filters
from reports.cc_chat_metrics import (
    builder_metric_value,
    report_chat_history,
    report_chat_offline,
    report_chat_operators,
    report_chat_period,
    report_chat_ratings,
    report_chat_sla,
    report_chat_topics,
    report_correctness,
    report_errors,
    report_executive,
    report_performance,
    report_relevance,
    report_repeats,
    report_usefulness,
)

REPORT_TYPES = (
    {
        "id": "chat-period",
        "fr": "FR-RPT-CC-11",
        "label": "Онлайн-чат: обращения за период",
        "default_view": "bar",
        "group": "Онлайн-чат",
    },
    {
        "id": "chat-sla",
        "fr": "FR-RPT-CC-03",
        "label": "SLA и время ожидания",
        "default_view": "bar",
        "group": "Онлайн-чат",
    },
    {
        "id": "chat-operators",
        "fr": "FR-RPT-CC-05",
        "label": "Нагрузка и эффективность операторов",
        "default_view": "table",
        "group": "Онлайн-чат",
    },
    {
        "id": "chat-ratings",
        "fr": "FR-RPT-CC-11",
        "label": "Оценки клиентов",
        "default_view": "pie",
        "group": "Онлайн-чат",
    },
    {
        "id": "chat-topics",
        "fr": "FR-RPT-CC-13",
        "label": "Тематики закрытия диалогов",
        "default_view": "pie",
        "group": "Онлайн-чат",
    },
    {
        "id": "chat-offline",
        "fr": "FR-RPT-CC-12",
        "label": "Необработанные и отказные обращения",
        "default_view": "pie",
        "group": "Онлайн-чат",
    },
    {
        "id": "chat_history",
        "fr": "FR-RPT-CC-15",
        "label": "Диалоги онлайн-чата (реестр)",
        "default_view": "table",
        "group": "Онлайн-чат",
    },
    {
        "id": "usefulness",
        "fr": "FR-RPT-CC-08",
        "label": "Полезность подсказок суфлёра",
        "default_view": "pie",
        "group": "Суфлёр / LLM",
    },
    {
        "id": "relevance",
        "fr": "FR-RPT-CC-07",
        "label": "Релевантность ответов",
        "default_view": "bar",
        "group": "Суфлёр / LLM",
    },
    {
        "id": "correctness",
        "fr": "FR-RPT-CC-04",
        "label": "Корректность: отметки оператора",
        "default_view": "pie",
        "group": "Суфлёр / LLM",
    },
    {
        "id": "performance",
        "fr": "FR-RPT-CC-05",
        "label": "Производительность (время ответа, AHT)",
        "default_view": "bar",
        "group": "Производительность",
    },
    {
        "id": "errors",
        "fr": "FR-RPT-CC-09",
        "label": "Неиспользованные подсказки",
        "default_view": "table",
        "group": "Суфлёр / LLM",
    },
    {
        "id": "topics",
        "fr": "FR-RPT-CC-13",
        "label": "Закономерности по тематике",
        "default_view": "table",
        "group": "Онлайн-чат",
    },
    {
        "id": "repeats",
        "fr": "FR-RPT-CC-12",
        "label": "Повторные обращения",
        "default_view": "table",
        "group": "Онлайн-чат",
    },
    {
        "id": "executive",
        "fr": "FR-RPT-CC-11",
        "label": "Сводка для руководства",
        "default_view": "table",
        "group": "Сводные",
    },
)

_BUILDERS: dict[str, Callable[..., dict[str, Any]]] = {
    "chat-period": report_chat_period,
    "chat-sla": report_chat_sla,
    "chat-operators": report_chat_operators,
    "chat-ratings": report_chat_ratings,
    "chat-topics": report_chat_topics,
    "chat-offline": report_chat_offline,
    "chat_history": report_chat_history,
    "usefulness": report_usefulness,
    "relevance": report_relevance,
    "correctness": report_correctness,
    "performance": report_performance,
    "errors": report_errors,
    "topics": report_chat_topics,
    "repeats": report_repeats,
    "executive": report_executive,
}


def _parse_filters(query: Any) -> dict[str, Any]:
    filters = parse_analytics_filters(query)
    report_id = (query.get("report") or "chat-period").strip()
    known = {item["id"] for item in REPORT_TYPES}
    if report_id not in known:
        # Aliases from older UI ids
        aliases = {
            "rpt-08": "usefulness",
            "rpt-02": "relevance",
            "rpt-07": "relevance",
            "rpt-04": "correctness",
            "rpt-05": "performance",
            "rpt-09": "errors",
            "rpt-13": "topics",
            "rpt-12": "repeats",
            "rpt-11": "executive",
            "rpt-10": "executive",
        }
        report_id = aliases.get(report_id, "chat-period")
    filters["report"] = report_id
    messenger = filters.get("messenger") or ""
    channel = filters.get("channel") or CHANNEL_ONLINE_CHAT
    if channel not in {CHANNEL_ONLINE_CHAT, "", "telephony"}:
        messenger = channel
    topic = str(query.get("topic") or "").strip()
    status = str(query.get("status") or query.get("dialogue_status") or "").strip()
    department = str(query.get("department") or "").strip()
    filters["messenger"] = messenger
    filters["topic"] = topic
    filters["status"] = status
    filters["department_id"] = department
    group_by = str(query.get("group_by") or "channel").strip().lower()
    if group_by not in {"", "none", "channel", "topic"}:
        group_by = "channel"
    filters["group_by"] = group_by or "channel"
    return filters


def build_report_payload(query: Any) -> dict[str, Any]:
    filters = _parse_filters(query)
    date_from = date.fromisoformat(filters["date_from"])
    date_to = date.fromisoformat(filters["date_to"])
    report_id = filters["report"]
    meta = next(item for item in REPORT_TYPES if item["id"] == report_id)
    builder = _BUILDERS[report_id]
    kwargs = {
        "messenger": filters.get("messenger") or "",
        "department_id": filters.get("department_id") or "",
        "topic": filters.get("topic") or "",
        "status": filters.get("status") or "",
    }
    # group_by applies only to relevance report; other builders reject unknown kwargs.
    if report_id == "relevance":
        kwargs["group_by"] = filters.get("group_by") or "channel"
    try:
        built = builder(date_from, date_to, **kwargs)
    except TypeError as exc:
        raise CcAnalyticsError(
            f"Не удалось построить отчёт «{meta.get('label') or report_id}»: {exc}"
        ) from exc
    rows = built.get("rows") or []
    chart = built.get("chart") or []
    summary = {
        "report_id": report_id,
        "rows": len(rows),
        "period": f"{filters['date_from']} — {filters['date_to']}",
        **(built.get("summary") or {}),
    }
    # Hide technical ids / advanced percentiles from KPI strip.
    summary.pop("p95_first_response_sec", None)
    summary.pop("p95_ms", None)
    return {
        "filters": filters,
        "catalog": list(REPORT_TYPES),
        "report": meta,
        "rows": rows,
        "chart": chart,
        "summary": summary,
        "stub": bool(built.get("stub")),
        "source": "Онлайн-чат",
        "alerts": [],
    }


def list_builder_templates(*, saved: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {
        "templates": [
            {
                "id": "tpl-chat-period-week",
                "name": "Онлайн-чат: обращения за неделю",
                "metrics": ["dialogs_total", "dialogs_closed", "avg_first_response_sec"],
                "filters": {"channel": "online_chat", "period": "week", "report": "chat-period"},
                "view_mode": "bar",
            },
            {
                "id": "tpl-chat-sla-week",
                "name": "Онлайн-чат: SLA и ожидание",
                "metrics": ["sla_pct", "avg_first_response_sec", "aht_sec"],
                "filters": {"channel": "online_chat", "period": "week", "report": "chat-sla"},
                "view_mode": "table",
            },
            {
                "id": "tpl-chat-operators-month",
                "name": "Онлайн-чат: операторы за месяц",
                "metrics": ["dialogs_total", "aht_sec", "avg_first_response_sec", "sla_pct"],
                "filters": {"channel": "online_chat", "period": "month", "report": "chat-operators"},
                "view_mode": "bar",
            },
            {
                "id": "tpl-chat-ratings-week",
                "name": "Онлайн-чат: оценки клиентов",
                "metrics": ["csat", "dialogs_closed", "dialogs_total"],
                "filters": {"channel": "online_chat", "period": "week", "report": "chat-ratings"},
                "view_mode": "pie",
            },
            {
                "id": "tpl-chat-topics-week",
                "name": "Онлайн-чат: тематики закрытия",
                "metrics": ["topics_top", "dialogs_closed", "dialogs_total"],
                "filters": {"channel": "online_chat", "period": "week", "report": "chat-topics"},
                "view_mode": "pie",
            },
            {
                "id": "tpl-chat-offline-week",
                "name": "Онлайн-чат: необработанные и офлайн",
                "metrics": ["dialogs_total", "dialogs_closed", "avg_first_response_sec"],
                "filters": {"channel": "online_chat", "period": "week", "report": "chat-offline"},
                "view_mode": "table",
            },
            {
                "id": "tpl-chat-history-day",
                "name": "Онлайн-чат: реестр диалогов за день",
                "metrics": ["dialogs_total", "aht_sec", "avg_first_response_sec"],
                "filters": {"channel": "online_chat", "period": "day", "report": "chat_history"},
                "view_mode": "table",
            },
        ],
        "saved": saved or [],
        "metric_catalog": [
            {"id": "dialogs_total", "label": "Число диалогов"},
            {"id": "dialogs_closed", "label": "Закрытых диалогов"},
            {"id": "sla_pct", "label": "Соблюдение SLA первого ответа, %"},
            {"id": "csat", "label": "Средняя оценка клиента"},
            {"id": "useful_pct", "label": "Полезность суфлёра, %"},
            {"id": "sufler_used_pct", "label": "Использование суфлёра, %"},
            {"id": "relevance_avg", "label": "Средняя релевантность, %"},
            {"id": "incorrect_llm", "label": "Доля «не использовал», %"},
            {"id": "avg_first_response_sec", "label": "Среднее время первого ответа, с"},
            {"id": "topics_top", "label": "Число тематик"},
            {"id": "aht_sec", "label": "Среднее время обработки, с"},
            {"id": "aht", "label": "Среднее время обработки, с"},
        ],
        "stub": False,
    }


def preview_builder(body: dict[str, Any]) -> dict[str, Any]:
    metrics = body.get("metrics") or ["dialogs_total", "useful_pct", "csat"]
    view_mode = body.get("view_mode") or "table"
    name = body.get("name") or "Черновик отчёта"
    today = datetime.now(timezone.utc).date()
    date_from = today - timedelta(days=6)
    date_to = today
    raw_from = body.get("date_from")
    raw_to = body.get("date_to")
    if raw_from:
        try:
            date_from = date.fromisoformat(str(raw_from)[:10])
        except ValueError:
            pass
    if raw_to:
        try:
            date_to = date.fromisoformat(str(raw_to)[:10])
        except ValueError:
            pass

    rows = []
    chart = []
    metric_labels = {
        "dialogs_total": "Число диалогов",
        "dialogs_closed": "Закрытых диалогов",
        "sla_pct": "Соблюдение SLA первого ответа, %",
        "csat": "Средняя оценка клиента",
        "useful_pct": "Полезность суфлёра, %",
        "sufler_used_pct": "Использование суфлёра, %",
        "relevance_avg": "Средняя релевантность, %",
        "incorrect_llm": "Доля «не использовал», %",
        "avg_first_response_sec": "Среднее время первого ответа, с",
        "topics_top": "Число тематик",
        "aht_sec": "Среднее время обработки, с",
        "aht": "Среднее время обработки, с",
    }
    for metric in metrics:
        metric_id = str(metric)
        value, unit = builder_metric_value(metric_id, date_from, date_to)
        label = metric_labels.get(metric_id, metric_id)
        display = value if value is not None else "—"
        rows.append(
            {
                "metric": label,
                "metric_id": metric_id,
                "value": display if not isinstance(display, str) else 0,
                "unit": unit or "—",
                "display": display,
            }
        )
        if isinstance(value, (int, float)):
            chart.append({"label": label, "value": float(value)})
    return {
        "name": name,
        "view_mode": view_mode,
        "rows": [
            {
                "metric": row["metric"],
                "value": row["value"] if isinstance(row["value"], (int, float)) else 0,
                "unit": row["unit"],
            }
            for row in rows
        ],
        "chart": chart,
        "stub": False,
        "message": f"Предпросмотр за период {date_from.isoformat()} — {date_to.isoformat()}.",
        "period": {"date_from": date_from.isoformat(), "date_to": date_to.isoformat()},
    }
