# Замечания к ТЗ: модуль «Онлайн-чат»

Замечания заказчика к переданному ТЗ платформы онлайн-чата и АРМ оператора.

## Документ ТЗ (Исполнитель)

| Файл | Описание |
|------|----------|
| [tz-online-chat-platform.md](../../integration/online-chat/tz-online-chat-platform.md) | Итоговое ТЗ — сценарии, функционал, макеты, приёмка |

## Связанные материалы

| Материал | Путь |
|----------|------|
| Техническая спецификация (команда) | [протокол-online-chat.md](../../integration/online-chat/протокол-online-chat.md) |
| Макеты интерфейсов | [makety-interfeysov.md](../../integration/online-chat/makety-interfeysov.md) |
| Протоколы совещаний | [sources/meeting-protocols/](../../sources/meeting-protocols/) |

## Файлы замечаний

| Файл | Описание |
|------|----------|
| `Чат коррект.docx` | Исходное ТЗ v0.1 с 17 правками заказчика (Деева С.В., Track Changes) |
| `Чат коррект +-ответы-исполнителя.docx` | То же ТЗ **без изменений текста** + **17 пар** комментариев: замечание (**Деева С.В.**) → ответ (**Андрей Пономарев**); правки — в Track Changes |
| [plan-dorabotok-v1.2.md](./plan-dorabotok-v1.2.md) | **План доработок** модуля «Онлайн-чат» для единого ТЗ v1.2 |
| [add_comment_replies.py](./add_comment_replies.py) | Скрипт генерации DOCX с ответами |

### Генерация DOCX с ответами

```powershell
cd c:\sufler\docs\remarks\online-chat
python add_comment_replies.py
```

**Вход:** `Чат коррект.docx` · **Выход:** `Чат коррект +-ответы-исполнителя.docx` (перезаписывается).
