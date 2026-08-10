"""Real-time / operational panel for II.6 FR-RPT-CC-03 (demo + online_chat)."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any


def _demo_live() -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    return {
        "generated_at": now.isoformat(),
        "stub": True,
        "source": "demo + online_chat (если есть диалоги)",
        "kpis": {
            "in_progress": 24,
            "in_queue": 7,
            "avg_wait_sec": 102,
            "operators_online": 18,
            "sla_ok_pct": 91.5,
            "hint_p95_ms": 1380,
        },
        "departments": [
            {"name": "Розничные продукты", "active": 12, "queue": 4},
            {"name": "Юрлица", "active": 8, "queue": 2},
            {"name": "Ипотека", "active": 4, "queue": 1},
        ],
        "operators": [
            {
                "name": "Иванов И.И.",
                "status": "online",
                "active_dialogs": 5,
                "channel": "online_chat",
            },
            {
                "name": "Петрова М.С.",
                "status": "online",
                "active_dialogs": 4,
                "channel": "online_chat",
            },
            {
                "name": "Козлов Д.В.",
                "status": "break",
                "active_dialogs": 0,
                "channel": "telephony",
            },
            {
                "name": "Сидорова А.П.",
                "status": "online",
                "active_dialogs": 3,
                "channel": "telephony",
            },
            {
                "name": "Орлов Н.В.",
                "status": "offline",
                "active_dialogs": 0,
                "channel": "online_chat",
            },
        ],
        "alerts": [
            {
                "id": "a1",
                "tone": "warning",
                "title": "SLA очереди > 3 мин",
                "detail": "Розница · email + дашборд",
                "at": (now - timedelta(minutes=18)).isoformat(),
            },
            {
                "id": "a2",
                "tone": "warning",
                "title": "p95 подсказки > 2 с",
                "detail": "Все каналы · дашборд супервизора",
                "at": (now - timedelta(hours=3)).isoformat(),
            },
            {
                "id": "a3",
                "tone": "info",
                "title": "Рост тематики «Лимиты ATM» +18%",
                "detail": "автоуведомление FR-RPT-CC-06",
                "at": (now - timedelta(minutes=40)).isoformat(),
            },
        ],
        "llm_feed": [
            {
                "id": "f1",
                "channel": "online_chat",
                "operator": "Иванов И.И.",
                "topic": "Карты и счета",
                "relevance_pct": 92,
                "feedback": "used",
                "latency_ms": 810,
                "at": (now - timedelta(minutes=2)).isoformat(),
            },
            {
                "id": "f2",
                "channel": "telephony",
                "operator": "Сидорова А.П.",
                "topic": "Кредиты",
                "relevance_pct": 74,
                "feedback": "incomplete",
                "latency_ms": 1560,
                "at": (now - timedelta(minutes=5)).isoformat(),
            },
            {
                "id": "f3",
                "channel": "online_chat",
                "operator": "Петрова М.С.",
                "topic": "ЕРИП",
                "relevance_pct": 88,
                "feedback": "used",
                "latency_ms": 640,
                "at": (now - timedelta(minutes=8)).isoformat(),
            },
        ],
        "chat": {
            "waiting": 0,
            "active": 0,
            "closed_today": 0,
            "operators_from_chat": [],
        },
    }


def _merge_online_chat(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        from online_chat.models import Dialog
    except Exception:
        return payload

    waiting = Dialog.objects.filter(status=Dialog.Status.WAITING).count()
    active = Dialog.objects.filter(status=Dialog.Status.ACTIVE).count()
    today = datetime.now(timezone.utc).date()
    closed_today = Dialog.objects.filter(
        status=Dialog.Status.CLOSED,
        closed_at__date=today,
    ).count()

    names = list(
        Dialog.objects.filter(status=Dialog.Status.ACTIVE)
        .exclude(operator_name="")
        .values_list("operator_name", flat=True)
    )
    counter = Counter(names)
    operators_from_chat = [
        {
            "name": name,
            "status": "online",
            "active_dialogs": count,
            "channel": "online_chat",
        }
        for name, count in counter.most_common(12)
    ]

    payload["chat"] = {
        "waiting": waiting,
        "active": active,
        "closed_today": closed_today,
        "operators_from_chat": operators_from_chat,
    }
    if waiting or active or closed_today:
        payload["stub"] = False
        payload["source"] = "online_chat live + demo KPI (LLM/КЦ ещё нет)"
        payload["kpis"]["in_queue"] = waiting
        payload["kpis"]["in_progress"] = active or payload["kpis"]["in_progress"]
        if operators_from_chat:
            payload["operators"] = operators_from_chat + [
                op
                for op in payload["operators"]
                if op["name"] not in {row["name"] for row in operators_from_chat}
            ]
            payload["kpis"]["operators_online"] = sum(
                1 for op in payload["operators"] if op["status"] == "online"
            )
    return payload


def build_live_dashboard() -> dict[str, Any]:
    return _merge_online_chat(_demo_live())
