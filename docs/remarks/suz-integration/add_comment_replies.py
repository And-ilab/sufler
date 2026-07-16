#!/usr/bin/env python3
"""Add threaded executor replies to TZ-Bitrix-RAG_MIX.docx (body unchanged)."""

from __future__ import annotations

import random
import re
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
W14 = "{http://schemas.microsoft.com/office/word/2010/wordml}"
W15 = "{http://schemas.microsoft.com/office/word/2012/wordml}"

AUTHOR = "Андрей Пономарев"
INITIALS = "АП"
REPLY_DATE = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

SRC = Path(__file__).parent / "TZ-Bitrix-RAG_MIX.docx"
OUT = Path(__file__).parent / "TZ-Bitrix-RAG +-ответы-исполнителя.docx"
WORK = Path(__file__).parent / "_reply_work"

TZ = "едином ТЗ v1.2"
MOD = "раздел «Интеграция СУЗ ↔ суфлёр»"

# Parent Word comment ids whose executor replies should be refreshed on re-run.
REFRESH_PARENT_IDS = frozenset({
    "16", "28", "30", "31", "32", "33", "34", "35", "83", "86", "159", "162",
    "177", "178", "179", "180", "181",
})

# None = без ответа (замечания к ДИТ / CMS)
RESPONSES: dict[str, str | None] = {
    "0": (
        f"Принято. В {TZ} заголовок и термины {MOD} приведём к Прил. 1 §1 "
        "(СУЗ, Суфлёр, база знаний LLM, ретривер). Интеграцию с СУЗ привяжем к §7.1 "
        "и §4.5.1.3–4.5.1.6. Термины «RAG» и «CMS» в заголовке уберём — в ТТ их нет; "
        "для СУЗ указано «1С-Битрикс: Система управления сайтом»."
    ),
    "1": (
        f"Согласны. В {TZ} добавим колонку «ТТ» в таблицы требований, INT и приёмки "
        "и сводную таблицу «пункт Прил. 1 → раздел → сценарий → приёмка» в общем вводном разделе."
    ),
    "2": (
        "Принято. Поле «Проект» уберём или заменим на наименование из договора: "
        "«Работы по кастомизации и внедрению ПО на базе ИИ для ОАО «АСБ Беларусбанк»» "
        f"(Прил. 1 к договору), без внутренних формулировок исполнителя."
    ),
    "3": (
        "Описание моделей интеграции A (короткий webhook + GET) и B (полный текст в POST), "
        f"сравнение и обоснование выбора B — в §3.7–3.8 {TZ}. "
        "В модели B webhook содержит метаданные и полный текст статьи "
        "(`body_html`, `body_plain`, `title`, `event_id`, `status`, `version_id` и др.). "
        f"Термины «webhook», «payload», «event_id» в ТТ не определены — "
        f"опишем дополнительно в глоссарии {TZ}; перечень полей — в §6.2."
    ),
    "12": None,  # ДИТ
    "13": None,  # ДИТ
    "14": None,  # ДИТ
    "15": (
        f"Принято. В ТТ (Прил. 1 §8–9) нет термина «ЦК» и нет названия подразделения — "
        "есть «требования информационной безопасности»; аббревиатура ИБ используется "
        "в §8.12 (ТТП ИБ 2.1-2020), §9.1.9 (события ИБ). "
        f"Строку «Подразделение по…» из текста уберём. "
        f"В глоссарии {TZ}: ИБ — требования §8–9 Прил. 1, согласование с Заказчиком. "
        "Не путаем с КЦ (Контакт-центр, §2.4 ТТ)."
    ),
    "16": (
        "Согласны: ручной replay не должен быть основным способом доставки. "
        "Штатная эксплуатация — автоматически: при сохранении/публикации статьи "
        "модуль sync формирует payload и кладёт запись в outbox (BTX-2), затем "
        "отправляет HTTP POST в суфлёр; при сбое (503, timeout) — автоматический "
        "retry с тем же event_id (BTX-3), а также досылка failed агентом по "
        "расписанию (BTX-7, напр. каждые 15 мин) — без участия человека. "
        "Replay вручную — только резерв (BTX-8): если автоматические повторы "
        "исчерпаны или нужна разовая досылка по инциденту — администратор СУЗ "
        "нажимает кнопку replay в журнале модуля bank.sufler.sync; "
        "повторно уходит тот же event_id и payload — это не правка текста статьи. "
        f"В глоссарии {TZ} уточним формулировку: «Replay — ручная досылка "
        "(fallback)»; термины «outbox», «event_id», «replay» в ТТ не определены — "
        f"опишем дополнительно."
    ),
    "17": (
        f"Принято. Термин «рабочий индекс» (production-индекс) в ТТ не определён — "
        f"опишем дополнительно в глоссарии {TZ} "
        "(поисковый индекс суфлёра только для опубликованных статей КЦ). "
        f"В {MOD} — «см. глоссарий»."
    ),
    "18": (
        f"Принято. Правило для {TZ}: термины из ТТ — дублируем из Прил. 1 §1 "
        "(с указанием пункта ТТ); термины, которых в ТТ нет (outbox, payload, replay и др.), — "
        f"дополнительно описываем в глоссарии. Каждый термин — один раз; "
        f"в {MOD} далее только ссылка «см. глоссарий»."
    ),
    "19": (
        f"Согласны. Текущее определение СУЗ в тексте не совпадает с ТТ. "
        f"В глоссарии {TZ} продублируем определение из Прил. 1 §1 (со ссылкой на пункт ТТ). "
        f"В {MOD} — «см. глоссарий», без повторного текста."
    ),
    "20": (
        f"Согласны. Текущее определение («ПО с RAG + LLM…») не из ТТ. "
        f"В глоссарии {TZ} продублируем определение «Суфлёр» из Прил. 1 §1 дословно "
        f"(со ссылкой на пункт ТТ). В {MOD} — «см. глоссарий»."
    ),
    "21": (
        f"Принято. Роли из Прил. 1 §2.4 продублируем в глоссарии {TZ} "
        f"(со ссылкой на пункт ТТ). Организационную роль «Редактор СУЗ» уберём "
        "(см. ответ к id=25). В {MOD} — «см. глоссарий»."
    ),
    "22": (
        f"Принято. Каждый термин — одно определение в глоссарии {TZ}: "
        "из ТТ — дублируем с указанием пункта; новые — описываем дополнительно. "
        f"В {MOD} — только ссылка «см. глоссарий», без повторов."
    ),
    "23": (
        f"Принято. Роль «Внутренний пользователь» из Прил. 1 §2.4 продублируем "
        f"в глоссарии {TZ} (со ссылкой на пункт ТТ). Уточним область применения суфлёра для КЦ "
        "и внутренних пользователей."
    ),
    "25": (
        "Согласны. Кто вносит информацию в СУЗ — вне предмета интеграционного раздела. "
        "Editor_SUZ на диаграммах — технический актор события в CMS, не организационная роль."
    ),
    "26": (
        f"Принято. «Оператор КЦ» приведём к формулировкам Прил. 1 §2.4 "
        f"и продублируем в глоссарии {TZ} (со ссылкой на пункт ТТ)."
    ),
    "27": (
        f"АРМ в ТТ не определён — опишем дополнительно в глоссарии {TZ} "
        "(автоматизированное рабочее место оператора: модули «Суфлёр», онлайн-чат, телефония). "
        f"В {MOD} — «см. глоссарий»."
    ),
    "28": (
        "Да, используется: в §6 (payload, INT-10), матрице BTX и маппинге полей CMS. "
        "Термин в ТТ не определён — опишем дополнительно в глоссарии "
        f"{TZ}. В тексте — «см. глоссарий»."
    ),
    "29": (
        "Да, попадают. Таблицы, спойлеры, тултипы — часть HTML-текста статьи СУЗ (DETAIL_TEXT). "
        "Модуль sync передаёт их вместе с текстом в поле body_html webhook — "
        "не как отдельные объекты CMS. "
        f"Термин «сериализация» (представление данных статьи в JSON payload) в ТТ не определён — "
        f"опишем дополнительно в глоссарии {TZ}."
    ),
    "30": (
        "Да, используется: в payload (`article_id`), сценариях INT и критериях приёмки §4.6. "
        f"В ТТ не определён — опишем дополнительно в глоссарии {TZ}."
    ),
    "31": (
        "Да, используется: в payload (`section_id`), правилах области индексации для КЦ "
        f"(BTX-4) и фильтрах индекса. В ТТ не определён — опишем дополнительно в глоссарии {TZ}."
    ),
    "32": (
        "Да, используется: в payload (`status=draft`), сценариях INT и правилах индексации — "
        "черновик передаётся в обмене, но не попадает в рабочий RAG-индекс. "
        f"В ТТ не определён — опишем дополнительно в глоссарии {TZ}. В тексте — «см. глоссарий»."
    ),
    "33": (
        "Когда статья получает статус published, это триггер события: статья попадает "
        "в область индексации КЦ и отправляется на обновление в Суфлёр. "
        "Проще: опубликовали статью → сработало событие → Суфлёр обновил индекс. "
        f"Более подробно триггер и условия срабатывания опишем в {TZ}."
    ),
    "34": (
        "Под «permalink» здесь имеется в виду постоянная (стабильная) ссылка на статью в СУЗ: "
        "один и тот же URL для конкретной статьи, по которому оператор может открыть источник "
        "из подсказки суфлёра. Даже при обновлении содержимого статьи ссылка остаётся той же. "
        f"В ТТ отдельным термином не определён — добавим в глоссарий {TZ}."
    ),
    "35": (
        "В ТТ отдельного термина «visibility_scope» нет. В Приложении 1 логика доступа описана "
        "через роли, права и область применения (для КЦ и внутренних пользователей, §2.4). "
        "В интеграционном модуле это формализуем как поле payload «область видимости» "
        "(`visibility_scope`), которое модуль sync вычисляет по правилам банка (разделы, права). "
        f"Ссылку на пункты ТТ добавим в {TZ}."
    ),
    "36": (
        "Целевая модель определяется правилами BTX-4: какие изменения дают event_type published/unpublished, "
        "какие разделы в whitelist КЦ, как формируется version_id."
    ),
    "37": (
        f"Принято. Формулировка: СУЗ — авторитетный источник контента для индексации и подсказок суфлёра "
        "(п. ТТ о базе знаний LLM). «Для ответов КЦ» уберём."
    ),
    "38": "Уточнение к п. ТТ о единственном источнике знаний для суфлёра; в v1.2 оставим один раз в глоссарии.",
    "39": (
        "Черновик статьи в CMS (status=draft) в production-индекс RAG не попадает. "
        "Черновики Битрикса без публикации не индексируются."
    ),
    "40": None,  # ДИТ
    "41": (
        "Приёмник для идемпотентности — сервис Sufler_Ingest (контур исполнителя). "
        "Повтор одного event_id не должен дублировать индекс."
    ),
    "42": None,  # ДИТ
    "43": None,  # ДИТ
    "44": (
        "Курсор хранится на стороне суфлёра (INT-09/reconcile) и/или в журнале outbox модуля sync "
        "для GET /changes."
    ),
    "45": (
        "Согласны. Ориентир «1–2 мин» в черновике уберём. "
        "По ТТ §4.5.1.3 — обновление базы знаний LLM из СУЗ в режиме реального времени; "
        "§4.1.5 — обновление данных в режиме онлайн. "
        "Числовой порог для цепочки «СУЗ → индекс» в ТТ не задан. "
        f"«< 2 мин» в §4.6 {MOD} — только верхняя граница приёмочного теста доставки webhook, "
        "не целевой режим. Целевой режим интеграции: webhook сразу при сохранении (outbox)."
    ),
    "46": (
        "Vector Store — векторы чанков и метаданные (article_id, version_id, section_id, status, checksum). "
        f"Детали — в разделе «Суфлёр» {TZ}."
    ),
    "47": None,  # ДИТ
    "48": None,  # ДИТ
    "49": (
        "Согласны. П. 4.5.1.3–4.5.1.6 Прил. 1 — зона Исполнителя (модуль «Суфлёр», база знаний LLM), "
        "не разработчика Bitrix. "
        "Строка «Инфраструктура заказчика» на диаграмме — канал доставки (endpoint webhook, сеть, TLS, allowlist); "
        "её обеспечивает Заказчик/ДИТ. Исполнитель размещает ПО суфлёра на предоставленной инфраструктуре "
        "и реализует функции по ТТ (§4.1.5 — база знаний LLM на основе СУЗ с обновлением онлайн). "
        "4.5.1.3 — обновление базы знаний LLM из СУЗ в режиме реального времени: Исполнитель — "
        "приём webhook (INT-01…08), индексация из payload, reconcile (INT-09/10); Bitrix — только "
        "события и передача актуального контента (п. 7.1 ТТ). "
        "4.5.1.4 — оповещения об изменениях базы знаний LLM для проверки администраторами базы знаний "
        "и сценариев/промптов: реализует Исполнитель в контуре суфлёра (раздел «Суфлёр» v1.2). "
        "4.5.1.5 — логирование процесса обновления базы знаний LLM: Исполнитель "
        "(журнал индексации, статусы обработки событий). "
        "4.5.1.6 — «разметка СУЗ для работы с LLM» разработчиком по согласованию с Заказчиком: "
        "не создание метаданных в CMS (инфоблок, свойства, HTML уже есть), "
        "а методика подготовки контента для базы знаний LLM (нормализация HTML, чанкинг, эмбеддинги) — "
        "Исполнитель; регламент согласуем с Заказчиком. "
        f"§4 настоящего раздела описывает только минимум для Bitrix (outbox, payload, BTX-1…10). "
        f"В {TZ} добавим таблицу «п. ТТ → зона Исполнителя / зона Bitrix / зона Заказчика»."
    ),
    "50": None,  # ДИТ
    "59": (
        "Принято. Используем определение из Прил. 1 §1: "
        "«1С-Битрикс: Система управления сайтом» (не «CMS»)."
    ),
    "60": (
        "Хранение — элементы инфоблока СУЗ. Таблицы, спойлеры, тултипы — в составе HTML-тела статьи. "
        "Детальная структура полей — регламент BTX-5 (согласование с владельцем СУЗ)."
    ),
    "61": (
        f"Согласны. {MOD} в {TZ} — детализация п. 7.1: контракт обмена, события, payload, "
        "приёмка интеграционного контура."
    ),
    "62": (
        f"Принято. Бизнес-правила КЦ — ссылки на пункты ТТ + таблица «правило ТТ → поле payload/event_type», "
        "без полного дублирования текста ТТ."
    ),
    "63": (
        "Согласны. Корректно: источником знаний для подсказок суфлёра является СУЗ; "
        "оператор может использовать иные системы вне суфлёра."
    ),
    "64": (
        f"Принято. Добавим ссылку на пункт ТТ: в payload — permalink; "
        f"АРМ суфлёра отображает ссылку оператору (раздел «Суфлёр» {TZ})."
    ),
    "65": (
        f"Согласны. Это общее требование ТТ к модулю «Суфлёр»; "
        f"в {MOD} — перекрёстная ссылка на общий раздел {TZ}."
    ),
    "66": f"Принято. Заменим на «регулярно, в течение рабочего дня» / формулировку ТТ.",
    "67": (
        "Согласны. Возможны точечные правки, смена/перенос разделов, новые разделы, переименования — "
        "покрывается event_type и changed_fields."
    ),
    "68": (
        f"Описание моделей A и B и обоснование выбора — в §3.7–3.8 {TZ}. "
        "В актуальной модели B webhook содержит полный текст; отдельный GET после события не используется. "
        f"Диаграмма §2 — один POST Bitrix → Sufler_Ingest. GET — только INT-10/INT-06."
    ),
    "69": None,  # ДИТ
    "70": (
        "Триггер — бизнес-событие публикации для области индексации КЦ (см. BTX-4): "
        "обработчик OnAfterIBlockElement* после правил status=published."
    ),
    "71": None,  # ДИТ
    "72": (
        "Outbox: webhook отправляется сразу при сохранении; при сбое — retry агентом (≤1 мин). "
        "По ТТ §4.5.1.3 обновление базы знаний из СУЗ — в режиме реального времени; "
        "допустимой задержки в минутах ТТ не задаёт."
    ),
    "73": (
        f"Описание моделей A и B и обоснование выбора B — §3.7–3.8 {TZ}. "
        "Модель B (выбранная): отдельный GET после webhook не нужен — полный текст статьи "
        "передаётся в одном POST (body_html, body_plain и метаданные §6.2); суфлёр индексирует из payload. "
        "Модель A (для сравнения): Bitrix отправляет короткий webhook (article_id, event_id, метаданные); "
        "полный текст суфлёр запрашивает сам — сценарий INT-06, GET iblock.element.get к REST API Bitrix. "
        "REST GET iblock.element.get — штатный метод платформы 1С-Битрикс [Штатно] "
        "(документация dev.1c-bitrix.ru); Исполнитель его не создаёт и не разрабатывает. "
        "В проекте GET используется только для INT-10 (первичная загрузка) и опционально INT-06 "
        "(fallback, отладка, миграция; в модели A — после каждого события). "
        "Формулировка черновика «GET после webhook» относилась к модели A и не применяется "
        "к штатной цепочке INT-01…05, 08."
    ),
    "74": (
        "Статья попадает в индекс после приёма webhook и индексации (модель B — из payload). "
        "По ТТ §4.5.1.3 — режим реального времени; сквозных секунд для «СУЗ → индекс» нет. "
        "Выдача подсказки оператору в диалоге после обновления индекса — §4.3.1.4 (≤1–2 с, телефония), "
        "§4.3.2.3 (≤2 с, онлайн-чат), §3.4 (ответ LLM 1–2 с)."
    ),
    "75": f"Принято. «Источник истины» — один раз в общем глоссарии {TZ}.",
    "76": (
        "Дополним: источник RAG — опубликованные статьи инфоблока в области индексации для КЦ; "
        "метаданные (раздел, статус, версия); HTML-разметка (таблицы, спойлеры, тултипы) — в body_html."
    ),
    "77": None,  # ДИТ
    "78": None,  # ДИТ
    "79": None,  # ДИТ
    "80": None,  # ДИТ
    "81": (
        f"Принято. В русскоязычном тексте — «1С-Битрикс»; Bitrix — только в коде/API "
        "(bank.sufler.sync, REST)."
    ),
    "82": (
        "Да, «Разово ок» — неудачное сокращение в таблице. Имелось в виду: разовая первичная "
        "загрузка (INT-10) допустима через штатный REST iblock.element.list; для оперативной "
        "синхронизации REST не заменяет webhook (модель B). В v1.2 переформулируем: "
        "«Разовая полная выгрузка (INT-10) — через REST [Штатно]; оперативные изменения — "
        "webhook (INT-01…08)»."
    ),
    "83": (
        "Фильтр «только КЦ» — не отдельный переключатель в админке СУЗ. "
        "По терминологии Прил. 1 §1: «1С-Битрикс: Система управления сайтом» / СУЗ (не «CMS»). "
        "Отдельного штатного признака «доступно операторам КЦ» в инфоблоках нет — "
        "подтверждено Солдатенко Е.П. (id=179): «Признака доступности операторам нет, "
        "все настраивается правами». "
        "Штатно в 1С-Битрикс (dev.1c-bitrix.ru): инфоблоки и иерархия разделов "
        "(iblock.section.list/.get, ACTIVE/GLOBAL_ACTIVE); элементы с флагом ACTIVE (Y/N) "
        "и привязкой к разделам; пользовательские свойства (REST iblock.element.list/.get); "
        "расширенные права доступа к инфоблоку, разделу и элементу (группы пользователей, "
        "наследование по иерархии). Готового флага «только для КЦ» из коробки нет. "
        "[Доработка] — модуль bank.sufler.sync (BTX-4): в обработчиках OnAfterIBlockElement* "
        "по правилам банка вычисляет visibility_scope и status=published; для статей вне "
        "области индексации для КЦ не инициирует publish-события (или отправляет unpublished). "
        "Строка 13 матрицы §4.2. "
        "Где настраивается: (1) админка СУЗ — структура инфоблока (разделы), права групп; "
        "(2) экран настроек модуля (BTX-1): IBLOCK_ID, whitelist section_id для области "
        "индексации для КЦ; (3) код модуля — правила BTX-4, регламент BTX-5. "
        "На стороне суфлёра: фильтр при индексации и retrieval — только status=published "
        "и visibility_scope с аудиторией КЦ (напр. kc_operator)."
    ),
    "84": (
        f"Единообразие: в тексте — «1С-Битрикс»; в идентификаторах — Bitrix. "
        f"Зафиксируем в стиле {TZ}."
    ),
    "85": None,  # ДИТ
    "86": (
        "Отдельного поля «status» в 1С-Битрикс: Система управления сайтом (СУЗ) нет. "
        "Нормализованный status (draft/published/archived) формирует модуль sync по правилам BTX-4 "
        "(маппинг из сырого ACTIVE и других полей инфоблока). "
        "По уточнению Солдатенко Е.П.: «Черновик используется КЦ, я точно не помню, "
        "но скорее всего речь идет о активности статьи, ставится галка.»"
    ),
    "87": None,  # ДИТ
    "88": (
        "Согласны: п. 4.5.1.3–4.5.1.6 Прил. 1 — обязанности Исполнителя, не разработчика Bitrix. "
        "4.5.1.3 — обновление базы знаний LLM из СУЗ в режиме реального времени: Исполнитель — "
        "приём webhook (INT-01…08), индексация из payload, reconcile (INT-09/10); Bitrix — только "
        "события и передача актуального контента (п. 7.1 ТТ, §4.1.5). "
        "4.5.1.4 — оповещения об изменениях базы знаний LLM для проверки администраторами базы знаний "
        "и сценариев/промптов: реализует Исполнитель в контуре суфлёра (раздел «Суфлёр» v1.2). "
        "4.5.1.5 — логирование процесса обновления базы знаний LLM: Исполнитель "
        "(журнал индексации, статусы обработки событий). "
        "4.5.1.6 — «разметка СУЗ для работы с LLM» разработчиком по согласованию с Заказчиком: "
        "не создание метаданных в CMS, а методика подготовки контента для базы знаний LLM "
        "(нормализация HTML, чанкинг, эмбеддинги) — Исполнитель; регламент согласуем с Заказчиком. "
        f"§4 настоящего раздела описывает только минимум для Bitrix (outbox, payload, BTX-1…10). "
        "Зона Заказчика — инфраструктура (endpoint, сеть, TLS). "
        f"В {TZ} добавим таблицу «п. ТТ → зона Исполнителя / зона Bitrix / зона Заказчика»."
    ),
    "89": f"Согласны. Правила для суфлёра — ссылки на ТТ + маппинг в payload, без дублирования.",
    "153": (
        "Согласны. «Разметка СУЗ для работы с LLM» (п. 4.5.1.6 ТТ) — не создание метаданных в СУЗ: "
        "они уже есть (инфоблок, разделы, свойства, HTML-тело статьи). "
        "По ТТ это методика подготовки контента СУЗ для базы знаний LLM, которую разрабатывает "
        "Исполнитель по согласованию с Заказчиком: нормализация HTML, разбиение на фрагменты (чанки), "
        "эмбеддинги, правила использования существующих свойств в метаданных индекса. "
        "Строку про «регламент для суфлёра» (ID инфоблока, коды свойств) в v1.2 переформулируем: "
        "это техническая спецификация интеграции (BTX-5), не п. 4.5.1.6; готовит владелец СУЗ/Bitrix. "
        "Маппинг свойств в payload (BTX-4) — перенос уже существующих метаданных, не разметка для LLM."
    ),
    "154": (
        "Да, попадают в RAG. Таблицы, спойлеры, тултипы — элементы HTML внутри текста статьи СУЗ. "
        "Модуль sync не выделяет их в отдельные поля payload: при формировании сообщения для суфлёра "
        "весь текст статьи, включая эту разметку, передаётся в поле body_html (из DETAIL_TEXT). "
        "Отдельной записи «таблица» или «спойлер» в payload нет — суфлёр извлекает содержимое из HTML "
        "при индексации. "
        f"Термин «сериализация» (преобразование данных статьи в JSON payload для webhook) "
        f"в ТТ не определён — опишем дополнительно в глоссарии {TZ}; в тексте — «см. глоссарий»."
    ),
    "155": (
        f"Принято. Файлы-вложения в RAG v1 не индексируются (п. ТТ). "
        "Строку матрицы №4 оформим как «не входит в v1.2»."
    ),
    "156": (
        "По п. 4.5.1.6 ТТ «разметка СУЗ» — не правка метаданных в CMS (они уже заданы в СУЗ), "
        "а подготовка контента для базы знаний LLM: из payload (body_html/body_plain и свойства) "
        "Исполнитель нормализует HTML, делит на чанки, формирует эмбеддинги и метаданные индекса "
        "(article_id, раздел, статус, область видимости). "
        f"Методику согласуем с Заказчиком и опишем в разделе «Суфлёр» {TZ}."
    ),
    "157": (
        "Push — фоновый обмен: событие CMS → outbox → HTTP POST на endpoint суфлёра → 202 → индексация. "
        "Отдельного уведомления оператору нет."
    ),
    "158": (
        "draft — RAG не обновляет; published — индексация; archived/unpublished — soft delete; "
        "deleted — hard delete."
    ),
    "159": (
        "В СУЗ нет отдельного поля или галочки «только для КЦ». "
        "Учтено (Солдатенко Е.П., id=179): доступность операторам задаётся правами групп "
        "и размещением статьи в разделах инфоблока. "
        "Штатные инструменты 1С-Битрикс: дерево разделов, флаг ACTIVE элемента, "
        "расширенное управление правами (инфоблок → раздел → элемент), "
        "пользовательские свойства — при необходимости в маппинге BTX-5. "
        "Отдельного свойства «доступно КЦ» не предусмотрено. "
        "Поле «область видимости» (visibility_scope в payload) и принадлежность к "
        "области индексации для КЦ вычисляет модуль bank.sufler.sync по правилам банка: "
        "whitelist разделов из настроек модуля (BTX-1) + исходные данные СУЗ (раздел, ACTIVE, права). "
        "Это не пункт меню редактора — состав области индексации для КЦ задаётся в настройках "
        "модуля и регламенте BTX-5 (BTX-4)."
    ),
    "160": (
        f"В ТТ (§8–9) — «требования информационной безопасности» (аббревиатура ИБ); "
        "термина «ЦК» в ТТ нет. "
        f"В {TZ} — отсылка к §8–9 ТТ и матрице мер (TLS, HMAC-SHA256/mTLS, allowlist IP). "
        "Конкретные требования к каналу обмена и заключение по ИБ "
        "согласует и предоставляет Заказчик."
    ),
    "161": None,  # ДИТ
    "162": (
        f"Согласны. §4.6 {MOD} в {TZ} — только приёмка интеграционного обмена СУЗ ↔ суфлёр: "
        "доставка webhook/outbox (HTTP 202, статусы pending/sent/failed в журнале модуля), "
        "валидность payload по схеме BTX-10, идемпотентность по event_id (INT). "
        "Строки «статья в production-индексе», «soft delete» — проверка результата обмена "
        "(суфлёр принял и обработал событие), без оценки UI и качества подсказок оператору. "
        f"Полный пул требований ТТ (§4.3 — окно оператора и SLA подсказки; §4.5 — обновление "
        f"базы знаний; §4.5.1.3–4.5.1.6) — отдельная приёмка Контакт-центра по разделу "
        f"«Суфлёр» {TZ}. В §4.6 переработаем таблицу: оставим только проверки обмена; "
        "добавим перекрёстные ссылки на пункты ТТ для полной приёмки КЦ."
    ),
    "163": (
        "Триггер публикации — см. BTX-4: status=published после обработчика события инфоблока."
    ),
    "164": (
        f"Расширим матрицу приёмки: таблицы/спойлеры в body_html, перенос разделов, "
        "крупный новый раздел (напр. СДБО)."
    ),
    "165": (
        "Нет. «< 2 мин» — только верхняя граница приёмочного теста §4.6, не целевой режим. "
        "По ТТ §4.5.1.3 — обновление базы знаний в режиме реального времени. "
        "Целевой режим интеграции: webhook формируется и отправляется сразу при сохранении (outbox), "
        "без ожидания 2 мин."
    ),
    "166": (
        "ТТ не задаёт сквозное время «публикация в СУЗ → новая подсказка оператору» в секундах. "
        "Обновление базы знаний из СУЗ — §4.5.1.3 (режим реального времени), §4.1.5 (режим онлайн). "
        "Выдача подсказки оператору в диалоге (уже после обновления индекса): "
        "§4.3.1.4 — не более 1–2 с на реплику (телефония); "
        "§4.3.2.3 — не более 2 с (онлайн-чат); §3.4 — ответ LLM 1–2 с. "
        f"§4.6 «< 2 мин» — верхняя граница теста доставки webhook, не SLA подсказки. "
        f"В {TZ} разделим: §4.6 — обмен; SLA §4.3.1.4/4.3.2.3 — раздел «Суфлёр»."
    ),
    "167": (
        "Поддерживается любой version_number; в RAG одновременно только is_current=true. "
        "v2 в приёмке — пример."
    ),
    "168": (
        "Деактивация — article.unpublished → soft delete (исключение из retrieval), "
        "не hard delete."
    ),
    "169": (
        "Сбой — недоступность endpoint суфлёра (503/timeout) во внутренней сети банка; "
        "сценарий INT-08: outbox → retry."
    ),
    "170": (
        "Нагрузочный приёмочный тест: серия правок в СУЗ; проверка, что outbox не теряет event_id. "
        "Не прогноз производственной нагрузки."
    ),
    "171": None,  # ДИТ
    "172": (
        "Отдельного «окна успеха» для редактора нет. Основной контроль — не штатный «Журнал событий» Bitrix, "
        "а админ-страница модуля bank.sufler.sync (BTX-8, доработка): журнал outbox со статусами "
        "pending/sent/failed, текстом ошибки, event_id и кнопкой replay. "
        "На приёмке §4.6: после действия в СУЗ — HTTP 202, в журнале sent, payload валиден (BTX-10). "
        "«Настройки → Журнал событий» Bitrix может дополнительно показывать срабатывание "
        "OnAfterIBlockElement*, но для приёмки интеграции опираемся на журнал модуля. "
        f"Оператор КЦ видит результат косвенно — актуальную подсказку в АРМ суфлёра; "
        f"UI оператора — отдельная приёмка (раздел «Суфлёр» {TZ})."
    ),
    "173": (
        f"Согласны. INT — приёмка обмена; UI оператора (окно, кнопки, ошибки) — "
        f"раздел «Суфлёр» {TZ} с отдельной приёмкой КЦ."
    ),
    "174": (
        f"В ТТ (§8–9) — «требования информационной безопасности» (ИБ); термина «ЦК» в ТТ нет. "
        f"В {TZ} — отсылка к §8–9 ТТ (в т.ч. подпись HMAC, TLS). "
        "Заключение/согласование по требованиям ИБ — от Заказчика."
    ),
    "177": (
        "С учётом ответа Солдатенко Е.П.: отдельная сервисная учётка для чтения инфоблоков "
        "не обязательна — авторизованный пользователь КЦ в СУЗ нужен для статистики, "
        "для интеграции сбор статистики не требуется. "
        "В модели B актуальный контент передаётся в webhook (полный текст в POST), "
        "отдельного оперативного REST-чтения не требуется. "
        "REST read (при необходимости — сервисный пользователь с правами только чтения) — "
        "только для первичной загрузки INT-10 и опционального fallback; "
        f"требование уточним в BTX-5 и {TZ}."
    ),
    "178": (
        "Принято, тогда ориентируемся на флаг активности статьи в СУЗ (галка). "
        "В payload модуль sync формирует нормализованный status "
        "(draft/published/archived) по правилам BTX-4. "
        f"Маппинг полей опишем в {TZ}."
    ),
    "179": (
        "Принято, тогда отдельного признака «доступно операторам КЦ» в инфоблоке нет — "
        "доступ настраивается правами и разделами. "
        "Поле «область видимости» (`visibility_scope` в payload) вычисляет модуль sync "
        f"по правилам BTX-4; опишем в {TZ}."
    ),
    "180": (
        "Принято, тогда при обновлении содержимого статьи permalink не меняется. "
        "URL может измениться только при изменении настроек статьи — "
        "такие изменения на практике редки. "
        f"Зафиксируем в payload и {TZ}."
    ),
    "181": (
        "Принято, тогда для отладки интеграции используем копию СУЗ "
        "(актуальность статей ~полгода назад) — для тестирования обмена и RAG этого достаточно, "
        "свежесть контента не критична. "
        "Дополнительно: отдельный URL webhook на тестовый контур суфлёра (BTX-20). "
        f"Зафиксируем в {TZ}."
    ),
}


def new_para_id() -> str:
    return f"{random.randint(0, 0xFFFFFF):06X}"


def new_rsid() -> str:
    return f"{random.randint(0, 0xFFFFFF):06X}"


def escape_xml(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def split_comment_paragraphs(text: str) -> list[str]:
    text = text.strip()
    if len(text) <= 900:
        return [text]
    chunks: list[str] = []
    while text:
        if len(text) <= 900:
            chunks.append(text)
            break
        cut = text.rfind(" ", 0, 900)
        if cut < 400:
            cut = 900
        chunks.append(text[:cut].strip())
        text = text[cut:].strip()
    return chunks


def build_reply_comment_xml(comment_id: int, paragraphs: list[str]) -> tuple[str, str]:
    rsid = new_rsid()
    para_ids = [new_para_id() for _ in paragraphs]
    parts = [
        f'<w:comment w:id="{comment_id}" w:author="{AUTHOR}" '
        f'w:date="{REPLY_DATE}" w:initials="{INITIALS}">'
    ]
    for idx, (para_id, para_text) in enumerate(zip(para_ids, paragraphs)):
        parts.append(
            f'<w:p w14:paraId="{para_id}" w14:textId="77777777" '
            f'w:rsidR="{rsid}" w:rsidRDefault="{rsid}" w:rsidP="{rsid}">'
            f'<w:pPr><w:pStyle w:val="affff2"/>'
            f'<w:rPr><w:lang w:val="ru-RU"/></w:rPr></w:pPr>'
        )
        if idx == 0:
            parts.append(
                f'<w:r><w:rPr><w:rStyle w:val="affff1"/></w:rPr><w:annotationRef/></w:r>'
            )
        parts.append(
            f'<w:r><w:rPr><w:lang w:val="ru-RU"/></w:rPr>'
            f'<w:t xml:space="preserve">{escape_xml(para_text)}</w:t></w:r>'
            f"</w:p>"
        )
    parts.append("</w:comment>")
    return "".join(parts), para_ids[0]


def parse_comment_parents(comments_xml: str) -> dict[str, str]:
    root = ET.fromstring(comments_xml)
    mapping: dict[str, str] = {}
    for comment in root.findall(W + "comment"):
        cid = comment.get(W + "id")
        if cid is None:
            continue
        first_p = comment.find(W + "p")
        if first_p is not None:
            para_id = first_p.get(W14 + "paraId")
            if para_id:
                mapping[cid] = para_id
    return mapping


def max_comment_id(comments_xml: str) -> int:
    root = ET.fromstring(comments_xml)
    ids = [int(c.get(W + "id", "0")) for c in root.findall(W + "comment")]
    return max(ids) if ids else 0


def comment_text(comments_xml: str, comment_id: str) -> str:
    root = ET.fromstring(comments_xml)
    for comment in root.findall(W + "comment"):
        if comment.get(W + "id") != comment_id:
            continue
        parts: list[str] = []
        for node in comment.iter(W + "t"):
            if node.text:
                parts.append(node.text)
        return "".join(parts)
    return ""


def comment_authors(comments_xml: str) -> dict[str, str]:
    root = ET.fromstring(comments_xml)
    return {
        c.get(W + "id", ""): c.get(W + "author", "")
        for c in root.findall(W + "comment")
    }


def executor_reply_para_ids(comments_xml: str, comments_ext_xml: str) -> set[str]:
    """paraIds of threaded reply comments authored by AUTHOR."""
    parents = parse_comment_parents(comments_xml)
    para_to_cid = {para: cid for cid, para in parents.items()}
    authors = comment_authors(comments_xml)
    reply_para_ids: set[str] = set()
    ext_root = ET.fromstring(comments_ext_xml)
    for ex in ext_root.findall(W15 + "commentEx"):
        parent_para = ex.get(W15 + "paraIdParent")
        reply_para = ex.get(W15 + "paraId")
        if not parent_para or not reply_para:
            continue
        reply_cid = para_to_cid.get(reply_para)
        if reply_cid and authors.get(reply_cid) == AUTHOR:
            reply_para_ids.add(reply_para)
    return reply_para_ids


def ensure_top_level_comment_ex(
    comments_xml: str, comments_ext_xml: str
) -> tuple[str, int]:
    """Add missing top-level commentEx rows for customer comments only."""
    authors = comment_authors(comments_xml)
    parents = parse_comment_parents(comments_xml)
    ext_root = ET.fromstring(comments_ext_xml)
    existing_top = {
        ex.get(W15 + "paraId")
        for ex in ext_root.findall(W15 + "commentEx")
        if ex.get(W15 + "paraId") and not ex.get(W15 + "paraIdParent")
    }
    new_entries: list[str] = []
    for cid, para_id in parents.items():
        if authors.get(cid) == AUTHOR:
            continue
        if para_id in existing_top:
            continue
        new_entries.append(f'<w15:commentEx w15:paraId="{para_id}" w15:done="0"/>')
    if not new_entries:
        return comments_ext_xml, 0
    ext_insert = comments_ext_xml.rfind("</w15:commentsEx>")
    if ext_insert == -1:
        raise RuntimeError("Invalid commentsExtended.xml")
    updated = (
        comments_ext_xml[:ext_insert] + "".join(new_entries) + comments_ext_xml[ext_insert:]
    )
    return updated, len(new_entries)


def ensure_executor_replies_editable(
    comments_xml: str, comments_ext_xml: str
) -> tuple[str, int]:
    """Force w15:done=\"0\" on all executor reply commentEx entries."""
    reply_para_ids = executor_reply_para_ids(comments_xml, comments_ext_xml)
    if not reply_para_ids:
        return comments_ext_xml, 0
    unlocked = 0
    for para_id in reply_para_ids:
        pattern = (
            rf'(<w15:commentEx\b(?=[^>]*\bw15:paraId="{re.escape(para_id)}")'
            rf'(?=[^>]*\bw15:paraIdParent=")[^>]*\bw15:done=")[01]("[^>]*>)'
        )
        updated, count = re.subn(pattern, r"\g<1>0\2", comments_ext_xml, count=1)
        if count:
            comments_ext_xml = updated
            unlocked += count
            continue
        insert_pattern = (
            rf'(<w15:commentEx\b(?=[^>]*\bw15:paraId="{re.escape(para_id)}")'
            rf'(?=[^>]*\bw15:paraIdParent=")(?![^>]*\bw15:done=")[^>]*)(/>|>)'
        )
        updated, count = re.subn(insert_pattern, r'\1 w15:done="0"\2', comments_ext_xml, count=1)
        if count:
            comments_ext_xml = updated
            unlocked += count
    return comments_ext_xml, unlocked


def remove_document_protection(settings_xml: str) -> str:
    settings_xml = re.sub(r"<w:documentProtection\b[^>]*/>", "", settings_xml)
    settings_xml = re.sub(r"<w:writeProtection\b[^>]*/>", "", settings_xml)
    return settings_xml


def verify_executor_replies(comments_xml: str, comments_ext_xml: str) -> dict[str, int]:
    authors = comment_authors(comments_xml)
    ponomarev_comments = sum(1 for author in authors.values() if author == AUTHOR)
    reply_para_ids = executor_reply_para_ids(comments_xml, comments_ext_xml)
    ext_root = ET.fromstring(comments_ext_xml)
    done_zero = 0
    done_one = 0
    for ex in ext_root.findall(W15 + "commentEx"):
        reply_para = ex.get(W15 + "paraId")
        if reply_para not in reply_para_ids:
            continue
        done = ex.get(W15 + "done")
        if done == "0":
            done_zero += 1
        elif done == "1":
            done_one += 1
    return {
        "ponomarev_comments": ponomarev_comments,
        "ponomarev_replies": len(reply_para_ids),
        "reply_done_zero": done_zero,
        "reply_done_one": done_one,
    }


def executor_reply_map(comments_xml: str, comments_ext_xml: str) -> dict[str, str]:
    """Map parent comment id -> executor reply comment id."""
    parents = parse_comment_parents(comments_xml)
    ext_root = ET.fromstring(comments_ext_xml)
    para_to_cid: dict[str, str] = {para: cid for cid, para in parents.items()}
    root = ET.fromstring(comments_xml)
    comment_authors = {
        c.get(W + "id", ""): c.get(W + "author", "") for c in root.findall(W + "comment")
    }
    mapping: dict[str, str] = {}
    for ex in ext_root.findall(W15 + "commentEx"):
        parent_para = ex.get(W15 + "paraIdParent")
        reply_para = ex.get(W15 + "paraId")
        if not parent_para or not reply_para:
            continue
        parent_cid = para_to_cid.get(parent_para)
        reply_cid = para_to_cid.get(reply_para)
        if (
            parent_cid
            and reply_cid
            and comment_authors.get(reply_cid) == AUTHOR
        ):
            mapping[parent_cid] = reply_cid
    return mapping


def existing_executor_parents(comments_xml: str, comments_ext_xml: str) -> set[str]:
    """Parent comment ids that already have a non-empty threaded reply from AUTHOR."""
    replies = executor_reply_map(comments_xml, comments_ext_xml)
    return {
        parent_cid
        for parent_cid, reply_cid in replies.items()
        if comment_text(comments_xml, reply_cid).strip()
    }


def replace_reply_comment_xml(
    comments_xml: str, reply_cid: str, paragraphs: list[str]
) -> str:
    root = ET.fromstring(comments_xml)
    rsid = new_rsid()
    for comment in root.findall(W + "comment"):
        if comment.get(W + "id") != reply_cid:
            continue
        first_p = comment.find(W + "p")
        preserved_para_id = (
            first_p.get(W14 + "paraId") if first_p is not None else new_para_id()
        )
        for child in list(comment):
            if child.tag == W + "p":
                comment.remove(child)
        for idx, para_text in enumerate(paragraphs):
            para_id = preserved_para_id if idx == 0 else new_para_id()
            p = ET.SubElement(comment, W + "p")
            p.set(W14 + "paraId", para_id)
            p.set(W14 + "textId", "77777777")
            p.set(W + "rsidR", rsid)
            p.set(W + "rsidRDefault", rsid)
            p.set(W + "rsidP", rsid)
            p_pr = ET.SubElement(p, W + "pPr")
            p_style = ET.SubElement(p_pr, W + "pStyle")
            p_style.set(W + "val", "affff2")
            r_pr = ET.SubElement(p_pr, W + "rPr")
            lang = ET.SubElement(r_pr, W + "lang")
            lang.set(W + "val", "ru-RU")
            if idx == 0:
                r_ref = ET.SubElement(p, W + "r")
                r_ref_pr = ET.SubElement(r_ref, W + "rPr")
                r_style = ET.SubElement(r_ref_pr, W + "rStyle")
                r_style.set(W + "val", "affff1")
                ET.SubElement(r_ref, W + "annotationRef")
            r = ET.SubElement(p, W + "r")
            r_pr = ET.SubElement(r, W + "rPr")
            lang = ET.SubElement(r_pr, W + "lang")
            lang.set(W + "val", "ru-RU")
            t = ET.SubElement(r, W + "t")
            t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
            t.text = para_text
        comment.set(W + "date", REPLY_DATE)
        break
    ET.register_namespace("w", "http://schemas.openxmlformats.org/wordprocessingml/2006/main")
    ET.register_namespace("w14", "http://schemas.microsoft.com/office/word/2010/wordml")
    ET.register_namespace("w15", "http://schemas.microsoft.com/office/word/2012/wordml")
    return ET.tostring(root, encoding="unicode")


def update_existing_replies(comments_xml: str, comments_ext_xml: str) -> tuple[str, int]:
    replies = executor_reply_map(comments_xml, comments_ext_xml)
    updated = 0
    for parent_cid, reply_cid in replies.items():
        if parent_cid not in REFRESH_PARENT_IDS:
            continue
        response = RESPONSES.get(parent_cid)
        if not response:
            continue
        comments_xml = replace_reply_comment_xml(
            comments_xml, reply_cid, split_comment_paragraphs(response)
        )
        updated += 1
    return comments_xml, updated


def add_replies(comments_xml: str, comments_ext_xml: str) -> tuple[str, str, int]:
    parents = parse_comment_parents(comments_xml)
    already = existing_executor_parents(comments_xml, comments_ext_xml)
    next_id = max_comment_id(comments_xml) + 1
    added = 0

    insert_pos = comments_xml.rfind("</w:comments>")
    if insert_pos == -1:
        raise RuntimeError("Invalid comments.xml")

    new_comments: list[str] = []
    new_ext_entries: list[str] = []

    for cid in sorted(parents.keys(), key=lambda x: int(x)):
        if cid in already:
            continue
        response = RESPONSES.get(cid)
        if not response:
            continue
        xml_block, reply_para_id = build_reply_comment_xml(
            next_id, split_comment_paragraphs(response)
        )
        new_comments.append(xml_block)
        new_ext_entries.append(
            f'<w15:commentEx w15:paraId="{reply_para_id}" '
            f'w15:paraIdParent="{parents[cid]}" w15:done="0"/>'
        )
        next_id += 1
        added += 1

    updated_comments = comments_xml[:insert_pos] + "".join(new_comments) + comments_xml[insert_pos:]

    ext_insert = comments_ext_xml.rfind("</w15:commentsEx>")
    if ext_insert == -1:
        raise RuntimeError("Invalid commentsExtended.xml")
    updated_ext = (
        comments_ext_xml[:ext_insert] + "".join(new_ext_entries) + comments_ext_xml[ext_insert:]
    )

    return updated_comments, updated_ext, added


def ensure_executor_in_people(people_xml: str) -> str:
    if AUTHOR in people_xml:
        return people_xml
    insert_at = people_xml.rfind("</w15:people>")
    person = (
        f'<w15:person w15:author="{AUTHOR}">'
        f'<w15:presenceInfo w15:providerId="None" w15:userId="{AUTHOR}"/>'
        f"</w15:person>"
    )
    return people_xml[:insert_at] + person + people_xml[insert_at:]


def main() -> None:
    if not SRC.exists():
        raise SystemExit(f"Source not found: {SRC}")

    # Always rebuild from MIX so stale OUT state (e.g. w15:done="1") is not preserved.
    source = SRC
    if WORK.exists():
        shutil.rmtree(WORK)
    WORK.mkdir()

    with zipfile.ZipFile(source, "r") as zin:
        zin.extractall(WORK)

    comments_path = WORK / "word" / "comments.xml"
    ext_path = WORK / "word" / "commentsExtended.xml"
    people_path = WORK / "word" / "people.xml"
    settings_path = WORK / "word" / "settings.xml"

    comments_xml = comments_path.read_text(encoding="utf-8")
    ext_xml = ext_path.read_text(encoding="utf-8")

    updated_comments, updated_count = update_existing_replies(comments_xml, ext_xml)
    updated_comments, updated_ext, added = add_replies(updated_comments, ext_xml)
    updated_ext, top_level_added = ensure_top_level_comment_ex(updated_comments, updated_ext)
    updated_ext, unlocked = ensure_executor_replies_editable(updated_comments, updated_ext)

    comments_path.write_text(updated_comments, encoding="utf-8")
    ext_path.write_text(updated_ext, encoding="utf-8")
    people_path.write_text(
        ensure_executor_in_people(people_path.read_text(encoding="utf-8")),
        encoding="utf-8",
    )
    settings_path.write_text(
        remove_document_protection(settings_path.read_text(encoding="utf-8")),
        encoding="utf-8",
    )

    if OUT.exists():
        OUT.unlink()

    with zipfile.ZipFile(OUT, "w", compression=zipfile.ZIP_DEFLATED) as zout:
        for file_path in WORK.rglob("*"):
            if file_path.is_file():
                zout.write(file_path, file_path.relative_to(WORK).as_posix())

    parents = parse_comment_parents(comments_xml)
    dit_skipped = sorted(
        cid for cid in parents if RESPONSES.get(cid) is None and cid in RESPONSES
    )
    unmapped = sorted(set(parents) - set(RESPONSES), key=int)

    stats = verify_executor_replies(updated_comments, updated_ext)
    protection_removed = "documentProtection" not in settings_path.read_text(encoding="utf-8")

    print(f"Source: {source}")
    print(f"Written: {OUT}")
    print(f"Top-level commentEx added: {top_level_added}")
    print(f"Replies updated: {updated_count}")
    print(f"Replies added: {added}")
    print(f"Reply done flags reset: {unlocked}")
    print(f"Ponomarev comments: {stats['ponomarev_comments']}")
    print(f"Ponomarev threaded replies: {stats['ponomarev_replies']}")
    print(f"Reply commentEx done=0: {stats['reply_done_zero']}")
    print(f"Reply commentEx done=1: {stats['reply_done_one']}")
    print(f"Document protection removed: {protection_removed}")
    print(f"DIT skipped (no reply): {len(dit_skipped)}")
    if unmapped:
        print(f"Unmapped comment ids: {', '.join(unmapped)}")


if __name__ == "__main__":
    main()
