# Sufler — руководство по репозиторию

**Проект:** программное обеспечение на базе ИИ для банковских процессов  
**Заказчик:** ОАО «АСБ Беларусбанк» · **Договор:** № 14-03/2026  
**Исполнитель:** ООО «ГС Ритейл»

Единая точка входа в репозиторий `C:\sufler`. Подробный индекс документации — в [`docs/README.md`](docs/README.md).

---

## Быстрый старт

| Задача | Куда идти |
|--------|-----------|
| Текущее единое ТЗ (черновик) | [`docs/modules/ai-hub/tz-unified-v1.4.md`](docs/modules/ai-hub/tz-unified-v1.4.md) |
| Согласованная итерация ТЗ | [`docs/modules/ai-hub/tz-unified-v1.3.md`](docs/modules/ai-hub/tz-unified-v1.3.md) |
| Активный план доработок | [`docs/remarks/plan-dorabotok-v1.4.md`](docs/remarks/plan-dorabotok-v1.4.md) |
| Договорные требования (Прил. 1) | [`docs/sources/technical-requirements/prilozhenie-1.md`](docs/sources/technical-requirements/prilozhenie-1.md) |
| Интерактивные макеты UI | [`canvases/`](canvases/) |
| Прототип АРМ оператора | [`dashboard/app/`](dashboard/app/) |

---

## Карта репозитория

```
sufler/
├── docs/              ← документация (источники, ТЗ, замечания, UI, HR)
├── canvases/          ← интерактивные макеты (Cursor Canvas)
├── dashboard/         ← прототип Django: АРМ оператора онлайн-чата
├── recognizer/        ← прототип ASR (Vosk, WebSocket)
├── _extracted/        ← рабочие текстовые выгрузки из DOCX (не канон)
├── _*.py, _*.md       ← рабочие скрипты и черновики (не канон)
└── .cursor/           ← правила и настройки Cursor IDE
```

---

## 1. Документация (`docs/`)

### Слои

| Слой | Путь | Назначение |
|------|------|------------|
| **Исходники заказчика** | [`docs/sources/`](docs/sources/) | Входящие материалы: договор, протоколы, AD, SIEM, Oktell, СУЗ |
| **ТЗ и спецификации** | [`docs/integration/`](docs/integration/), [`docs/modules/`](docs/modules/), [`docs/ui/`](docs/ui/) | Рабочие документы исполнителя для согласования и разработки |
| **Замечания** | [`docs/remarks/`](docs/remarks/) | Обратная связь заказчика по переданным ТЗ |
| **HR** | [`docs/hr/`](docs/hr/) | Требования к вакансиям |

> Технические `протокол-интеграция-*.md` в `integration/` — **не** протоколы совещаний. Протоколы встреч — в [`docs/sources/meeting-protocols/`](docs/sources/meeting-protocols/).

### Модули продукта

| Модуль | Путь | Ключевой файл |
|--------|------|---------------|
| **Контур AI Hub** (зонтичное ТЗ) | [`docs/modules/ai-hub/`](docs/modules/ai-hub/) | `tz-unified-v1.4.md` |
| **ИИ-ассистент** (API-дополнение) | [`docs/modules/ai-assistant/`](docs/modules/ai-assistant/) | `tz-ai-assistant-belarusbank.md` |

**Структура единого ТЗ v1.4** (§2.2 Прил. 1):

| Часть | Содержание |
|-------|------------|
| **0** | Реквизиты документа (ГОСТ §1) |
| **I** | Общие положения, глоссарий, роли, ИБ, LDAPS, портальный лаунчер |
| **II** | Модуль Контакт-центра (суфлёр, онлайн-чат, отчётность) |
| **III** | Модуль ИИ-ассистент |
| **IV** | Модуль распознавания документов |
| **V** | Модуль LLM |
| **VI** | Интеграции (СУЗ, Oktell, SIEM/KUMA) |
| **VII** | Работы, приёмка, документирование, открытые вопросы |
| **Прил. A–D** | Согласование, сценарии, источники, индекс замечаний |

### Интеграции

| Интеграция | Путь | Версия ТЗ | Раздел unified |
|------------|------|-----------|----------------|
| Oktell ↔ суфлёр | [`docs/integration/oktell-sufler-telephony/`](docs/integration/oktell-sufler-telephony/) | v0.1 | Part VI.2 |
| СУЗ ↔ RAG (1С-Битрикс) | [`docs/integration/suz-bitrix-rag/`](docs/integration/suz-bitrix-rag/) | v1.2 | Part VI.1 |
| Онлайн-чат (АРМ КЦ) | [`docs/integration/online-chat/`](docs/integration/online-chat/) | v0.1 | Part II.5 |

### Исходники заказчика

| Категория | Папка |
|-----------|-------|
| Технические требования (Прил. 1–2) | [`technical-requirements/`](docs/sources/technical-requirements/) |
| Протоколы совещаний | [`meeting-protocols/`](docs/sources/meeting-protocols/) |
| Active Directory | [`active-directory/`](docs/sources/active-directory/) |
| SIEM (Kaspersky KUMA) | [`siem/`](docs/sources/siem/) |
| Oktell (документация вендора) | [`oktell/`](docs/sources/oktell/) |
| СУЗ (система управления знаниями) | [`suz/`](docs/sources/suz/) |
| Анкета киберустойчивости | [`анкета по киберустойчивости/`](docs/sources/анкета%20по%20киберустойчивости/) |

### Замечания к переданным ТЗ

| ТЗ | Папка | План доработок |
|----|-------|----------------|
| Контур AI Hub | [`ai-contour/`](docs/remarks/ai-contour/) | [`plan-dorabotok-v1.4.md`](docs/remarks/plan-dorabotok-v1.4.md) |
| Онлайн-чат | [`online-chat/`](docs/remarks/online-chat/) | ↑ |
| СУЗ ↔ RAG | [`suz-integration/`](docs/remarks/suz-integration/) | ↑ |

---

## 2. Технические задания — версии и статус

### Единое ТЗ (AI Hub)

| Файл | Версия | Дата | Статус |
|------|--------|------|--------|
| `tz-unified-v1.4.md` | v1.4 | 2026-07-08 | **Текущая работа** — протоколы 02.07 / 06.07 |
| `tz-unified-v1.3.md` | v1.3 | 2026-06-26 | Согласованная итерация (253 комм. 23.06) |
| `tz-unified-v1.2.md` | v1.2 | 2026-06-14 | Архив |
| `tz-ai-hub-contour.md` | v1.1 | 2026-06-08 | Архив / источник переноса |

Word-экспорты: `TZ-unified-v1.2.docx`, `TZ-unified-v1.3.docx`, `TZ-unified-v1.4.docx`, `TZ-unified-v1.4-internal.docx`.

### Модульные и интеграционные ТЗ

| Файл | Версия | Дата |
|------|--------|------|
| `integration/online-chat/tz-online-chat-platform.md` | v0.1 | 2026-06-03 |
| `integration/suz-bitrix-rag/tz-bitrix-rag-sufler.md` | v1.2 | 2026-07-14 |
| `integration/oktell-sufler-telephony/tz-oktell-sufler-telephony.md` | v0.1 | 2026-06-07 |
| `modules/ai-assistant/tz-ai-assistant-belarusbank.md` | v0.2 | 2026-06-08 |

### Договорный источник истины

| Файл | Роль |
|------|------|
| `docs/sources/technical-requirements/prilozhenie-1.md` | **Приложение 1** — главный договорный источник |
| `docs/sources/technical-requirements/app2-scenarios/manifest.yaml` | **Приложение 2** — 10 эталонных сценариев (CC-SCR-001…010) |

---

## 3. Макеты интерфейсов

### Cursor Canvas (`canvases/`)

Интерактивные React-макеты для согласования с заказчиком.

| Canvas | Назначение |
|--------|------------|
| `tray-launcher-mockup.canvas.tsx` | Портальный лаунчер AI Hub → «Суфлёр \| Ассистент» |
| `sufer-phone-mockup.canvas.tsx` | Суфлёр телефонии — реплики, подсказки, % релевантности |
| `ai-assistant-ui-mockup.canvas.tsx` | Окно ИИ-ассистента |
| `ai-hub-panel-mockup.canvas.tsx` | Панель AI Hub (FAB, RBAC, вкладки) |
| `online-chat-mockups.canvas.tsx` | АРМ оператора чата |
| `internal-user-kc-mockup.canvas.tsx` | Тест промптов внутреннего пользователя КЦ |
| `ai-hub-settings-mockup.canvas.tsx` | Центр настроек `/ai-hub/admin` |
| `ocr-documents-mockup.canvas.tsx` | Модуль распознавания документов |

**Backlog (в ТЗ, ещё не в репо):** `widget-sites-mockup`, `widget-client-mockup`, `reporting-builder-mockup`.

### Markdown-спеки UI (`docs/ui/`)

| Файл | Описание |
|------|----------|
| `ai-hub-panel-mockup.md` | Правая панель AI Hub: FAB, RBAC, 3 вкладки |
| `ai-hub-settings-mockup.md` | Админ-центр — 18 экранов, LLM, промпты, сценарии |

---

## 4. Прототипы кода

### Dashboard — АРМ оператора (`dashboard/app/`)

**Стек:** Django 5 · SQLite · channels · websockets

Прототип операторского рабочего места онлайн-чата: регистрация клиента, сессии по каналам, история сообщений, отчёты.

| Модель | Назначение |
|--------|------------|
| `Client` | Профиль клиента (имя, телефон, email, UUID сессии) |
| `ChatSession` | Сессия чата/звонка (chat, Telegram, Viber, WhatsApp, phone) |
| `Message` | Сообщения (клиент, оператор, рекомендация ИИ, ответ ИИ) |
| `CallLog` | Длительность и транскрипция звонка |

| Маршрут | Назначение |
|---------|------------|
| `/` | Главная |
| `/client-info/` | Регистрация клиента |
| `/chat/` | Интерфейс чата |
| `/dashboard/` | История сессий |
| `/reports/` | Статистика |
| `/api/*` | REST API |

### Recognizer — ASR-прототип (`recognizer/`)

Dev-прототип потокового распознавания речи: Vosk `vosk-model-ru-0.22` + WebSocket (`main.py`).

> В production-ТЗ ASR — on-prem streaming (вендор TBD); встроенный STT Oktell (Yandex/Google) **исключён**.

---

## 5. Модели и компоненты ИИ (по ТЗ)

| Компонент | Технология | Контекст |
|-----------|------------|----------|
| **ASR** | On-prem streaming (prod); Vosk (dev) | Part II, FR-ASR-*; dual-leg audio Oktell |
| **QU** (понимание запросов) | Embedding + cosine similarity | FR-UND-04/06 |
| **RAG** | Vector store + chunking/embedding | KB: `cc_production`, `assistant_*` |
| **LLM** | On-prem generative (вендор не фиксирован) | Part V; профили `sufler_cc`, `assistant_bank` |
| **OCR** | Модуль распознавания документов | Part IV |

**HR-стек** (см. [`docs/hr/trebovaniya-python-developer.md`](docs/hr/trebovaniya-python-developer.md)): LangChain/LlamaIndex, Vosk/Whisper/Kaldi, RAG pipeline.

---

## 6. Рабочие скрипты (корень, префикс `_`)

> Эфемерные артефакты — **не** каноническая документация.

| Группа | Файлы | Назначение |
|--------|-------|------------|
| Анкета ИБ | `_setup_anketa_folder.py`, `_gen_all_ib_docs.py`, `_gen_cyber_docs.py`, `_finalize_anketa_package.py`, `_export_ib_docx.py` | Генерация документов киберустойчивости |
| Извлечение | `_extract_meeting_docs.py` | Текст + комментарии Word из DOCX → `_extracted/` |
| Патчи ТЗ | `_patch_tz_ii7.py`, `_tmp_tz.py` | Точечные правки unified ТЗ |
| Черновики | `_i1_current.md`, `_part2_current.md`, `_vii2.md`, `_appd.md` | Рабочие фрагменты частей ТЗ |
| Планирование | `_plan22.md`, `_plan.txt` | Заметки итераций |

---

## 7. Cursor IDE (`.cursor/`)

| Файл | Назначение |
|------|------------|
| [`rules/tz-gost-34602.mdc`](.cursor/rules/tz-gost-34602.mdc) | Правило редактирования ТЗ: ГОСТ 34.602-2020, Прил. 1, формат FR (Вход → Под капотом → Выход → Приёмка) |
| `settings.json` | Настройки плагинов (Figma) |

---

## 8. Поток документов

```
docs/sources/                    docs/modules/ + docs/integration/
(Прил.1, протоколы,                    │
 AD, Oktell, СУЗ)                      ▼
        │                    docs/remarks/ (замечания заказчика)
        └──────────────────────────────┤
                                       ▼
                              canvases/ + docs/ui/
                              (макеты для согласования)
                                       ▼
                              dashboard/ + recognizer/
                              (прототипы реализации)
```

---

## 9. Конвенции

- **Исходники заказчика** → только `docs/sources/`; не дублировать наши `tz-*.md`.
- **ТЗ исполнителя** → `docs/integration/`, `docs/modules/`.
- **Замечания** → `docs/remarks/` после передачи ТЗ на согласование.
- **Имена файлов:** латиница, kebab-case; протоколы встреч — `YYYY-MM-DD-тема.md`.
- **Приоритет источников при редактировании ТЗ:** Прил. 1 → ГОСТ 34.602 → plan-dorabotok → протоколы → `docs/sources/`.
- **Рабочие скрипты** с префиксом `_` — временные; не включать в поставку.

---

## 10. Навигация по README в подпапках

| README | Путь |
|--------|------|
| Индекс документации | [`docs/README.md`](docs/README.md) |
| Исходники заказчика | [`docs/sources/README.md`](docs/sources/README.md) |
| Контур AI Hub | [`docs/modules/ai-hub/README.md`](docs/modules/ai-hub/README.md) |
| ИИ-ассистент | [`docs/modules/ai-assistant/README.md`](docs/modules/ai-assistant/README.md) |
| Oktell ↔ суфлёр | [`docs/integration/oktell-sufler-telephony/README.md`](docs/integration/oktell-sufler-telephony/README.md) |
| СУЗ ↔ RAG | [`docs/integration/suz-bitrix-rag/README.md`](docs/integration/suz-bitrix-rag/README.md) |
| Онлайн-чат | [`docs/integration/online-chat/README.md`](docs/integration/online-chat/README.md) |
| Замечания | [`docs/remarks/README.md`](docs/remarks/README.md) |
| HR | [`docs/hr/README.md`](docs/hr/README.md) |
