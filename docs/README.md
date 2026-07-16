# Документация проекта Sufler

**Заказчик:** ОАО «АСБ Беларусбанк» · **Договор:** № 14-03/2026

> Полное руководство по репозиторию (код, макеты, модели, скрипты) — в корневом [`README.md`](../README.md).

## Слои документации

| Слой | Путь | Назначение |
|------|------|------------|
| **Исходники заказчика** | [`sources/`](sources/) | Входящие материалы: договор (Прил.1–2), протоколы совещаний с поручениями, доки AD / SIEM / Oktell / СУЗ |
| **ТЗ и спецификации (Исполнитель)** | [`integration/`](integration/), [`modules/`](modules/), [`ui/`](ui/) | Наши рабочие документы для согласования и разработки |
| **Замечания к переданным ТЗ** | [`remarks/`](remarks/) | Обратная связь заказчика по нашим ТЗ после передачи на согласование |
| **HR / подбор** | [`hr/`](hr/) | Требования к вакансиям, профили должностей |

> Технические `протокол-интеграция-*.md` в `integration/` — **не** протоколы совещаний. Протоколы встреч с поручениями — в [`sources/meeting-protocols/`](sources/meeting-protocols/).

## Исходники заказчика — [`sources/`](sources/)

| Категория | Папка |
|-----------|-------|
| Технические требования (Приложение 1) | [technical-requirements/](sources/technical-requirements/) |
| Протоколы совещаний с поручениями | [meeting-protocols/](sources/meeting-protocols/) |
| Active Directory | [active-directory/](sources/active-directory/) |
| SIEM | [siem/](sources/siem/) |
| Oktell (исходная документация) | [oktell/](sources/oktell/) |
| СУЗ (система управления знаниями) | [suz/](sources/suz/) |
| Анкета киберустойчивости | [анкета по киберустойчивости/](sources/анкета%20по%20киберустойчивости/) |

## Замечания к переданным ТЗ — [`remarks/`](remarks/)

| ТЗ | Папка |
|----|-------|
| Интеграция СУЗ ↔ RAG | [suz-integration/](remarks/suz-integration/) |
| Модуль «Онлайн-чат» | [online-chat/](remarks/online-chat/) |
| Контур AI Hub | [ai-contour/](remarks/ai-contour/) |

## ТЗ и интеграции — Исполнитель

| Область | Путь |
|---------|------|
| Контур AI Hub (зонтичное ТЗ) | [modules/ai-hub/](modules/ai-hub/) |
| Модуль «Ассистент» | [modules/ai-assistant/](modules/ai-assistant/) |
| Oktell ↔ суфлёр | [integration/oktell-sufler-telephony/](integration/oktell-sufler-telephony/) |
| СУЗ ↔ RAG | [integration/suz-bitrix-rag/](integration/suz-bitrix-rag/) |
| Онлайн-чат | [integration/online-chat/](integration/online-chat/) |

## UI

| Тип | Путь |
|-----|------|
| Markdown-спеки | [ui/](ui/) |
| Интерактивные макеты (Cursor Canvas) | `canvases/` в корне репозитория |
