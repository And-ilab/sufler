# -*- coding: utf-8 -*-
"""Insert missing SUF-T / CHAT-T step scenarios into TZ docx. Does NOT touch comments.xml."""
from __future__ import annotations

import copy
import re
import shutil
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
WORK = Path(r"C:\Users\user\Desktop\sufler\sufler\_extracted\tz_v14_edit")
SRC_DOCX = WORK / "source.docx"
UNZ = WORK / "unz"
OUT_DOCX = Path(r"C:\Users\user\Desktop") / "TZ-unified-v1.4 (Замечания) + SUF-T-CHAT-T сценарии.docx"

# Preserve namespaces on serialize
for prefix, uri in [
    ("w", "http://schemas.openxmlformats.org/wordprocessingml/2006/main"),
    ("r", "http://schemas.openxmlformats.org/officeDocument/2006/relationships"),
    ("wp", "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"),
    ("w14", "http://schemas.microsoft.com/office/word/2010/wordml"),
    ("w15", "http://schemas.microsoft.com/office/word/2012/wordml"),
    ("mc", "http://schemas.openxmlformats.org/markup-compatibility/2006"),
    ("o", "urn:schemas-microsoft-com:office:office"),
    ("v", "urn:schemas-microsoft-com:vml"),
    ("wpc", "http://schemas.microsoft.com/office/word/2010/wordprocessingCanvas"),
    ("w10", "urn:schemas-microsoft-com:office:word"),
    ("wps", "http://schemas.microsoft.com/office/word/2010/wordprocessingShape"),
    ("wpg", "http://schemas.microsoft.com/office/word/2010/wordprocessingGroup"),
    ("wpi", "http://schemas.microsoft.com/office/word/2010/wordprocessingInk"),
    ("a", "http://schemas.openxmlformats.org/drawingml/2006/main"),
    ("pic", "http://schemas.openxmlformats.org/drawingml/2006/picture"),
]:
    try:
        ET.register_namespace(prefix, uri)
    except Exception:
        pass


def text_of(el: ET.Element) -> str:
    return "".join(t.text or "" for t in el.iter(W + "t"))


def set_cell_text(tc: ET.Element, value: str) -> None:
    """Replace all text in a table cell with a single run string; keep first paragraph style."""
    paras = tc.findall(W + "p")
    if not paras:
        p = ET.SubElement(tc, W + "p")
        paras = [p]
    first = paras[0]
    # remove extra paragraphs
    for p in paras[1:]:
        tc.remove(p)
    # clear runs in first para, keep pPr
    for child in list(first):
        if child.tag != W + "pPr":
            first.remove(child)
    r = ET.SubElement(first, W + "r")
    # copy rPr from template if available later — minimal bold for field col handled separately
    t = ET.SubElement(r, W + "t")
    if value.startswith(" ") or value.endswith(" ") or "\n" in value:
        t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    t.text = value


def set_row(tr: ET.Element, field: str, value: str) -> None:
    cells = tr.findall(W + "tc")
    if len(cells) < 2:
        return
    set_cell_text(cells[0], field)
    set_cell_text(cells[1], value)
    # bold field column first run if possible
    r0 = cells[0].find(f".//{W}r")
    if r0 is not None and r0.find(W + "rPr") is None:
        rPr = ET.Element(W + "rPr")
        ET.SubElement(rPr, W + "b")
        r0.insert(0, rPr)


def make_heading(template_p: ET.Element, title: str) -> ET.Element:
    p = copy.deepcopy(template_p)
    # replace all text with title in one run
    for child in list(p):
        if child.tag != W + "pPr":
            p.remove(child)
    r = ET.SubElement(p, W + "r")
    # keep bold/heading feel
    rPr = ET.SubElement(r, W + "rPr")
    ET.SubElement(rPr, W + "b")
    t = ET.SubElement(r, W + "t")
    t.text = title
    return p


def make_scenario_table(template_tbl: ET.Element, fields: dict[str, str]) -> ET.Element:
    tbl = copy.deepcopy(template_tbl)
    rows = tbl.findall(W + "tr")
    # Expect: header + 6 data rows (Название…Связь) — pad/trim
    order = [
        ("Название", fields["Название"]),
        ("Предусловия", fields["Предусловия"]),
        ("Шаги", fields["Шаги"]),
        ("Ожидаемый результат", fields["Ожидаемый результат"]),
        ("Стенд", fields["Стенд"]),
        ("Связь", fields["Связь"]),
    ]
    # ensure at least 1+6 rows
    while len(rows) < 7:
        rows.append(copy.deepcopy(rows[-1]))
        tbl.append(rows[-1])
    # header
    set_row(rows[0], "Поле", "Значение")
    for i, (f, v) in enumerate(order, start=1):
        set_row(rows[i], f, v)
    # remove extras
    for extra in rows[7:]:
        tbl.remove(extra)
    return tbl


SCENARIOS_SUF: list[tuple[str, dict[str, str]]] = [
    (
        "SUF-T-06 — Диалоговое окно для внутренних пользователей",
        {
            "Название": "Внутренний пользователь КЦ: отдельное диалоговое окно (не Hub-суфлёр, не АРМ оператора)",
            "Предусловия": "Роль: Внутренний пользователь Контакт-центра (§2.4 п.6). Стенд: AI Hub staging. Подготовлен эталон QU / сценарий-кандидат к проверке.",
            "Шаги": "1. Войти под внутренним пользователем КЦ. 2. Открыть диалоговое окно для внутренних пользователей (не АРМ оператора и не вкладки Hub «Ассистент»/«Документы»). 3. Ввести текстовый запрос по эталону/теме СУЗ. 4. Зафиксировать ответ и % релевантности. 5. Убедиться, что нет клиентского канала и автоотправки клиенту.",
            "Ожидаемый результат": "Окно открыто отдельно; отображаются запрос и ответ LLM с % релевантности; суфлёр телефонии/АРМ не используется; база знаний пользователем не изменяется.",
            "Стенд": "Hub staging",
            "Связь": "UC-SUF-N02 · II.3.5.5 · 4.3.1, 4.6.1",
        },
    ),
    (
        "SUF-T-07 — Обратная связь сохраняется в отчётности",
        {
            "Название": "Отметка полезности подсказки попадает в модуль «Отчётность»",
            "Предусловия": "SUF-T-01 или SUF-T-03 выполнен; под карточкой подсказки доступны кнопки «Воспользовался / Не воспользовался / Неполный ответ».",
            "Шаги": "1. Нажать одну из кнопок обратной связи под подсказкой с опорой на статью СУЗ. 2. Открыть модуль «Отчётность» под аналитиком КЦ. 3. Найти событие/строку по диалогу и оператору за текущий период.",
            "Ожидаемый результат": "Отметка зафиксирована (FeedbackEvent); видна в отчёте полезности / журнале диалога; повторное нажатие не создаёт противоречивый «пустой» статус без записи.",
            "Стенд": "test Oktell / Hub staging + Отчётность",
            "Связь": "UC-SUF-T04 · FR-SUF-C04 · 4.3.1.9 / 4.3.2.5",
        },
    ),
    (
        "SUF-T-08 — p95 подсказки ≤ 2 с на стенде",
        {
            "Название": "Нагрузочный/стендовый замер времени появления подсказки",
            "Предусловия": "Стенд test Oktell + test Bitrix; профиль нагрузки согласован (до 75 операторов — II.7.4). Серия эталонных реплик по СУЗ.",
            "Шаги": "1. Выполнить серию звонков/реплик с фиксацией t_final (asr.final) и t_hint_display. 2. Рассчитать Δt для каждой реплики. 3. Построить p95 по выборке стенда.",
            "Ожидаемый результат": "p95(Δt) ≤ 2 с; типичный ответ 1–2 с после asr.final. Результат задокументирован в протоколе приёмки.",
            "Стенд": "test Oktell + test Bitrix (нагрузка II.7.4)",
            "Связь": "FR-SUF-06 · II.7.4 · 4.3.1.4",
        },
    ),
    (
        "SUF-T-09 — ≥ 50 сценариев в рабочем каталоге",
        {
            "Название": "При вводе в ПЭ в рабочем каталоге порядка 50 сценарных диалогов (настройка Подрядчика)",
            "Предусловия": "Роль проверки: аналитик/админ диалоговых сценариев (просмотр каталога). Стенд: Hub staging / pre-prod.",
            "Шаги": "1. Открыть рабочий каталог диалоговых сценариев суфлёра. 2. Подсчитать опубликованные/рабочие сценарии. 3. Выборочно открыть карту сценария (узлы/ветки).",
            "Ожидаемый результат": "В каталоге не менее порядка 50 сценарных диалогов, настроенных Подрядчиком при внедрении; у выбранных сценариев есть карта/описание веток.",
            "Стенд": "Hub staging / pre-prod",
            "Связь": "FR-SCR-01 · 4.5.2.1",
        },
    ),
    (
        "SUF-T-10 — Test-run сценариев реестра (4.5.2.7–8)",
        {
            "Название": "Прогон test-run для сценариев реестра перед публикацией",
            "Предусловия": "Доступ к редактору сценариев; выбран сценарий из реестра/каталога.",
            "Шаги": "1. Открыть сценарий. 2. Запустить test-run / проверку по п. 4.5.2.7–8. 3. Зафиксировать результат (успех/ошибки веток).",
            "Ожидаемый результат": "Test-run выполнен без критических ошибок; результат сохранён/отображён в UI; сценарий допускается к публикации только при успешном прогоне (по правилам редактора).",
            "Стенд": "Hub staging",
            "Связь": "FR-SCR-10 · 4.5.2.7–4.5.2.8",
        },
    ),
    (
        "SUF-T-11 — CC-SCR-001…010: ветки как в Прил.2",
        {
            "Название": "Эталонные сценарии Прил.2 воспроизводятся по веткам",
            "Предусловия": "В каталоге доступны CC-SCR-001…010 (или их проектные аналоги); стенд с cc_production.",
            "Шаги": "1. Выбрать сценарий CC-SCR-00N. 2. Пройти основные ветки по карте Прил.2 (позитив/уточнение/эскалация — по карточке). 3. Сверить фактическое поведение с описанием Прил.2.",
            "Ожидаемый результат": "Ветки соответствуют Прил.2; расхождения зафиксированы как дефект. Минимум выборочная проверка всех 10 ID либо полный прогон по плану приёмки.",
            "Стенд": "Hub staging + test Bitrix",
            "Связь": "FR-SCR-01 · Прил.2 · 4.5.2",
        },
    ),
    (
        "SUF-T-13 — Фокус в окне суфлёра / АРМ, не в Hub «Ассистент+Документы»",
        {
            "Название": "Активный звонок/диалог: рабочий фокус вне оболочки Hub А+Д",
            "Предусловия": "Роль: оператор телефонии или онлайн-чата. Активный звонок или диалог.",
            "Шаги": "1. Начать обслуживание клиента. 2. Проверить, где отображаются подсказки. 3. Открыть AI Hub и убедиться, что лента суфлёра не подменена вкладками «Ассистент»/«Документы» в том же окне.",
            "Ожидаемый результат": "Телефония — отдельное окно суфлёра; онлайн-чат — панель в АРМ. Hub slide-in не является основным местом подсказок суфлёра.",
            "Стенд": "test Oktell / Hub staging",
            "Связь": "FR-SUF-12 · 4.6.2.3 / 4.3.2",
        },
    ),
    (
        "SUF-T-14 — UI ленты: реплики и карточки подсказок с %",
        {
            "Название": "Лента «реплика → подсказка(и) с %» без лишних элементов телефонии",
            "Предусловия": "SUF-T-01 выполнен; в настройках число карточек 1–5 (по умолчанию 1, если так зафиксировано в ТЗ).",
            "Шаги": "1. Провести диалог с репликами клиента и оператора. 2. Проверить структуру окна: хронология реплик и блок подсказок к реплике клиента. 3. Проверить наличие % релевантности и кнопок полезности у цельных ответов со статьёй СУЗ. 4. Убедиться в отсутствии лишних кнопок «Отправить клиенту» в телефонии.",
            "Ожидаемый результат": "UI соответствует лаконичной ленте §4.6.2; % на карточках; обратная связь на месте; нет смешения с телефонной панелью Oktell.",
            "Стенд": "test Oktell",
            "Связь": "FR-SUF-13 · 4.6.2.2",
        },
    ),
]

SCENARIOS_CHAT: list[tuple[str, dict[str, str]]] = [
    (
        "CHAT-T-06 — Закрытие диалога, история сохранена",
        {
            "Название": "Закрытие диалога с обязательной тематикой и сохранением истории",
            "Предусловия": "Активный диалог в АРМ; оператор online.",
            "Шаги": "1. Завершить переписку. 2. Нажать «Закрыть». 3. Выбрать тематику (обязательно). 4. Подтвердить закрытие. 5. Открыть историю/карточку клиента повторно.",
            "Ожидаемый результат": "Диалог закрыт; тематика сохранена; история переписки доступна; при необходимости показан post-chat опрос клиенту.",
            "Стенд": "Hub staging",
            "Связь": "UC-O4 · FR-CHAT-08 · 4.4",
        },
    ),
    (
        "CHAT-T-08 — Вход в АРМ через AD",
        {
            "Название": "Авторизация оператора онлайн-чата через AD/LDAPS",
            "Предусловия": "Стенд с интеграцией AD (после готовности ДРиРИТ / VII.5 №4). Учётная запись тестового оператора в нужной группе.",
            "Шаги": "1. Открыть АРМ без локального пароля приложения (SSO/AD). 2. Войти доменной УЗ. 3. Проверить доступ к очередям по роли.",
            "Ожидаемый результат": "Успешный вход через AD/LDAPS; права соответствуют роли. Если AD на стенде ещё не готов — статус «открыто», зафиксировать блокер.",
            "Стенд": "Hub staging + AD test",
            "Связь": "FR-CHAT-19 · 4.4 · VII.5 №4",
        },
    ),
    (
        "CHAT-T-09 — Супервизор: наблюдение и перевод",
        {
            "Название": "Супервизор видит диалоги и переназначает",
            "Предусловия": "Роль супервизора; есть активный диалог у оператора A.",
            "Шаги": "1. Открыть экран супервизора. 2. Найти активный диалог оператора A. 3. Перевести/переназначить на оператора B. 4. Проверить АРМ B.",
            "Ожидаемый результат": "Диалог доступен супервизору для наблюдения; после перевода отображается у оператора B и снимается с A (по правилам маршрутизации).",
            "Стенд": "Hub staging",
            "Связь": "UC-S1, UC-S2 · FR-CHAT-18 · 4.4",
        },
    ),
    (
        "CHAT-T-10 — Бот первой линии",
        {
            "Название": "Бот первой линии с эскалацией на оператора",
            "Предусловия": "Администратор включил сценарий бота (UC-A4); оператор online для эскалации.",
            "Шаги": "1. Клиент начинает диалог в виджете. 2. Получить ответ/меню бота. 3. Инициировать эскалацию (запрос оператора / условие сценария). 4. Проверить назначение на оператора.",
            "Ожидаемый результат": "Бот обрабатывает первую линию; при эскалации диалог попадает к оператору без потери истории клиента.",
            "Стенд": "Hub staging + виджет test",
            "Связь": "UC-A4, UC-O7 · FR-CHAT-17 · 4.4",
        },
    ),
    (
        "CHAT-T-11 — Оперативная панель",
        {
            "Название": "Оперативная панель: диалоги + сопутствующая информация в real-time",
            "Предусловия": "Роль супервизора или аналитика; есть активные диалоги телефонии и/или онлайн-чата.",
            "Шаги": "1. Открыть оперативную панель. 2. Проверить наличие списка/карточек диалогов (не только KPI). 3. Открыть карточку диалога и сопутствующие поля (канал, оператор, тематика, времена, подсказка/отметка).",
            "Ожидаемый результат": "В реальном времени видны диалоги со сопутствующей информацией; сводные показатели дополняют список, но не заменяют его (§4.7.3.1).",
            "Стенд": "Hub staging",
            "Связь": "UC-CHAT-R1 · FR-RPT-CC-03 · 4.7.3.1",
        },
    ),
    (
        "CHAT-T-12 — Мессенджер: сообщение → АРМ → ответ",
        {
            "Название": "Канал мессенджера (Telegram/Viber): сквозной ответ",
            "Предусловия": "Адаптер мессенджера настроен (UC-A5); оператор online.",
            "Шаги": "1. Клиент пишет в мессенджер. 2. Диалог появляется в АРМ. 3. Оператор отвечает. 4. Клиент получает ответ в мессенджере.",
            "Ожидаемый результат": "Сообщение доставлено в единое АРМ; ответ клиента уходит в тот же канал; канал идентифицирован в карточке диалога.",
            "Стенд": "Hub staging + test-бот мессенджера",
            "Связь": "UC-K2, UC-A5 · 4.4.6",
        },
    ),
    (
        "CHAT-T-14 — Отчёт за период",
        {
            "Название": "Свод/отчёт онлайн-чата за период с выгрузкой",
            "Предусловия": "Есть закрытые диалоги за период; роль аналитика/админа.",
            "Шаги": "1. Открыть отчётность онлайн-чата / дашборд за период. 2. Задать фильтры канал/период. 3. Проверить ключевые метрики по формулам свода §4.4.41. 4. Выгрузить xlsx/pdf.",
            "Ожидаемый результат": "Отчёт сформирован; значения согласуются с тестовыми диалогами; файл выгрузки открывается.",
            "Стенд": "Hub staging",
            "Связь": "UC-CHAT-R2 · 4.4.41 / 4.7.4",
        },
    ),
    (
        "CHAT-T-15 — Офлайн-обращение",
        {
            "Название": "Офлайн-сообщение вне рабочего времени / без операторов",
            "Предусловия": "Настроено нерабочее время или отсутствуют online-операторы; виджет принимает офлайн.",
            "Шаги": "1. Клиент оставляет вопрос в нерабочее время (или при отсутствии online). 2. Проверить текст клиенту о возможности оставить вопрос. 3. В рабочее время оператор обрабатывает офлайн-обращение из очереди.",
            "Ожидаемый результат": "Обращение сохранено как офлайн; попало в очередь; обработано оператором; в статистике отражено как офлайн.",
            "Стенд": "Hub staging + виджет test",
            "Связь": "UC-K4 · FR-CHAT-15 · 4.4",
        },
    ),
    (
        "CHAT-T-16 — Авто-диалог §4.3.2.8",
        {
            "Название": "Автоматизированный диалоговый сценарий/ветка 4.3.2.8",
            "Предусловия": "Включён соответствующий авто-сценарий (бот/сценарий) на стенде.",
            "Шаги": "1. Клиент инициирует тему, покрытую авто-сценарием. 2. Пройти шаги авто-диалога. 3. При необходимости проверить эскалацию на оператора.",
            "Ожидаемый результат": "Сценарий отрабатывает по настройке; клиент получает предусмотренные ответы/кнопки; эскалация сохраняет контекст.",
            "Стенд": "Hub staging",
            "Связь": "UC-O7 · 4.3.2.8",
        },
    ),
    (
        "CHAT-T-17 — Просмотр диалога коллеги (read-only)",
        {
            "Название": "Оператор/супервизор открывает диалог коллеги без права писать от его имени",
            "Предусловия": "Есть диалог у коллеги; у текущего пользователя есть право просмотра (по RBAC).",
            "Шаги": "1. Открыть раздел «Диалоги коллег» / список. 2. Выбрать диалог коллеги. 3. Попытаться ввести сообщение.",
            "Ожидаемый результат": "История видна; поле ввода недоступно (read-only) либо отправка блокируется; подпись режима просмотра отображается.",
            "Стенд": "Hub staging",
            "Связь": "UC-O8 · 4.4",
        },
    ),
    (
        "CHAT-T-18 — Черновик сообщения клиента в виджете",
        {
            "Название": "Черновик в виджете до отправки не теряется при навигации в рамках сессии",
            "Предусловия": "Виджет на test-странице; функция черновика включена (FR-CHAT-09).",
            "Шаги": "1. Клиент вводит текст, не отправляя. 2. Свернуть/развернуть виджет (или перейти и вернуться в рамках правил продукта). 3. Проверить сохранность черновика. 4. Отправить сообщение.",
            "Ожидаемый результат": "Черновик сохранён до отправки согласно FR-CHAT-09; после отправки становится сообщением в диалоге.",
            "Стенд": "Hub staging + виджет test",
            "Связь": "FR-CHAT-09 · 4.4",
        },
    ),
    (
        "CHAT-T-19 — Блокировка клиента",
        {
            "Название": "Блокировка спам-клиента и отклонение повторного обращения",
            "Предусловия": "Роль с правом блокировки; тестовый клиент.",
            "Шаги": "1. Заблокировать клиента из АРМ/админки. 2. Попытаться начать новый диалог тем же клиентом. 3. Проверить журнал блокировки.",
            "Ожидаемый результат": "Новый диалог отклонён/не создаётся; факт блокировки зафиксирован; разблокировка возможна уполномоченной ролью.",
            "Стенд": "Hub staging",
            "Связь": "FR-CHAT-10 · 4.4.44.5",
        },
    ),
    (
        "CHAT-T-20 — Классификация отказ / потерянный / офлайн",
        {
            "Название": "Система корректно классифицирует незавершённые обращения",
            "Предусловия": "Настроены таймауты; можно смоделировать отказ клиента, потерю и офлайн.",
            "Шаги": "1. Создать диалог и закрыть его клиентом до ответа (отказ). 2. Создать диалог и дождаться таймаута в очереди при online-операторах (пропущенный/потерянный — по правилам). 3. Создать офлайн-обращение. 4. Проверить статусы/отчёт.",
            "Ожидаемый результат": "Каждый кейс имеет корректную классификацию в АРМ/отчётности (отказ / потерянный / офлайн) согласно FR-CHAT-15.",
            "Стенд": "Hub staging",
            "Связь": "FR-CHAT-15 · UC-K4 · 4.4",
        },
    ),
]


def find_child_index(children: list[ET.Element], prefix: str) -> int:
    for i, el in enumerate(children):
        if el.tag != W + "p":
            continue
        t = text_of(el).strip()
        if t.startswith(prefix):
            return i
    raise KeyError(prefix)


def insert_after_scenario(body: ET.Element, after_heading_prefix: str, new_items: list[tuple[str, dict[str, str]]], heading_tpl: ET.Element, table_tpl: ET.Element) -> None:
    children = list(body)
    idx = find_child_index(children, after_heading_prefix)
    # scenario = heading + following table
    insert_at = idx + 1
    if insert_at < len(children) and children[insert_at].tag == W + "tbl":
        insert_at += 1
    # build nodes
    nodes: list[ET.Element] = []
    for title, fields in new_items:
        nodes.append(make_heading(heading_tpl, title))
        nodes.append(make_scenario_table(table_tpl, fields))
    # insert in reverse into body
    # ElementTree doesn't have insert on element prior to 3.9 for list — use manual
    # Rebuild body children
    new_children = children[:insert_at] + nodes + children[insert_at:]
    for ch in list(body):
        body.remove(ch)
    for ch in new_children:
        body.append(ch)
    print(f"Inserted {len(new_items)} scenarios after {after_heading_prefix!r} at {insert_at}")


def patch_status_note(body: ET.Element) -> None:
    for p in body.findall(W + "p"):
        t = text_of(p)
        if "описаны пошагово" in t and "SUF-T-01" in t:
            # replace text in runs
            new = (
                "Статус: в настоящей редакции пошагово описаны SUF-T-01…15 и CHAT-T-01…20 "
                "(включая ранее отсутствовавшие SUF-T-06…11, SUF-T-13…14 и CHAT-T-06,08…12,14…20)."
            )
            for child in list(p):
                if child.tag != W + "pPr":
                    p.remove(child)
            r = ET.SubElement(p, W + "r")
            te = ET.SubElement(r, W + "t")
            te.text = new
            print("Updated status note")
            return


def main() -> None:
    doc_path = UNZ / "word" / "document.xml"
    # Parse with all namespaces preserved as much as possible
    ET.register_namespace("w", "http://schemas.openxmlformats.org/wordprocessingml/2006/main")
    tree = ET.parse(doc_path)
    root = tree.getroot()
    body = root.find(W + "body")
    assert body is not None

    children = list(body)
    h_tpl = children[find_child_index(children, "SUF-T-01")]
    tbl_tpl = children[find_child_index(children, "SUF-T-01") + 1]
    assert tbl_tpl.tag == W + "tbl"

    # Insert SUF missing between 05 and 12
    suf_mid = [x for x in SCENARIOS_SUF if x[0].startswith("SUF-T-0") or x[0].startswith("SUF-T-1") and not x[0].startswith("SUF-T-13") and not x[0].startswith("SUF-T-14")]
    # clearer split:
    suf_06_11 = SCENARIOS_SUF[:6]
    suf_13_14 = SCENARIOS_SUF[6:]

    insert_after_scenario(body, "SUF-T-05", suf_06_11, h_tpl, tbl_tpl)
    insert_after_scenario(body, "SUF-T-12", suf_13_14, h_tpl, tbl_tpl)

    chat_06 = [SCENARIOS_CHAT[0]]
    chat_08_12 = SCENARIOS_CHAT[1:6]
    chat_14_20 = SCENARIOS_CHAT[6:]

    insert_after_scenario(body, "CHAT-T-05", chat_06, h_tpl, tbl_tpl)
    insert_after_scenario(body, "CHAT-T-07", chat_08_12, h_tpl, tbl_tpl)
    insert_after_scenario(body, "CHAT-T-13", chat_14_20, h_tpl, tbl_tpl)

    patch_status_note(body)

    # Write document.xml — keep XML declaration
    xml_bytes = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    # Word often needs standalone namespaces on root; ET may drop some — acceptable if file opens
    doc_path.write_bytes(xml_bytes)
    print("Wrote document.xml", len(xml_bytes))

    # Repack docx WITHOUT modifying comments
    if OUT_DOCX.exists():
        OUT_DOCX.unlink()
    with zipfile.ZipFile(SRC_DOCX, "r") as zin, zipfile.ZipFile(OUT_DOCX, "w", compression=zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename == "word/document.xml":
                data = doc_path.read_bytes()
            # never touch comments*
            zout.writestr(item, data)
    print("OUT", OUT_DOCX, OUT_DOCX.stat().st_size)

    # Verify
    with zipfile.ZipFile(OUT_DOCX) as z:
        assert "word/comments.xml" in z.namelist()
        root2 = ET.fromstring(z.read("word/document.xml"))
        full = "".join(t.text or "" for t in root2.iter(W + "t"))
        for key in [
            "SUF-T-06 —",
            "SUF-T-11 —",
            "SUF-T-13 —",
            "SUF-T-14 —",
            "CHAT-T-06 —",
            "CHAT-T-08 —",
            "CHAT-T-20 —",
        ]:
            print(key, "OK" if key in full else "MISSING")


if __name__ == "__main__":
    main()
