# Продолжение работы: модуль интеграции Oktell и SuflerTelephony

Используйте этот файл при старте **новой ветки чата** в проекте Sufler.

## Промпт для агента

```
Продолжаем модуль интеграции Oktell ↔ SuflerTelephony (суфлёр / КЦ).

Основной документ: docs/integration/oktell-sufler-telephony/tz-oktell-sufler-telephony.md
Протокол (UC, риски): docs/integration/oktell-sufler-telephony/протокол-интеграция-oktell-sufler-telephony.md

Связанная интеграция СУЗ/RAG: docs/integration/suz-bitrix-rag/tz-bitrix-rag-sufler.md

Опирайся на:
- раздел 4 — постановка для администраторов Oktell (OKT-1…10)
- раздел 6 — INT-T01…T11 (WebSocket, dual-leg ASR, RAG, АРМ)
- модель T: серверный WS + on-prem ASR, без Oktell STT и без voiceprint

Стиль ссылок: «раздел N» / «пункт N.M» (без символа §).
```

## Ссылки

| Артефакт | Путь |
|----------|------|
| ТЗ Oktell | `@docs/integration/oktell-sufler-telephony/tz-oktell-sufler-telephony.md` |
| Протокол | `@docs/integration/oktell-sufler-telephony/протокол-интеграция-oktell-sufler-telephony.md` |
| ТЗ СУЗ/RAG | `@docs/integration/suz-bitrix-rag/tz-bitrix-rag-sufler.md` |
| Plan Cursor | `.cursor/plans/oktell_suflertelephony_tz_ef3a7253.plan.md` |

## Проверка целостности (разделы 4–6)

В `tz-oktell-sufler-telephony.md` должны быть заголовки:

- `## 4. Постановка задачи для администраторов Oktell`
- `## 5. Что даёт открытая документация Oktell`
- `## 6. Спецификация обмена Oktell ↔ SuflerTelephony (INT-T01…T11)`
