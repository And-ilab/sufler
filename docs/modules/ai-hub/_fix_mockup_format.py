#!/usr/bin/env python3
"""Fix mockup references in tz-unified-v1.3.md — readable I.8 table + slide links."""

from pathlib import Path

TZ = Path(__file__).parent / "tz-unified-v1.3.md"
text = TZ.read_text(encoding="utf-8")

CANVAS = "../../canvases"

I8 = f"""## I.8. Сводная таблица макетов UI

Макеты — **интерактивные Canvas** (React-предпросмотр в Cursor). Каталог: [`canvases/`]({CANVAS}/).  
**Как открыть:** клик по ссылке в колонке «Canvas» → открыть `.canvas.tsx` **из managed-папки** Cursor (синхронизация: [`open-canvases.ps1`](open-canvases.ps1)).  
Не открывать исходник как обычный `.tsx` из корня репозитория — предпросмотр может не запуститься.

| ID | Слайд | Название макета | Раздел ТЗ | Canvas | Статус |
| --- | --- | --- | --- | --- | --- |
| I-1 | 1 | Оболочка AI Hub | [I.5](#i5-оболочка-ai-hub) | [AI Hub panel]({CANVAS}/ai-hub-panel-mockup.canvas.tsx) | готово |
| I-2 | 2 | Центр настроек — навигация LLM | [I.6](#i6-администрирование-и-настройки-сводка) | [Настройки Hub]({CANVAS}/ai-hub-settings-mockup.canvas.tsx) | готово |
| II-1 | 3 | Суфлёр телефония — общий вид | [II.3.2](#ii32-интерфейсы-и-макеты) | [Суфлёр телефония]({CANVAS}/sufer-phone-mockup.canvas.tsx) | готово |
| II-2 | 4 | Суфлёр телефония — подсказки на реплики | [II.3.2](#ii32-интерфейсы-и-макеты) | [Суфлёр телефония]({CANVAS}/sufer-phone-mockup.canvas.tsx) | готово |
| II-3 | 5 | Суфлёр чат — панель в АРМ | [II.4](#ii4-интерфейс-для-работы-суфлёра--онлайн-чат-2223-432) | [Онлайн-чат]({CANVAS}/online-chat-mockups.canvas.tsx) · вкладка «АРМ» | готово |
| II-4 | 6 | Редактор диалоговых сценариев | [II.3.5.1](#ii351-редактор-диалоговых-сценариев) | [Настройки Hub]({CANVAS}/ai-hub-settings-mockup.canvas.tsx) · «Редактор сценариев» | готово |
| II-5 | 7 | Тестирование диалогового сценария | [II.3.5.1](#ii351-редактор-диалоговых-сценариев) | [Настройки Hub]({CANVAS}/ai-hub-settings-mockup.canvas.tsx) · «Тест сценария» | готово |
| II-6 | 8 | Виджет и форма входа | [II.5.3](#ii53-виджет-и-форма-входа-замечания-612) | [Онлайн-чат]({CANVAS}/online-chat-mockups.canvas.tsx) · «Виджет клиента» | готово |
| II-7 | 9 | АРМ оператора онлайн-чата | [II.5.4](#ii54-арм-оператора-замечания-1315) | [Онлайн-чат]({CANVAS}/online-chat-mockups.canvas.tsx) · «АРМ оператора» | готово |
| II-8 | — | Внутренний пользователь КЦ (тест LLM) | [II.3.5.3](#ii353-интерфейс-внутреннего-пользователя-кц) | [Тест-диалог КЦ]({CANVAS}/internal-user-kc-mockup.canvas.tsx) | готово |
| II-9 | — | Супервизор чата | [II.5.2](#ii52-роли-и-администрирование) | [Онлайн-чат]({CANVAS}/online-chat-mockups.canvas.tsx) · «Супервизор» | готово |
| II-10 | — | Post-chat (оценка + e-mail) | [II.5.10](#ii510-дополнительные-функции-§444) | [Онлайн-чат]({CANVAS}/online-chat-mockups.canvas.tsx) · «Post-chat» | готово |
| III-1 | 10 | ИИ-ассистент — чат с источниками | [III.3](#iii3-интерфейсы-и-макеты) | [ИИ-ассистент]({CANVAS}/ai-assistant-ui-mockup.canvas.tsx) | готово |
| III-2 | 11 | ИИ-ассистент — состояния UI | [III.3](#iii3-интерфейсы-и-макеты) | [ИИ-ассистент]({CANVAS}/ai-assistant-ui-mockup.canvas.tsx) | готово |
| III-3 | 12 | ИИ-ассистент — генерация документа | [III.3](#iii3-интерфейсы-и-макеты) | [ИИ-ассистент]({CANVAS}/ai-assistant-ui-mockup.canvas.tsx) | готово |
| III-4 | 13 | Центр настроек — базы знаний LLM | [III.6](#iii6-настройки-модуля) | [Настройки Hub]({CANVAS}/ai-hub-settings-mockup.canvas.tsx) · «Базы знаний» | готово |
| III-5 | 14 | ИИ-ассистент — саммаризация A/V | [III.3](#iii3-интерфейсы-и-макеты) | [ИИ-ассистент]({CANVAS}/ai-assistant-ui-mockup.canvas.tsx) | готово |
| III-6 | 15 | ИИ-ассистент — код/SQL и RPA | [III.6.5](#iii65-политика-sql--код-§5139) | [ИИ-ассистент]({CANVAS}/ai-assistant-ui-mockup.canvas.tsx) | готово |
| III-7 | 16 | Центр настроек — реестр RPA | [III.6.3](#iii63-реестр-источников-данных) | [Настройки Hub]({CANVAS}/ai-hub-settings-mockup.canvas.tsx) · «RPA» | готово |
| III-8 | 17 | ИИ-ассистент — перевод RU↔EN | [III.3](#iii3-интерфейсы-и-макеты) | [ИИ-ассистент]({CANVAS}/ai-assistant-ui-mockup.canvas.tsx) | готово |
| IV-1 | 18 | OCR — очередь задач | [IV.3](#iv3-интерфейсы-и-макеты) | — | зарезервировано |
| IV-2 | 19 | OCR — загрузка документов | [IV.3](#iv3-интерфейсы-и-макеты) | — | зарезервировано |
| IV-3 | 20 | OCR — проверка поверх оригинала | [IV.3](#iv3-интерфейсы-и-макеты) | — | зарезервировано |
| IV-4 | 21 | Центр настроек — типы документов | [IV.6](#iv6-настройки-модуля) | [Настройки Hub]({CANVAS}/ai-hub-settings-mockup.canvas.tsx) · «Типы документов» | зарезервировано |

### I.8.1. Сводка Canvas v1.3 (КЦ)

| Макет | Ссылка | Что показано |
| --- | --- | --- |
| Суфлёр телефония | [sufer-phone-mockup.canvas.tsx]({CANVAS}/sufer-phone-mockup.canvas.tsx) | Пары «реплика → подсказка», summary, EN-блок, история |
| Онлайн-чат | [online-chat-mockups.canvas.tsx]({CANVAS}/online-chat-mockups.canvas.tsx) | Виджет, АРМ (+ summary), супервизор, post-chat |
| Тест-диалог КЦ | [internal-user-kc-mockup.canvas.tsx]({CANVAS}/internal-user-kc-mockup.canvas.tsx) | §2.4 п.6 — sandbox LLM без клиентского канала |
| AI Hub / настройки | [ai-hub-panel]({CANVAS}/ai-hub-panel-mockup.canvas.tsx) · [settings]({CANVAS}/ai-hub-settings-mockup.canvas.tsx) | Оболочка, LLM по каналам |
| ИИ-ассистент | [ai-assistant-ui-mockup.canvas.tsx]({CANVAS}/ai-assistant-ui-mockup.canvas.tsx) | Чат, состояния, генерация документов |
"""

import re

text = re.sub(
    r"## I\.8\. Сводная таблица макетов UI\n\n[\s\S]*?\n\n## I\.9\. Информационная безопасность",
    I8 + "\n\n## I.9. Информационная безопасность",
    text,
    count=1,
)

SLIDE_LINKS = {
    1: (f"[AI Hub panel]({CANVAS}/ai-hub-panel-mockup.canvas.tsx)", "I-1"),
    2: (f"[Настройки Hub]({CANVAS}/ai-hub-settings-mockup.canvas.tsx)", "I-2"),
    3: (f"[Суфлёр телефония]({CANVAS}/sufer-phone-mockup.canvas.tsx)", "II-1"),
    4: (f"[Суфлёр телефония]({CANVAS}/sufer-phone-mockup.canvas.tsx)", "II-2"),
    5: (f"[Онлайн-чат · АРМ]({CANVAS}/online-chat-mockups.canvas.tsx)", "II-3"),
    6: (f"[Настройки · редактор сценариев]({CANVAS}/ai-hub-settings-mockup.canvas.tsx)", "II-4"),
    7: (f"[Настройки · тест сценария]({CANVAS}/ai-hub-settings-mockup.canvas.tsx)", "II-5"),
    8: (f"[Онлайн-чат · виджет]({CANVAS}/online-chat-mockups.canvas.tsx)", "II-6"),
    9: (f"[Онлайн-чат · АРМ]({CANVAS}/online-chat-mockups.canvas.tsx)", "II-7"),
    10: (f"[ИИ-ассистент]({CANVAS}/ai-assistant-ui-mockup.canvas.tsx)", "III-1"),
    11: (f"[ИИ-ассистент · состояния]({CANVAS}/ai-assistant-ui-mockup.canvas.tsx)", "III-2"),
    12: (f"[ИИ-ассистент · генерация]({CANVAS}/ai-assistant-ui-mockup.canvas.tsx)", "III-3"),
    13: (f"[Настройки · базы знаний]({CANVAS}/ai-hub-settings-mockup.canvas.tsx)", "III-4"),
    14: (f"[ИИ-ассистент · саммаризация]({CANVAS}/ai-assistant-ui-mockup.canvas.tsx)", "III-5"),
    15: (f"[ИИ-ассистент · код/RPA]({CANVAS}/ai-assistant-ui-mockup.canvas.tsx)", "III-6"),
    16: (f"[Настройки · RPA]({CANVAS}/ai-hub-settings-mockup.canvas.tsx)", "III-7"),
    17: (f"[ИИ-ассистент · перевод]({CANVAS}/ai-assistant-ui-mockup.canvas.tsx)", "III-8"),
    18: ("—", "IV-1"),
    19: ("—", "IV-2"),
    20: ("—", "IV-3"),
    21: (f"[Настройки · типы документов]({CANVAS}/ai-hub-settings-mockup.canvas.tsx)", "IV-4"),
}

GENERIC = "*Макет: см. [I.8](#i8-сводная-таблица-макетов-ui) и canvas в `canvases/`*"

for n, (link, mid) in SLIDE_LINKS.items():
    old_block = f"**Слайд {n}."
    if old_block not in text:
        continue
    # Replace generic line after each slide header (within next 3 lines)
    pattern = rf"(\*\*Слайд {n}\.[^\n]+\*\*\n\n)\{re.escape(GENERIC)}"
    replacement = rf"\1> **Canvas ({mid}):** {link} · [реестр I.8](#i8-сводная-таблица-макетов-ui)"
    text = re.sub(pattern, replacement, text, count=1)

text = text.replace(GENERIC, "> **Canvas:** см. [I.8.1](#i81-сводка-canvas-v13-кц) и таблицу [I.8](#i8-сводная-таблица-макетов-ui)")

# I.5 block — cleaner links
text = text.replace(
    "- **Телефония:** standalone-панель / окно «Суфлёр» (не вкладка Hub с ассистентом); макет — [canvases/sufer-phone-mockup.canvas.tsx](../../canvases/sufer-phone-mockup.canvas.tsx).\n"
    "- **Чат:** правая панель АРМ ([II.4](#ii4-интерфейс-для-работы-суфлёра--онлайн-чат-2223-432)); макет — [canvases/online-chat-mockups.canvas.tsx](../../canvases/online-chat-mockups.canvas.tsx).\n"
    "- **Внутренний пользователь КЦ (§2.4 п.6):** тестовый диалог с LLM — [canvases/internal-user-kc-mockup.canvas.tsx](../../canvases/internal-user-kc-mockup.canvas.tsx).",
    "- **Телефония:** standalone-панель «Суфлёр» — Canvas [Суфлёр телефония](../../canvases/sufer-phone-mockup.canvas.tsx).\n"
    "- **Чат:** панель в АРМ — Canvas [Онлайн-чат](../../canvases/online-chat-mockups.canvas.tsx) (вкладка «АРМ»).\n"
    "- **Внутренний пользователь КЦ (§2.4 п.6):** Canvas [Тест-диалог КЦ](../../canvases/internal-user-kc-mockup.canvas.tsx).",
)

text = text.replace(
    "Макет — [internal-user-kc-mockup.canvas.tsx](../../canvases/internal-user-kc-mockup.canvas.tsx).",
    "Canvas — [Тест-диалог КЦ](../../canvases/internal-user-kc-mockup.canvas.tsx).",
)

TZ.write_text(text, encoding="utf-8")
print("Fixed mockup format in", TZ)
