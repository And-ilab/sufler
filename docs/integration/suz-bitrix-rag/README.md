# Интеграция СУЗ (1С-Битрикс CMS) ↔ RAG суфлёра

**Версия:** v1.2 · **Дата:** 2026-07-14

Документация для согласования с заказчиком (CMS) и Исполнителем (суфлёр). Сводка в едином ТЗ: [tz-unified-v1.4.md Part VI.1](../../modules/ai-hub/tz-unified-v1.4.md#vi1-суз--rag). Приёмка INT-T: [VI.1.7](../../modules/ai-hub/tz-unified-v1.4.md#vi17-приёмка-int-t-интеграция-суз); UC — [протокол](протокол-интеграция-суз-bitrix-rag.md) §8.

## Файлы

| Файл | Кому | Описание |
|------|------|----------|
| **[tz-bitrix-rag-sufler.md](tz-bitrix-rag-sufler.md)** | **Заказчик / Bitrix** | **ТЗ v1.2 (компактное):** модель B; webhook с полным телом; BTX-1…10; реестр INT; ссылки на штатную документацию Bitrix |
| **[TZ-Bitrix-RAG.docx](TZ-Bitrix-RAG.docx)** | Заказчик | Word-экспорт ТЗ v1.2 |
| [протокол-интеграция-суз-bitrix-rag.md](протокол-интеграция-суз-bitrix-rag.md) | Команда проекта | Полный протокол §1–11: контекст, UC, этапы |
| [CONTINUATION.md](CONTINUATION.md) | Разработка | Контекст для продолжения в Cursor |
| [export-to-word.ps1](export-to-word.ps1) | — | Экспорт MD → DOCX |

## Экспорт в Word

```powershell
cd docs\integration\suz-bitrix-rag
.\export-to-word.ps1
```

Либо: `pandoc tz-bitrix-rag-sufler.md -o TZ-Bitrix-RAG.docx --toc --toc-depth=3`

## Модель интеграции

**B (Push с полным телом):** один webhook с метаданными и текстом (`body_html`, `body_plain`). СУЗ и суфлёр — **один контур банка**. Отдельный GET (INT-06) в штатной оперативной синхронизации **не используется** (только INT-10 и резерв).
