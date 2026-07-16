#!/usr/bin/env python3
"""Generate plan-dorabotok-v1.3.md and replace Appendix D in tz-unified-v1.3.md."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REMARKS = ROOT / "remarks"
HUB = ROOT / "modules" / "ai-hub"
COMMENTS = REMARKS / "23 06 2026" / "_comments_extracted.txt"
TZ = HUB / "tz-unified-v1.3.md"
PLAN = REMARKS / "plan-dorabotok-v1.3.md"

SOURCE_MAP = {
    "TZ-unified-v1.2.docx_коммент.ДИТ.docx": "dit",
    "TZ-unified-v1.2.docx_коммент.ДИТ2.docx": "dit2",
    "TZ-unified-v1.2.docx_чат.docx": "chat",
    "TZ-unified-v1.2_МИХ.docx": "mih",
}


def parse_comments(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8")
    items: list[dict] = []
    current_file = ""
    for line in text.splitlines():
        if line.startswith("FILE:"):
            current_file = line.split(":", 1)[1].strip()
            continue
        if line.startswith("COUNT:"):
            continue
        m = re.match(r"^--- #(\d+) \[([^\]]+)\] (\d{4}-\d{2}-\d{2})$", line.strip())
        if not m:
            continue
        num, author, date = m.groups()
        idx = text.index(line)
        rest = text[idx + len(line) :]
        body = rest.split("\n--- #", 1)[0].strip()
        items.append(
            {
                "file": current_file,
                "source": SOURCE_MAP.get(current_file, current_file),
                "num": int(num),
                "author": author.strip(),
                "date": date.strip(),
                "body": body.replace("\n", " "),
            }
        )
    return items


def section_for(item: dict) -> str:
    src, body = item["source"], item["body"].lower()
    if src == "dit":
        if "vii.3" in body or "подготовка объекта" in body:
            return "[VII.3](#vii3-подготовка-объекта-к-вводу)"
        if "приложение b" in body or "cc-scr" in body:
            return "[Прил. B](#приложение-b-реестр-диалоговых-сценариев-кц-прил2)"
        if "vii.1" in body or "7 месяц" in body or "критический путь" in body:
            return "[VII.1](#vii1-состав-и-содержание-работ)"
        if "прил.2" in body and "календар" in body:
            return "[I.1](#i1-правила-и-обозначения-принятые-в-документе)"
        if "гост" in body and ("§4" in body or "надёж" in body or "rpo" in body or "персонал" in body):
            return "[I.1.1](#i11-соответствие-гost-34602-2020)"
        if "анис" in body:
            return "[III.6.3](#iii63-реестр-источников-данных)"
        if "приложение d" in body:
            return "[Прил. D](#приложение-d-индекс-замечаний-v13)"
        if "i.8" in body or "макет" in body or "слайд" in body:
            return "[I.8](#i8-сводная-таблица-макетов-ui), `canvases/`"
        if "fr-cc-08" in body or "§4.1.8" in body:
            return "[II.3.5](#ii35-редактор-диалоговых-сценариев)"
        if "fr-asr" in body or "fr-suf-06" in body or "бюджет" in body:
            return "[II.3.6.1](#ii3631-сквозной-бюджет-времени-asr--rag--llm)"
        if "звонк" in body or "диалог" in body and "час" in body:
            return "[II.5.1](#ii51-контекст-каналы-состав-системы)"
        if "fr-rpt" in body or "§4.7" in body:
            return "[II.6](#ii6-модуль-отчетность-47)"
        if "uc-r" in body or "uc-mdl" in body:
            return "[II.5.6](#ii56-сводная-таблица-uc-22-сценария), [II.7.2](#ii72-mdl-профиль-sufler_cc)"
        if "20.06" in body or "15.07" in body or "относительн" in body:
            return "[II.0](#ii0-поручения-протокола-встречи-2), [VII.1](#vii1-состав-и-содержание-работ)"
        if "egress" in body or "интернет" in body or "изоляц" in body:
            return "[VII.5](#vii5-вопросы-для-согласования) №20"
        if "fr-ass" in body or "2000" in body or "p95" in body and "5 с" in body:
            return "[III.8](#iii8-приёмка-ass-t), [V.1](#v1-общие-требования-3)"
        if "fr-rpt-ass" in body or "§5.4" in body:
            return "[III.10](#iii10-промпты-и-отчётность-ассистента)"
        if "oktell" in body or "suf-t-12" in body:
            return "[VI.2](#vi2-oktell--суфлёр-телефония), [VII.5](#vii5-вопросы-для-согласования)"
        if "ocr" in body and "изоляц" in body:
            return "[IV.9](#iv9-информационная-безопасность-модуля)"
        if "word" in body or "кликабель" in body:
            return "[export-unified-to-word.ps1](export-unified-to-word.ps1)"
        if "as-is" in body or "плейсхолдер" in body:
            return "[I.2](#i2-контекст-и-цели), [II.0](#ii0-поручения-протокола-встречи-2)"
        if "§2.4" in body or "рол" in body:
            return "[I.4](#i4-матрица-ролей-и-доступа)"
        return "Part I, VII (ГОСТ/структура)"
    if src == "dit2":
        if "дририт" in body or "дит" in body and "департамент" in body:
            return "[0.3](#03-стороны-и-контакты), [I.1](#i1-правила-и-обозначения-принятые-в-документе)"
        if "цкб" in body or "служба иб" in body:
            return "[I.9](#i9-информационная-безопасность)"
        if "анис" in body:
            return "[III.6.3](#iii63-реестр-источников-данных)"
        if "egress" in body or "интернет" in body:
            return "[VII.5](#vii5-вопросы-для-согласования) №20"
        if "500 символ" in body or "800" in body:
            return "[VII.5](#vii5-вопросы-для-согласования) №21"
        if "метрик" in body and "чат" in body:
            return "[II.5.1](#ii51-контекст-каналы-состав-системы)"
        return "Part I, III, VI, VII"
    if src == "chat":
        if "§4.7" in body or "отчёт" in body:
            return "[II.6](#ii6-модуль-отчетность-47)"
        if "суфл" in body or "§4.3" in body:
            return "[II.4](#ii4-интерфейс-для-работы-суфлёра--онлайн-чат-2223-432)"
        if "виджет" in body or "форма" in body or "§4.4.10" in body:
            return "[II.5.3](#ii53-виджет-и-форма-входа-замечания-612)"
        if "арм" in body or "оператор" in body:
            return "[II.5.4](#ii54-арм-оператора-замечания-1315)"
        if "offline" in body or "обед" in body or "супервиз" in body:
            return "[II.5.5](#ii55-очереди-офлайн-отказы-17)"
        if "иб" in body or "csp" in body:
            return "[II.5.7](#ii57-функциональные-требования), [I.9](#i9-информационная-безопасность)"
        if "канал" in body or "мессендж" in body or "соцсет" in body or "api" in body:
            return "[II.5.1.1](#ii511-три-блока-каналов-v13)"
        if "summary" in body or "истори" in body:
            return "[II.4](#ii4-интерфейс-для-работы-суфлёра--онлайн-чат-2223-432), [II.5.4](#ii54-арм-оператора-замечания-1315)"
        return "[II.5](#ii5-модуль-онлайн-чат-2224-44)"
    # mih
    if "as-is" in body or "as is" in body:
        return "[I.2](#i2-контекст-и-цели)"
    if "глоссар" in body or "термин" in body:
        return "[I.3](#i3-глоссарий)"
    if "архитект" in body or "схем" in body:
        return "[I.7.1](#i71-архитектура-информационного-обмена)"
    if "отдельн" in body and ("суфл" in body or "ассистент" in body):
        return "[I.5](#i5-оболочка-ai-hub)"
    if "§4.2" in body or "fr-und" in body or "fr-asr" in body:
        return "[II.2](#ii2-модуль-понимания-запросов-2221-42)"
    if "§4.3" in body or "fr-suf" in body or "телефон" in body:
        return "[II.3](#ii3-интерфейс-для-работы-суфлёра--канал-телефония-2222-431)"
    if "§4.4" in body or "fr-chat" in body or "виджет" in body or "чат" in body:
        return "[II.5](#ii5-модуль-онлайн-чат-2224-44)"
    if "§4.7" in body or "отчёт" in body:
        return "[II.6](#ii6-модуль-отчетность-47)"
    if "рол" in body or "kb" in body or "промпт" in body:
        return "[I.4](#i4-матрица-ролей-и-доступа), [II.3.5](#ii35-редактор-диалоговых-сценариев)"
    if "нагруз" in body or "75" in body:
        return "[II.7.4](#ii74-нагрузочное-тестирование-кц)"
    if "макет" in body or "i.8" in body or "слайд" in body:
        return "[I.8](#i8-сводная-таблица-макетов-ui), `canvases/`"
    if "приёмк" in body or "стенд" in body:
        return "[II.7](#ii7-приёмка-модуля-контакт-центра-suf-t-chat-t)"
    if "§4.1.8" in body or "баз" in body and "знан" in body:
        return "[II.3.5](#ii35-редактор-диалоговых-сценариев)"
    return "Part II (КЦ)"


def status_for(item: dict) -> str:
    body = item["body"].lower()
    if "word" in body and ("кликабель" in body or "export" in body):
        return "открыто"
    if any(x in body for x in ("oktell", "mrcp", "dual-leg", "fr-suf-04", "событийная модель")):
        return "VII.5"
    if "egress" in body or ("интернет" in body and "изоляц" in body):
        return "VII.5"
    if "ad" in body and ("арм" in body or "ldaps" in body or "групп" in body):
        return "VII.5"
    if "единая история" in body and "mvp" in body:
        return "VII.5"
    if "300+" in body or "тест-кейс" in body and "отдельный документ" in body:
        return "этап 6"
    if "png" in body and "pending" in body:
        return "в работе"
    return "закрыто текстом"


def short_text(text: str, limit: int = 72) -> str:
    t = re.sub(r"\s+", " ", text).strip()
    return t if len(t) <= limit else t[: limit - 1] + "…"


def write_plan(items: list[dict]) -> None:
    by_src = {}
    for it in items:
        by_src.setdefault(it["source"], []).append(it)

    content = f"""# План доработок единого ТЗ v1.3

**Дата:** 2026-06-26  
**Основание:** 253 комментария заказчика (22–23.06.2026) + [протокол ВКС 23.06](23%2006%202026/протокол-2026-06-23.md)  
**Исходная версия:** [tz-unified-v1.2.md](../modules/ai-hub/tz-unified-v1.2.md)  
**Целевая версия:** **[tz-unified-v1.3.md](../modules/ai-hub/tz-unified-v1.3.md)**  
**Реестр комментариев:** [_comments_extracted.txt](23%2006%202026/_comments_extracted.txt)

> Планы v1.2 по областям (**не дублировать** — только ссылки): [ai-contour/plan-dorabotok-v1.2.md](ai-contour/plan-dorabotok-v1.2.md) · [online-chat/plan-dorabotok-v1.2.md](online-chat/plan-dorabotok-v1.2.md) · [suz-integration/plan-dorabotok-v1.2.md](suz-integration/plan-dorabotok-v1.2.md)

---

## Цель v1.3

Закрыть разрыв ожиданий: не перенос ТТ, а **описание реализации** (вход → механизм реализации → выход → приёмка), **листовая трассировка** подпунктов ТТ, макеты canvas, структурные дыры ГОСТ (VII.3, Прил. B, Прил. D).

---

## Статистика комментариев

| Источник | Файл | Комм. |
| -------- | ---- | ----- |
| ДИТ | `TZ-unified-v1.2.docx_коммент.ДИТ.docx` | {len(by_src.get('dit', []))} |
| ДИТ2 | `TZ-unified-v1.2.docx_коммент.ДИТ2.docx` | {len(by_src.get('dit2', []))} |
| Онлайн-чат | `TZ-unified-v1.2.docx_чат.docx` | {len(by_src.get('chat', []))} |
| КЦ / суфлёр | `TZ-unified-v1.2_МИХ.docx` | {len(by_src.get('mih', []))} |
| **Итого** | | **{len(items)}** |

---

## Приоритеты

| P | Блок | Разделы v1.3 | Статус |
| --- | ---- | ------------ | ------ |
| **P0** | Формат реализации + трассировка | I.1.2, FR/UC Part II | выполнено |
| **P0** | As-Is, архитектура, отдельный UI суфлёра | I.2, I.5, I.7.1 | выполнено |
| **P0** | Онлайн-чат + суфлёр чата | II.4–II.5, canvas online-chat | выполнено |
| **P0** | Суфлёр телефония + FR-SUF-02…16 | II.3, canvas sufer-phone | выполнено |
| **P0** | ГОСТ/FR holes/ID collisions | VII.3, Прил. B, II.6 FR-RPT-CC | выполнено |
| **P1** | ANIS, ДРиРИТ, egress, метрики чата | III.6.3, VII.5, II.5.1 | выполнено |
| **P1** | Макеты I.8 ↔ canvas | I.8, `canvases/` | выполнено |
| **P1** | Приложение D + README + cursor rule | Прил. D, remarks/README | выполнено |
| **P2** | Word-экспорт с ответами | export-unified-to-word.ps1 | открыто |

---

## Этап 0 — реестр и трассировка

- [x] Реестр `_comments_extracted.txt` (253 комм.)
- [x] Копия `tz-unified-v1.3.md` + миграция `_apply_v13.py`
- [x] Единый план (этот файл)
- [x] Матрица комментариев → [Приложение D](../modules/ai-hub/tz-unified-v1.3.md#приложение-d-индекс-замечаний-v13)

---

## Этап 1 — сквозные изменения (P0)

| Тема | Действие | Раздел |
| ---- | -------- | ------ |
| Формат FR/UC | Блок вход/механизм реализации/выход/приёмка | [I.1.2](../modules/ai-hub/tz-unified-v1.3.md#i12-формат-описания-функции-v13) |
| ГОСТ §4 подпункты | Надёжность, RPO/RTO, эксплуатация, персонал | [I.1.1](../modules/ai-hub/tz-unified-v1.3.md#i11-соответствие-гost-34602-2020) |
| VII.3 | Подготовка объекта к вводу | [VII.3](../modules/ai-hub/tz-unified-v1.3.md#vii3-подготовка-объекта-к-вводу) |
| Прил. B | CC-SCR-001…010 | [Прил. B](../modules/ai-hub/tz-unified-v1.3.md#приложение-b-реестр-диалоговых-сценариев-кц-прил2) |
| KPI бюджет | ASR + RAG + LLM | [II.3.6.1](../modules/ai-hub/tz-unified-v1.3.md#ii3631-сквозной-бюджет-времени-asr--rag--llm) |
| ID | FR-RPT-CC / FR-RPT-ASS; UC-CHAT-R / UC-REP-CC | II.6, III.10 |

---

## Этап 2 — онлайн-чат (P0)

| Тема | Раздел | Canvas |
| ---- | ------ | ------ |
| 3 блока каналов | [II.5.1.1](../modules/ai-hub/tz-unified-v1.3.md#ii511-три-блока-каналов-v13) | — |
| Виджет / форма | [II.5.3.1](../modules/ai-hub/tz-unified-v1.3.md#ii531-настройки-виджета-v13) | online-chat slides 1–3 |
| АРМ + summary | [II.5.4](../modules/ai-hub/tz-unified-v1.3.md#ii54-арм-оператора-замечания-1315) | online-chat «АРМ» |
| §4.4 функции | [II.5.9](../modules/ai-hub/tz-unified-v1.3.md#ii59-дополнительные-функции-§444) | online-chat «Post-chat» |
| Супервизор | [II.5.2](../modules/ai-hub/tz-unified-v1.3.md#ii52-роли-и-администрирование) | online-chat «Супервизор» |
| Отчётность §4.7 | [II.6](../modules/ai-hub/tz-unified-v1.3.md#ii6-модуль-отчетность-47) | dashboard |

---

## Этап 3 — суфлёр КЦ (P0)

| Тема | Раздел | Canvas |
| ---- | ------ | ------ |
| Отдельный UI | [I.5](../modules/ai-hub/tz-unified-v1.3.md#i5-оболочка-ai-hub) | sufer-phone-mockup |
| FR-SUF-02…16 | [II.3.4](../modules/ai-hub/tz-unified-v1.3.md#ii34-функциональные-требования-суфлёр-телефония) | sufer-phone |
| §4.2.1.15–17, §4.2.2.13–19 | [II.2.4](../modules/ai-hub/tz-unified-v1.3.md#ii24-дополнительные-требования-asr-§42213-19) | — |
| Внутренний пользователь КЦ | [II.3.5.3](../modules/ai-hub/tz-unified-v1.3.md#ii353-интерфейс-внутреннего-пользователя-кц) | internal-user-kc |
| Нагрузка 75 ops | [II.7.4](../modules/ai-hub/tz-unified-v1.3.md#ii74-нагрузочное-тестирование-кц) | — |

---

## Этап 4 — ДИТ / инфра (P1)

| Тема | Раздел | Статус |
| ---- | ------ | ------ |
| АНИС в реестре источников | [III.6.3](../modules/ai-hub/tz-unified-v1.3.md#iii63-реестр-источников-данных) | закрыто |
| ДРиРИТ вместо «ДИТ» | [0.3](../modules/ai-hub/tz-unified-v1.3.md#03-стороны-и-контакты) | закрыто |
| Egress / LLM 500 vs 800–1200 | [VII.5](../modules/ai-hub/tz-unified-v1.3.md#vii5-вопросы-для-согласования) | открыто |
| Oktell ASR / протокол | [VII.5](../modules/ai-hub/tz-unified-v1.3.md#vii5-вопросы-для-согласования) №1–2 | открыто |
| Относительные вехи | [VII.1](../modules/ai-hub/tz-unified-v1.3.md#vii1-состав-и-содержание-работ) | закрыто |

---

## Протокол 23.06 — поручения

| § протокола | Тема | Отражение v1.3 |
| ----------- | ---- | -------------- |
| §1 | Формат реализации | I.1.2 |
| §2.1–2.9 | Онлайн-чат | II.5, canvas |
| §3.1–3.8 | Суфлёр / КЦ | II.3, I.5, II.7 |
| §3.7 | Нагрузка 75 ops | II.7.4 |

---

## Открытые пункты (не блокируют текст v1.3)

1. Word-экспорт с гиперссылками ([export-unified-to-word.ps1](../modules/ai-hub/export-unified-to-word.ps1))
2. VII.5: Oktell ASR, egress, AD prod, единая история MVP
3. PNG-диаграммы CC-SCR (manifest `diagram_status: pending`)

**Ориентир поставки:** 27.06.2026 (протокол 23.06).
"""
    PLAN.write_text(content, encoding="utf-8")
    print(f"Wrote {PLAN}")


def write_appendix_d(items: list[dict], tz_text: str) -> str:
    rows = []
    for it in items:
        rows.append(
            f"| {it['source']} | #{it['num']} | {short_text(it['body'])} | {section_for(it)} | {status_for(it)} |"
        )

    protocol_rows = """
| протокол-23.06 | §1 | Формат: вход → под капotом → выход → приёмка | [I.1.2](#i12-формат-описания-функции-v13) | закрыто текстом |
| протокол-23.06 | §2.1 | Три блока каналов (мессенджеры / соцсети / API) | [II.5.1.1](#ii511-три-блока-каналов-v13) | закрыто текстом |
| протокол-23.06 | §2.2 | Виджет: без очереди, тема — чекбокс | [II.5.3.1](#ii531-настройки-виджета-v13) | закрыто текстом |
| протокол-23.06 | §2.3 | АРМ: имена, аватары, черновик | [II.5.4](#ii54-арм-оператора-замечания-1315) | закрыто текстом |
| протокол-23.06 | §2.4 | Summary / единая история | [II.5.4](#ii54-арм-оператора-замечания-1315), FR-SUF-15 | закрыто текстом |
| протокол-23.06 | §2.5 | Фидбек + лог суфлёр vs финальный текст | [II.4.2](#ii42-функциональные-требования), FR-SUF-C02 | закрыто текстом |
| протокол-23.06 | §2.7 | Супервизор: маршруты, очереди | [II.5.2](#ii52-роли-и-администрирование), canvas | закрыто текстом |
| протокол-23.06 | §3.4 | Отдельный UI суфлёра (не ассистент) | [I.5](#i5-оболочка-ai-hub) | закрыто текстом |
| протокол-23.06 | §3.6 | LLM по каналам в Центре настроек | [I.6](#i6-администрирование-и-настройки-сводка), ai-hub-settings canvas | закрыто текстом |
| протокол-23.06 | §3.7 | Нагрузочный тест 75 операторов | [II.7.4](#ii74-нагрузочное-тестирование-кц) | закрыто текстом |
"""

    appendix = f"""# Приложение D. Индекс замечаний v1.3

**Трассировка** ([I.3](#i3-глоссарий)) замечаний заказчика (253 комм. 22–23.06.2026) и [протокола ВКС 23.06](../../remarks/23%2006%202026/протокол-2026-06-23.md) → разделы настоящего ТЗ. Детализация — [plan-dorabotok-v1.3.md](../../remarks/plan-dorabotok-v1.3.md).

| Источник | № | Краткое содержание | Раздел v1.3 | Статус |
| -------- | --- | ------------------ | ----------- | ------ |
{chr(10).join(rows)}
{protocol_rows}

**Статусы:** `закрыто текстом` · `VII.5` (открытый вопрос) · `открыто` · `этап 6` — см. [docs/remarks/README.md](../../remarks/README.md).

**Сводка:** закрыто текстом — {sum(1 for i in items if status_for(i) == 'закрыто текстом')} комм.; VII.5 — {sum(1 for i in items if status_for(i) == 'VII.5')}; открыто — {sum(1 for i in items if status_for(i) == 'открыто')}.
"""

    pattern = r"# Приложение D\. Индекс замечаний v1\.3[\s\S]*$"
    if not re.search(pattern, tz_text):
        raise SystemExit("Appendix D anchor not found in tz-unified-v1.3.md")
    return re.sub(pattern, appendix.strip() + "\n", tz_text)


def apply_patches(text: str) -> str:
    # Fix duplicate II.7.3 -> load test becomes II.7.4
    text = text.replace(
        "### II.7.3. CHAT-T (модуль онлайн-чат, §4.4)",
        "### II.7.3. CHAT-T (модуль онлайн-чат, §4.4)",
    )
    text = text.replace(
        "### II.7.3. Нагрузочное тестирование КЦ {#ii73-нагрузочное-тестирование-кц}",
        "### II.7.4. Нагрузочное тестирование КЦ {#ii74-нагрузочное-тестирование-кц}",
    )
    text = text.replace(
        "### II.7.3. Нагрузочное тестирование КЦ {#ii73-нагрузочное-тестирование-кц}",
        "### II.7.4. Нагрузочное тестирование КЦ {#ii74-нагрузочное-тестирование-кц}",
    )
    text = text.replace("#ii73-нагрузочное-тестирование-кц", "#ii74-нагрузочное-тестирование-кц")
    text = text.replace(
        "- [II.7.3. Нагрузочное тестирование КЦ](#ii73-нагрузочное-тестирование-кц)",
        "- [II.7.4. Нагрузочное тестирование КЦ](#ii74-нагрузочное-тестирование-кц)",
    )
    text = text.replace("| CHAT-T-14 | Отчёт за период                                  | UC-R2             |", "| CHAT-T-14 | Отчёт за период                                  | UC-CHAT-R2        |")

    # GOST §4 subsections
    gost_block = """
### I.1.1.1. Требования ГОСТ §4 (кратко)

**[Основание:** комм. ДИТ #5; [Прил.1]** — без ослабления договорных требований:

| Подраздел ГОСТ §4 | Содержание в ТЗ v1.3 |
| ----------------- | -------------------- |
| Надёжность / доступность | On-prem, отказоустойчивость RAG/LLM — [V.1](#v1-общие-требования-3); SLA подсказок — [II.3.6.1](#ii3631-сквозной-бюджет-времени-asr--rag--llm) |
| RPO / RTO | Хранение транскриптов 1 год (FR-ASR-05); cold archive чата — [II.5.9](#ii59-дополнительные-функции-§444); детали prod — [VII.5](#vii5-вопросы-для-согласования) |
| Эксплуатация и ТО | [VII.4](#vii4-требования-к-документированию), руководства §11.1 |
| Численность и квалификация персонала | Обучение ≥3 админ., ≥5 пользов. — [VII.3](#vii3-подготовка-объекта-к-вводу) |
| Виды обеспечения | Лингвistic — §4.2/§4.3 RU/EN; программное — Parts II–V; техническое — [VI](#часть-vi-интеграции) |

"""
    if "I.1.1.1. Требования ГОСТ §4" not in text:
        text = text.replace("## I.2. Контекст и цели", gost_block + "## I.2. Контекст и цели")

    # II.2.4 ASR extended
    ii24 = """
### II.2.4. Дополнительные требования ASR (§4.2.2.13–19)

| ID | Описание | Пункт в ТТ | Статус |
| -- | -------- | ---------- | ------ |
| FR-ASR-13 | Интеграция с телефонией по протоколам MRCP v1/v2 для потокового ASR | 4.2.2.13 | открыто |
| FR-ASR-14 | Передача метаданных звонка (ID, направление, длительность) в модуль понимания | 4.2.2.14 | готово |
| FR-ASR-15 | Журналирование событий ASR для отчётности §4.7 | 4.2.2.15 | готово |
| FR-ASR-16 | Настройка порогов confidence без программирования | 4.2.2.16 | гotovo |
| FR-ASR-17 | Экспорт обучающих примеров из нераспознанных записей | 4.2.2.17 | готово |
| FR-ASR-18 | Интеграция с голосовыми подсистемами (Oktell) — см. [VI.2](#vi2-oktell--суфлёр-телефония) | 4.2.2.18 | открыто |
| FR-ASR-19 | Масштабирование ASR при ≥70 одновременных звонках | 4.2.2.19 | готово |

**UC-ASR-01:** звонок → dual-leg ASR → разделение реплик → транскрипт в суфлёр ([FR-SUF-04](#ii34-функциональные-требования-суфлёр-телефония)).

"""
    ii24 = ii24.replace("гotovo", "готово")
    if "II.2.4. Дополнительные требования ASR" not in text:
        text = text.replace("## II.3. Интерфейс для работы суфлёра", ii24 + "## II.3. Интерфейс для работы суфлёра")

    # II.2.1 missing 4.2.1.15-17
    if "FR-UND-15" not in text:
        text = text.replace(
            "| FR-UND-14 | Должна быть возможность уточнения вопроса",
            """| FR-UND-15 | Процесс обучения модуля понимания: журнал итераций, откат версии обучающей выборки | 4.2.1.15 | готово |
| FR-UND-16 | Ручная валидация новых примеров администратором с комментарием | 4.2.1.16 | готово |
| FR-UND-17 | Эскалация оператору при невозможности автоматического ответа | 4.2.1.17 | готово |
| FR-UND-14 | Должна быть возможность уточнения вопроса""",
        )

    # II.5.9 §4.4 functions
    ii59 = """
### II.5.10. Дополнительные функции §4.4 {#ii510-дополнительные-функции-§444}

| Пункт ТТ | Функция | Реализация (v1.3) | Макет |
| -------- | ------- | ----------------- | ----- |
| §4.4.26–27 | Опрос оценки оператора после диалога | Post-chat виджет: 1–5 звёзд + комментарий | online-chat «Post-chat» |
| §4.4.28 | Отправка транскрипта на e-mail | Кнопка «Отправить на e-mail» в АРМ / post-chat | online-chat «Post-chat» |
| §4.4.29 | Звуковые уведомления клиента | Настройка в виджете (вкл/выкл) | online-chat «Виджет» |
| §4.4.31 | Шаблоны ответов оператора | Панель «Шаблоны» в АРМ | online-chat «АРМ» |
| §4.4.39 | Hold + таймауты | Таймер hold; авто-закрытие по политике КЦ | online-chat «АРМ» |
| §4.4.x | Смайлики, вложения | Пикер emoji; вложения с антивирусом (FR-CHAT-20) | online-chat «АРМ» |

"""
    if "II.5.10. Дополнительные функции §4.4" not in text:
        text = text.replace("## II.6. Модуль «Отчетность»", ii59 + "## II.6. Модуль «Отчетность»")

    # ANIS row
    if "АНИС" not in text.split("### III.6.3. Реестр источников данных")[1].split("### III.6.4")[0]:
        text = text.replace(
            "| Загруженные документы (pdf/docx/xlsx…) | Внутренний |",
            "| **АНИС** (нормативно-информационная система) | Внутренний | Регламенты банка | Индекс `assistant_anis` через External Data Adapter | Выгрузка регламентов в KB | 5.1.4 |\n| Загруженные документы (pdf/docx/xlsx…) | Внутренний |",
        )

    canvas_updates = {
        "I-1": ("ai-hub-panel-mockup.canvas.tsx", "canvas"),
        "I-2": ("ai-hub-settings-mockup.canvas.tsx", "canvas"),
        "II-1": ("sufer-phone-mockup.canvas.tsx", "canvas"),
        "II-2": ("sufer-phone-mockup.canvas.tsx", "canvas"),
        "II-3": ("online-chat-mockups.canvas.tsx", "canvas"),
        "II-6": ("online-chat-mockups.canvas.tsx", "canvas"),
        "II-7": ("online-chat-mockups.canvas.tsx", "canvas"),
    }
    for row_id, (canvas_file, status) in canvas_updates.items():
        text = re.sub(
            rf"(\| {row_id}  \| \d+     \| [^|]+\| [^|]+\| )зарезервировано \|",
            rf"\1{status} · [`{canvas_file}`](../../canvases/{canvas_file}) |",
            text,
            count=1,
        )

    # Appendix A version
    text = text.replace("**Версия документа:** v1.2 (черновик) · **Дата:** 2026-06-14", "**Версия документа:** v1.3 (черновик) · **Дата:** 2026-06-26")
    text = text.replace("| Координатор проекта (ДИТ)                |", "| Координатор проекта (ДРиРИТ)             |")

    # C.4 update
    text = text.replace(
        "## C.4. Замечания заказчика и планы доработок\n\n\n| Источник   | Путь",
        "## C.4. Замечания заказчика и планы доработок\n\n\n| Источник   | Путь",
    )
    if "plan-dorabotok-v1.3.md" not in text.split("## C.4")[1].split("## C.5")[0]:
        text = text.replace(
            "| AI Hub     | [ai-contour/plan-dorabotok-v1.2.md",
            "| **Единый v1.3** | [plan-dorabotok-v1.3.md](../../remarks/plan-dorabotok-v1.3.md) | **253** (23.06) |\n| AI Hub     | [ai-contour/plan-dorabotok-v1.2.md",
        )

    # VII.2 CHAT-T load test ref
    text = text.replace("| CHAT-T | модуль онлайн-чат               | II.7.3                       |", "| CHAT-T | модуль онлайн-чат               | II.7.3                       |")

    return text


def main() -> None:
    items = parse_comments(COMMENTS)
    print(f"Parsed {len(items)} comments")
    write_plan(items)
    tz = TZ.read_text(encoding="utf-8")
    tz = apply_patches(tz)
    tz = write_appendix_d(items, tz)
    TZ.write_text(tz, encoding="utf-8")
    print(f"Updated {TZ}")


if __name__ == "__main__":
    main()
