# Интеграция Oktell ↔ SuflerTelephony (суфлёр)

**Версия:** v0.1 (планирование) · **Дата:** 2026-06-07

Документация для согласования с заказчиком (телефония / Oktell) и Исполнителем (модуль SuflerTelephony, ASR, RAG, АРМ оператора).

## Файлы

| Файл | Кому | Описание |
|------|------|----------|
| **[tz-oktell-sufler-telephony.md](tz-oktell-sufler-telephony.md)** | **Заказчик / Oktell + Исполнитель** | **Итоговое ТЗ v0.1:** модель **T** (WebSocket события + dual-leg ASR on-prem + RAG) |
| [протокол-интеграция-oktell-sufler-telephony.md](протокол-интеграция-oktell-sufler-telephony.md) | Команда проекта | UC оператора, риски, этапы, расширенный чек-лист |
| [CONTINUATION.md](CONTINUATION.md) | Разработка | Контекст для продолжения в Cursor |

## Связанные документы

| Интеграция | Путь |
|------------|------|
| СУЗ ↔ RAG | [docs/integration/suz-bitrix-rag/](../suz-bitrix-rag/README.md) |
| UI АРМ (вкладка «Суфлёр») | [docs/ui/ai-hub-panel-mockup.md](../../ui/ai-hub-panel-mockup.md) |
| Прототип ASR (dev) | [recognizer/main.py](../../../recognizer/main.py) |

## Модель интеграции

**T (Telephony push + dual-leg ASR):**

1. **Серверный WebSocket** Oktell → SuflerTelephony: `phoneevent_ringstarted`, `phoneevent_commstarted`, `phoneevent_commstopped` и подписка `subscribeevent`.
2. **Dual-leg запись** Oktell (2 файла на участника) → **on-prem ASR** суфлёра; роль спикера из метаданных Oktell (`operator` / `client`).
3. Транскрипт клиента → **RAG** (production-индекс СУЗ) → подсказки в **АРМ оператора**.
4. **Oktell.js** в браузере — опционально только для UI телефонии; **не** источник учёта звонков и транскрипта.

STT компонентов Oktell (Yandex/Google SpeechKit) **не используем**. Голосовой слепок **не применяем**.

## Экспорт в Word / Google Docs

1. Откройте `tz-oktell-sufler-telephony.md`.
2. **Word:** Файл → Открыть `.md` → Сохранить как `.docx`.
3. **Pandoc:** `pandoc tz-oktell-sufler-telephony.md -o TZ-Oktell.docx --toc`
4. **Mermaid:** диаграммы — [mermaid.live](https://mermaid.live) → PNG → вставка в документ.
