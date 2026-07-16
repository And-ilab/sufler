# Замечания к ТЗ: контур AI Hub

Замечания заказчика к переданному зонтичному ТЗ **AI Hub** (Суфлёр · Ассистент · Документы).

## Документ ТЗ (Исполнитель)

| Файл | Описание |
|------|----------|
| [tz-ai-hub-contour.md](../../modules/ai-hub/tz-ai-hub-contour.md) | Итоговое ТЗ v1.1 — Части I–V, Приложение B |

## Связанные материалы

| Материал | Путь |
|----------|------|
| Дополнение: API ассистента | [tz-ai-assistant-belarusbank.md](../../modules/ai-assistant/tz-ai-assistant-belarusbank.md) |
| Эталоны сценариев (Прил.2) | [app2-scenarios/manifest.yaml](../../sources/technical-requirements/app2-scenarios/manifest.yaml) |
| UI-спеки | [ui/](../../ui/) |
| Протоколы совещаний | [sources/meeting-protocols/](../../sources/meeting-protocols/) |

## Файлы замечаний

| Файл | Описание |
|------|----------|
| `TZ-AI-Hub +.docx` | Исходное ТЗ с 46 комментариями заказчика (Солдатенко Е.П., 10–11.06.2026) |
| `TZ-AI-Hub +-ответы-исполнителя.docx` | То же ТЗ **без изменений текста** + 46 ответов исполнителя в threads комментариев Word |
| `add_comment_replies.py` | Скрипт генерации файла с ответами (повторный запуск перезаписывает output) |
| [plan-dorabotok-v1.2.md](./plan-dorabotok-v1.2.md) | **План доработок ТЗ v1.2** по 46 замечаниям |

**Ответы:** на все 46 комментариев заказчика (ответы А. Пономарёва в Word).

### Генерация DOCX с ответами

Из корня репозитория:

```powershell
cd c:\sufler
python docs/remarks/ai-contour/add_comment_replies.py
```

Или из папки замечаний:

```powershell
cd c:\sufler\docs\remarks\ai-contour
python add_comment_replies.py
```

**Вход:** `TZ-AI-Hub +.docx` (только комментарии заказчика, 46 шт.).  
**Выход:** `TZ-AI-Hub +-ответы-исполнителя.docx` — **46 пар вопрос/ответ** (заказчик + ответ А. Пономарёва).

> Закройте файл в Word перед генерацией. Если файл занят, создаётся `… (new).docx`.  
> Для просмотра пар «вопрос → ответ» используйте **Microsoft Word** (режим рецензирования). При импорте в Google Docs ответы могут не отображаться как threads.

Тексты ответов — словарь `RESPONSES` в `add_comment_replies.py`.
