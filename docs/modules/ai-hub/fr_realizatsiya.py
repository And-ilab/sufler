"""Implementation texts for FR rows — column «Реализация» in tz-unified-v1.3.md."""

from __future__ import annotations

import re

from business_realizatsiya import polish_business
from fr_business_ru import FR_ASS_RPT, apply_business_fr
from ru_localize import localize

FR: dict[str, str] = {}


def _s(text: str) -> str:
    return text.strip()


def pick_label(body: str) -> str:
    b = body.strip()
    infra = re.compile(
        r"on-prem|air-gapped|deploy|TLS|RBAC|egress|scale|cluster|CI/CD|encrypt|"
        r"audit|i18n|horizontal|PostgreSQL|K8s|isolated|локальн",
        re.I,
    )
    ui = re.compile(
        r"\bUI\b|webhook|embed|panel|CRUD|button|thread|dropdown|canvas|"
        r"upload|preview|moderation|HITL|snippet|вкладк|панел|форм|виджет|АРМ",
        re.I,
    )
    algo = re.compile(
        r"RAG|LLM|QU|ASR|embedding|semantic|orchestration|pipeline|OCR|"
        r"lang detect|classifier|retriev|prompt|index|ETL|FeedbackEvent",
        re.I,
    )
    if infra.search(b) and not algo.search(b[:40]):
        return "Обеспечивается за счёт"
    if ui.search(b) and algo.search(b):
        return "Механизм реализации"
    if ui.search(b):
        return "Реализовано посредством"
    if algo.search(b):
        return "Механизм реализации"
    if infra.search(b):
        return "Обеспечивается за счёт"
    return "Механизм реализации"


def _wrap(
    fr_id: str,
    *,
    entry: str = "",
    under: str,
    out: str,
    accept: str,
) -> None:
    parts = []
    if entry:
        parts.append(f"**Вход:** {polish_business(localize(entry))}")
    parts.append(f"**{pick_label(under)}:** {polish_business(localize(under))}")
    parts.append(f"**Выход:** {polish_business(localize(out))}")
    parts.append(f"**Приёмка:** {polish_business(localize(accept))}")
    FR[fr_id] = _s(" ".join(parts))


apply_business_fr(_wrap, pick_label, polish_business, localize, _s)

# Overrides when same FR ID used in different modules (III.10.2 assistant vs II.6 КЦ)
FR_DESC_PREFIX: dict[tuple[str, str], str] = {}
_ass_rpt_prefixes = {
    "01": "Средняя",
    "02": "Полезность",
    "03": "ошибоч",
    "04": "Категор",
    "05": "галлюц",
    "06": "Регуляр",
    "07": "Таблицы",
    "08": "Конструктор",
}
for num, (entry, under, out, accept) in FR_ASS_RPT.items():
    parts = [
        f"**Вход:** {polish_business(localize(entry))}",
        f"**{pick_label(under)}:** {polish_business(localize(under))}",
        f"**Выход:** {polish_business(localize(out))}",
        f"**Приёмка:** {polish_business(localize(accept))}",
    ]
    text = _s(" ".join(parts))
    prefix = _ass_rpt_prefixes[num]
    FR_DESC_PREFIX[(f"FR-RPT-CC-{num}", prefix)] = text


def derive_from_uc(fr_id: str, uc_map: dict[str, str]) -> str | None:
    """Map FR-* to UC-* implementations where numbers align."""
    m = {
        "FR-SUF-11": "UC-SUF-T01",
        "FR-SUF-07": "UC-SUF-T04",
        "FR-SUF-08": "UC-SUF-T05",
        "FR-SUF-03": "UC-SUF-T03",
        "FR-SUF-C01": "UC-SUF-C01",
        "FR-SUF-C02": "UC-SUF-C02",
        "FR-SUF-C03": "UC-SUF-C03",
        "FR-ASS-34": "UC-ASS-12",
        "FR-ASS-26": "UC-ASS-13",
        "FR-ASS-27": "UC-ASS-15",
        "FR-ASS-28": "UC-ASS-16",
        "FR-ASS-23": "UC-ASS-17",
        "FR-ASS-25": "UC-ASS-11",
        "FR-ASS-35": "UC-ASS-01",
    }
    uc_id = m.get(fr_id)
    if uc_id and uc_id in uc_map:
        return uc_map[uc_id]
    return None


def get_fr_impl(fr_id: str, desc: str, uc_map: dict[str, str] | None = None) -> str:
    for (fid, prefix), text in FR_DESC_PREFIX.items():
        if fid == fr_id and prefix in desc:
            return text
    if fr_id in FR:
        return FR[fr_id]
    if uc_map:
        derived = derive_from_uc(fr_id, uc_map)
        if derived:
            return derived
    short = desc[:120].rstrip() + ("…" if len(desc) > 120 else "")
    body = f"{short} — реализация в Hub/on-prem по § ТТ."
    return polish_business(localize(_s(
        f"**{pick_label(body)}:** {body} "
        f"**Выход:** UI/артефакт по требованию. **Приёмка:** модульный smoke / INT-T."
    )))
