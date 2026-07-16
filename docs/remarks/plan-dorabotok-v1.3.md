# План доработок единого ТЗ v1.3

**Дата:** 2026-06-26  
**Основание:** 253 комментария заказчика (22–23.06.2026) + [протокол ВКС 23.06](23%2006%202026/протокол-2026-06-23.md)  
**Исходная версия:** [tz-unified-v1.2.md](../modules/ai-hub/tz-unified-v1.2.md)  
**Целевая версия:** **[tz-unified-v1.3.md](../modules/ai-hub/tz-unified-v1.3.md)**  
**Реестр комментариев:** [_comments_extracted.txt](23%2006%202026/_comments_extracted.txt)

> Планы v1.2 по областям (**не дублировать** — только ссылки): [ai-contour/plan-dorabotok-v1.2.md](ai-contour/plan-dorabotok-v1.2.md) · [online-chat/plan-dorabotok-v1.2.md](online-chat/plan-dorabotok-v1.2.md) · [suz-integration/plan-dorabotok-v1.2.md](suz-integration/plan-dorabotok-v1.2.md)

---

## Цель v1.3

Закрыть разрыв ожиданий: не перенос ТТ, а **описание реализации** (вход → под капотом → выход → приёмка), **листовая трассировка** подпунктов ТТ, макеты canvas, структурные дыры ГОСТ (VII.3, Прил. B, Прил. D).

---

## Статистика комментариев

| Источник | Файл | Комм. |
| -------- | ---- | ----- |
| ДИТ | `TZ-unified-v1.2.docx_коммент.ДИТ.docx` | 35 |
| ДИТ2 | `TZ-unified-v1.2.docx_коммент.ДИТ2.docx` | 44 |
| Онлайн-чат | `TZ-unified-v1.2.docx_чат.docx` | 36 |
| КЦ / суфлёр | `TZ-unified-v1.2_МИХ.docx` | 138 |
| **Итого** | | **253** |

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
| Формат FR/UC | Блок вход/под капотом/выход/приёмка | [I.1.2](../modules/ai-hub/tz-unified-v1.3.md#i12-формат-описания-функции-v13) |
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
| §4.4 функции | [II.5.10](../modules/ai-hub/tz-unified-v1.3.md#ii510-дополнительные-функции-§444) | online-chat «Post-chat» |
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
