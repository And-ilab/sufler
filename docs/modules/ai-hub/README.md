# Контур AI Hub — документация

**Версия:** v1.4 (работа) · **Дата:** 2026-07-08 · **Проект:** ПО на базе ИИ · Заказчик: ОАО «АСБ Беларусбанк»

Документация для **согласования с заказчиком**: единое ТЗ на контур **AI Hub** (оболочка) и договорные модули **[Прил.1 §2.2]** в рамках договора № 14-03/2026.

## Файлы

| Файл | Описание |
|------|----------|
| **[tz-unified-v1.4.md](tz-unified-v1.4.md)** | **Единое ТЗ v1.4** — текущая итерация (ВКС 02.07 + 06.07.2026) |
| [tz-unified-v1.3.md](tz-unified-v1.3.md) | Единое ТЗ v1.3 — предыдущая согласованная редакция |
| [tz-unified-v1.2.md](tz-unified-v1.2.md) | Единое ТЗ v1.2 — архив |
| [tz-ai-hub-contour.md](tz-ai-hub-contour.md) | ТЗ v1.1 — архив / источник для переноса содержания |
| [export-unified-to-word.ps1](export-unified-to-word.ps1) | Экспорт `tz-unified-v1.4.md` → `TZ-unified-v1.4.docx` (параметр `-Version`) |

## План доработок v1.4

[plan-dorabotok-v1.4.md](../../remarks/plan-dorabotok-v1.4.md) — 129 комментариев Word + протоколы 02.07 / 06.07.

## Структура единого ТЗ v1.4

| Часть | Содержание (§2.2 Прил.1) |
|-------|--------------------------|
| **0** | Реквизиты документа (ГОСТ §1) |
| **I** | Общие положения, глоссарий, роли §2.4, ИБ, LDAPS, **портальный лаунчер** |
| **II** | **модуль Контакт-центра** (понимание запросов, интерфейсы суфлёра, онлайн-чат, «Отчетность») |
| **III** | **модуль ИИ-ассистент** |
| **IV** | **модуль распознавания документов** |
| **V** | **модуль LLM** (§3) |
| **VI** | Интеграции (СУЗ, Oktell, SIEM/KUMA) |
| **VII** | Работы, приёмка, документирование, открытые вопросы |
| **Прил. A–D** | Согласование, сценарии, источники, **индекс замечаний v1.4** |

## Интерактивные макеты (Cursor Canvas)

| Canvas | Содержание |
|--------|------------|
| `tray-launcher-mockup.canvas.tsx` | **Портальный лаунчер** AI Hub → «Суфлёр \| Ассистент», два окна |
| `sufer-phone-mockup.canvas.tsx` | Суфлёр телефония — реплики, 3–5 подсказок, % |
| `ai-assistant-ui-mockup.canvas.tsx` | Окно ИИ-ассистента (отдельно от суфлёра) |
| `online-chat-mockups.canvas.tsx` | АРМ чата — панель суфлёра |
| `internal-user-kc-mockup.canvas.tsx` | Тест промптов внутреннего пользователя КЦ |
| `ai-hub-settings-mockup.canvas.tsx` | Центр настроек `/ai-hub/admin` |

**Резерв / backlog (I.8.1):** `widget-sites-mockup`, `widget-client-mockup`, `reporting-builder-mockup` и др. — см. [I.8.1](tz-unified-v1.4.md#i81-резерв-и-backlog-макетов-v14) в ТЗ.

Путь: `%USERPROFILE%\.cursor\projects\c-sufler\canvases\`

## Справочные ТЗ

| Документ | Перенос в |
|----------|-----------|
| [tz-online-chat-platform.md](../../integration/online-chat/tz-online-chat-platform.md) | Part II.5 |
| [tz-bitrix-rag-sufler.md](../../integration/suz-bitrix-rag/tz-bitrix-rag-sufler.md) | Part VI.1 |
| [tz-oktell-sufler-telephony.md](../../integration/oktell-sufler-telephony/tz-oktell-sufler-telephony.md) | Part VI.2 |
| [tz-ai-assistant-belarusbank.md](../ai-assistant/tz-ai-assistant-belarusbank.md) | Part III (API) |

## Порядок согласования

1. Часть I — глоссарий §1, роли §2.4, лаунчер I.5, ИБ, LDAPS.
2. Часть II — модуль Контакт-центра (суфлёр, чат, отчётность).
3. Части III–V — ИИ-ассистент, OCR, модуль LLM.
4. Часть VI — интеграции.
5. Часть VII + приложения A–D — приёмка, поставка, индекс замечаний.
