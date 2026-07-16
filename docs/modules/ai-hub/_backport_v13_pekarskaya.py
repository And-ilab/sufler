#!/usr/bin/env python3
"""Backport Pekarskaya [89]-[97] patches from v1.4 into tz-unified-v1.3.md."""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
V13 = ROOT / "tz-unified-v1.3.md"
V14 = ROOT / "tz-unified-v1.4.md"

sys.path.insert(0, str(ROOT))
from _gen_v14 import patch_reporting_detail, patch_webhook_timing  # noqa: E402


def extract_ii7(text: str) -> str:
    m = re.search(r"(## II\.7\. Приёмка.*?\n)(?=# Часть III\.)", text, re.DOTALL)
    if not m:
        raise SystemExit("II.7 section not found")
    return m.group(1)


def backport_v13() -> None:
    v13 = V13.read_text(encoding="utf-8")
    v14 = V14.read_text(encoding="utf-8")

    # [89]-[92] reporting + [96] webhook
    v13 = patch_webhook_timing(v13)
    v13 = patch_reporting_detail(v13)

    # Sync full II.6 FR-RPT-CC table from v1.4 (patch_reporting_detail misses v1.3 originals)
    m14_fr = re.search(r"(\| FR-RPT-CC-01 \|.*?\n)(?=### II\.6\.2\.)", v14, re.DOTALL)
    if m14_fr:
        v13 = re.sub(
            r"\| FR-RPT-CC-01 \|.*?\n(?=### II\.6\.2\.)",
            m14_fr.group(1),
            v13,
            count=1,
            flags=re.DOTALL,
        )

    # [93] II.7 expanded (57 scenarios, RPT-T, UND-T)
    ii7 = extract_ii7(v14)
    v13 = re.sub(
        r"## II\.7\. Приёмка.*?(?=\n# Часть III\.)",
        ii7.rstrip() + "\n\n",
        v13,
        count=1,
        flags=re.DOTALL,
    )

    # [95] SUZ markup — I.7 responsibility row
    v13 = v13.replace(
        "| Разметка СУЗ для LLM | §4.5.1.6 | [Исполнитель] + [Заказчик] | [VI.1](#vi1-суз--rag) |",
        "| Разметка СУЗ для LLM | §4.5.1.6 | [Исполнитель] (методика + выполнение; согласование с [Заказчиком]) | [VI.1.3.1](#vi131-разметка-суз-для-индексации-rag-4516) |",
    )

    # [95] glossary term
    if "**разметка СУЗ для LLM**" not in v13:
        v13 = v13.replace(
            "| **runtime** | Режим штатной эксплуатации",
            "| **разметка СУЗ для LLM** | Подготовка контента СУЗ для индекса `cc_production`: нормализация HTML, чанкинг, эмбеддинги, метаданные индекса — зона **Исполнителя** (§4.5.1.6); **не** создание метаданных в CMS и **не** редактирование статей контент-менеджерами КЦ | [VI.1.3.1](#vi131-разметка-суз-для-индексации-rag-4516) |\n| **runtime** | Режим штатной эксплуатации",
        )

    # [95] II.0 item 1.1 — methodology
    v13 = v13.replace(
        "| **1.1** | Спецификация интеграции СУЗ: поля, формат, триггеры, порядок обмена — **T+20 раб. дней** от подписания договора (Исполнитель) | FR-SUF-01, FR-UND-08; зависимость подсказок от актуального индекса | [VI.1](#vi1-суз--rag), [II.3.6](#ii36-kpi-и-интеграции) |",
        "| **1.1** | Спецификация интеграции СУЗ (поля, формат, триггеры) **и методика разметки** §4.5.1.6 — **T+20 раб. дней** от подписания договора (Исполнитель) | FR-SUF-01, FR-SUZ-01, FR-UND-08; зависимость подсказок от актуального индекса | [VI.1](#vi1-суз--rag), [VI.1.3.1](#vi131-разметка-суз-для-индексации-rag-4516) |",
    )

    # [95] II.3.7 section
    if "## II.3.7. Разметка СУЗ" not in v13:
        m = re.search(
            r"(## II\.3\.7\. Разметка СУЗ.*?\n\n)(## II\.4\.)",
            v14,
            re.DOTALL,
        )
        if m:
            v13 = v13.replace("## II.4.", m.group(1) + "## II.4.", 1)

    # [95] KPI table row for SUF-T-15
    if "INT-T-SUZ-09, SUF-T-15" not in v13:
        v13 = v13.replace(
            "| SUF-T-03…07, CHAT-T | Подсказки из актуального индекса СУЗ | тест Bitrix п. **1.4** — **T+30 раб. дней** (тест Bitrix) |",
            "| SUF-T-03…07, CHAT-T | Подсказки из актуального индекса СУЗ | тест Bitrix п. **1.4** — **T+30 раб. дней** (тест Bitrix) |\n| INT-T-SUZ-09, SUF-T-15 | Первичная разметка СУЗ и выборочная проверка retrieval | тест Bitrix п. **1.4** + согласованная методика (п. **1.1**) |",
        )

    # [95] VI.1.3.1 section
    if "#### VI.1.3.1. Разметка СУЗ" not in v13:
        m = re.search(
            r"(#### VI\.1\.3\.1\. Разметка СУЗ.*?\n\n)(### VI\.1\.4\.)",
            v14,
            re.DOTALL,
        )
        if m:
            v13 = v13.replace("### VI.1.4.", m.group(1) + "### VI.1.4.", 1)

    # [95] VI.1 responsibility + matrix
    v13 = v13.replace(
        "4. **Разделение ответственности:** Заказчик — инфраструктура, каналы, согласование **ИБ**; доработка Bitrix/Oktell — по матрицам BTX/OKT; Исполнитель — приёмник, RAG, ASR, LLM, методика разметки СУЗ **[Прил.1 §4.5.1.6]**.",
        "4. **Разделение ответственности:** Заказчик — инфраструктура, каналы, доступ к СУЗ (тест/prod), контент CMS, согласование **ИБ** и методики разметки; доработка Bitrix/Oktell — по матрицам BTX/OKT; Исполнитель — приёмник, RAG, ASR, LLM, **методика и выполнение разметки** контента СУЗ для индексации RAG **[Прил.1 §4.5.1.6]** ([VI.1.3.1](#vi131-разметка-суз-для-индексации-rag-4516)).",
    )
    v13 = v13.replace(
        "| Индексация, RAG, LLM | Да | — | — |",
        "| Индексация, RAG, LLM | Да | — | — |\n| Разметка СУЗ для LLM §4.5.1.6 | Методика + **выполнение разметки** (нормализация, чанкинг, эмбеддинги) | — | Доступ к СУЗ; согласование методики и ИБ |",
    )

    # [97] VII.2 matrix UND-T + RPT-T
    v13 = v13.replace(
        "Связь приёмки этапов с SUF-T, CHAT-T, ASS-T, DOC-T, INT-T.",
        "Связь приёмки этапов с **8 наборами** модулей: UND-T, SUF-T, CHAT-T, RPT-T, ASS-T, DOC-T, INT-T + HUB-T (контур целиком).",
    )
    v13 = v13.replace(
        "**Целевой эффект:** ввод системы сопровождается формализованной приёмкой.",
        "**Целевой эффект:** ввод системы сопровождается формализованной приёмкой всех модулей §2.2, включая модуль понимания запросов и отчётность КЦ.",
    )
    if "UND-T | модуль понимания" not in v13:
        v13 = v13.replace(
            "| SUF-T | интерфейсы суфлёра (тел./чат) | II.7.1 |",
            "| UND-T | модуль понимания запросов (КЦ) | [II.7.6](#ii76-und-t-модуль-понимания-запросов-421) | §4.2.1; UC-UND-01…02; QU ≠ ASR (§4.2.2 → SUF-T/INT-T) | готово |\n| SUF-T | интерфейсы суфлёра (тел./чат) | II.7.1 |",
        )
        v13 = v13.replace(
            "| CHAT-T | модуль онлайн-чат | II.7.3 | §4.4; стыковка [II.4](#ii4-интерфейс-для-работы-суфлёра--онлайн-чат-2223-432) | готово |\n| ASS-T |",
            "| CHAT-T | модуль онлайн-чат | II.7.3 | §4.4; стыковка [II.4](#ii4-интерфейс-для-работы-суфлёра--онлайн-чат-2223-432) | готово |\n| RPT-T | модуль «Отчётность» КЦ | [II.7.5](#ii75-rpt-t-отчётность-47) | §4.7; FR-RPT-CC-01…15; UC-REP-CC-01/02 | готово |\n| ASS-T |",
        )
        v13 = v13.replace(
            "| ASS-T | модуль ИИ-ассистент | [III.8](#iii8-приёмка-ass-t) | §[III.0](#iii0-поручения-протокола-встречи-2) п. 4.2; открытые FR — RPA/SQL/внешн. источники | готово |",
            "| ASS-T | модуль ИИ-ассистент | [III.8](#iii8-приёмка-ass-t) | §5.2 QU → ASS-T-QU-01…02; §5.4 → ASS-T-RPT-01…02 | готово |",
        )
    v13 = v13.replace(
        "| Контент СУЗ | КЦ | Production-индекс для INT-T |",
        "| Контент СУЗ | КЦ | Эксплуатация CMS, наполнение статей; доступ read для INT-10; **разметка для LLM — Исполнитель** ([VI.1.3.1](#vi131-разметка-суз-для-индексации-rag-4516), §4.5.1.6) |",
    )

    V13.write_text(v13, encoding="utf-8")
    print(f"Backported Pekarskaya patches to {V13} ({len(v13)} chars)")


def fix_v14_typo() -> None:
    v14 = V14.read_text(encoding="utf-8")
    if "гotово" in v14:
        v14 = v14.replace("гotово", "готово")
        V14.write_text(v14, encoding="utf-8")
        print("Fixed гotovo typo in v1.4")


if __name__ == "__main__":
    fix_v14_typo()
    backport_v13()
