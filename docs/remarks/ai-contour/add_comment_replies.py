#!/usr/bin/env python3
"""Add threaded replies to Word comments in TZ-AI-Hub DOCX (body unchanged)."""

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

SRC = Path(__file__).parent / "TZ-AI-Hub +.docx"
OUT = Path(__file__).parent / "TZ-AI-Hub +-ответы-исполнителя.docx"
WORK = Path(__file__).parent / "_reply_work"

# None = без ответа (зона внутреннего ДИТ заказчика)
RESPONSES: dict[str, str | None] = {
    "0": (
        "Принято. Цель 3 описывает размещение интерфейса: телефония — вкладка «Суфлёр» "
        "в панели контура ИИ (Oktell); онлайн-чат — правая колонка АРМ чата (п. I.2.3). "
        "Формулировку цели уточним, чтобы не дублировать таблицу I.2.3."
    ),
    "1": (
        "Колонка «Суфлёр в работе» — где оператор получает подсказки (панель контура ИИ / АРМ чата); "
        "«Вкладка в панели» — видимость вкладки в выдвижном макете. Переименуем заголовки и добавим пояснение в I.2.3."
    ),
    "2": (
        "«Нет» — вкладка сознательно скрыта для роли (например, оператор чата). "
        "«—» — не применимо. В версии 1.2 добавим легенду в I.1 и проверим ячейки по ТТ."
    ),
    "3": (
        "Принято. «Рабочий индекс» — термин контура ИИ для рабочего поискового индекса КЦ; "
        "в ТЗ по Битрикс — та же сущность. В версии 1.2 — единый глоссарий и перекрёстные ссылки."
    ),
    "4": (
        "Согласны. Матрица I.4 и роли модулей будут перестроены по минимальному набору "
        "ролей Прил.1 §2.4 с явными ссылками; дополнительные роли — только с обоснованием."
    ),
    "5": (
        "Согласны: «Суфлёр» — один модуль для КЦ (телефония и чат); различие только в точке "
        "интерфейса (панель контура ИИ и АРМ). Уточним в II.1 и I.2."
    ),
    "6": (
        "Принято. Расширим вводные разделы и добавим таблицу трассировки "
        "«пункт Прил.1 → раздел ТЗ → сценарий → приёмка» (I.1)."
    ),
    "7": (
        "Сводная таблица I.8 — обзор размещения функций по модулям и каналам, не смешение продуктов. "
        "При необходимости разобьём на подтаблицы по модулю."
    ),
    "8": "См. ответ к замечанию №2: «нет» = вкладка отключена; «—» = не применимо. Унифицируем в легенде I.1.",
    "9": (
        "Прил.1 (ТТ) — приложение к договору; настоящее ТЗ — проектная детализация этапа 1 "
        "со ссылками на пункты ТТ, без полного дублирования текста ТТ."
    ),
    "10": (
        "Принято. В каждый сценарий использования добавим ссылки на пункты Прил.1; "
        "в таблицах сценариев — колонку «ТТ»."
    ),
    "11": (
        "Перевод рус↔англ — п. 5.1.21–22, сценарий UC-ASS-11, требование FR-ASS-25, слайд III-7. "
        "В сводке «Инструменты» указан; дополним явной строкой в таблице функций §III.1."
    ),
    "12": (
        "Имелось в виду число одновременных пользователей (требование FR-ASS-36, п. 5.1.35 ТТ). "
        "Заменим формулировку на «до 2000 одновременных пользователей»."
    ),
    "13": (
        "Раздел «Не входит» фиксирует границы договора и отсылает к дочерним ТЗ. "
        "Можем сократить до ссылок без перечисления чужого функционала."
    ),
    "14": "См. ответ к №4: роли — по минимальному набору Прил.1 §2.4.",
    "15": (
        "Роли «Аналитик КЦ / ИИ-ассистента / распознавания документов» (Прил.1 §2.4 п. 7, 10, 13) "
        "будут добавлены в матрицы I.4 и модульные разделы с правами на отчётность."
    ),
    "16": (
        "Имеется в виду «Администратор системы» / администраторы модулей по ТТ. "
        "Уберём нестандартную формулировку, приведём к номенклатуре Прил.1 §2.4."
    ),
    "17": (
        "Строка «Оператор КЦ» поясняет, что основная роль КЦ не получает вкладку «Ассистент». "
        "Перенесём в примечание к матрице, не как самостоятельную роль модуля."
    ),
    "18": (
        "Если роль «Аудитор» (только просмотр) отсутствует в минимальном наборе ТТ — уберём из матрицы; "
        "права просмотра журналов закрепим за ролями по ТТ (администратор, аналитик)."
    ),
    "19": "См. ответ к №10: добавим явные ссылки на пункты Прил.1 в разделе «Ассистент».",
    "20": (
        "«Выбор базы знаний» — элемент панели инструментов: активная база, если у пользователя их несколько "
        "(по подразделению, п. 5.1.x ТТ). Не подмена источника суфлёра КЦ."
    ),
    "21": (
        "Перевод текста запроса и ответа рус↔англ (п. 5.1.21–22), не конвертация формата файла. "
        "Переключатель языка на панели инструментов — режим языка ответа и интерфейса."
    ),
    "23": (
        "III-2 — номер слайда «Состояния интерфейса» (пустой, потоковый вывод, ошибка), не код ошибки. "
        "Уточним подпись в §III.3."
    ),
    "24": (
        "Согласны: в ТЗ закрепим требования к интерфейсу из ТТ (§4.x, §5.x); макеты на холсте — иллюстрация, "
        "финальные экраны — на этапе реализации с приёмкой по ASS-T/SUF-T."
    ),
    "28": (
        "Принято. В версии 1.2: реестр сценариев с привязкой к ТТ, далее функциональные требования "
        "и настройки со ссылками на сценарии — по предложенной структуре."
    ),
    "29": (
        "«Выбор базы знаний» — активная база для диалога; подразделение задаёт доступный список баз. "
        "Связь опишем в §III.6."
    ),
    "30": (
        "Источники баз знаний: зеркало СУЗ, загрузки администратора, адаптеры (глоссарий I.3, §III.6). "
        "Добавим явную ссылку на пункт ТТ."
    ),
    "31": (
        "Маркер «+ загрузка» — поддерживаемые операции импорта в базу знаний (файлы и программный интерфейс). "
        "Раскроем в функциональных требованиях или заменим однозначной формулировкой."
    ),
    "32": (
        "Да, перечень внутренних (СУЗ, каталог пользователей) и внешних (адаптеры) источников — "
        "в §III.6/IV.7 с отсылкой к ТТ. Дополним таблицей."
    ),
    "33": (
        "При отсутствии программного интерфейса — загрузка файлов, административный интерфейс "
        "или пакетная обработка; детали — в дочернем ТЗ интеграции и V.2. Зафиксируем резервный способ."
    ),
    "34": (
        "«+ согласование ИБ» означает: функцию реализуем мы, но ввод в эксплуатацию — "
        "после согласования подразделением информационной безопасности банка "
        "(например, генерация изображений, п. 5.1.8.4). ИБ оценивает риски: утечка данных "
        "в запросах, недопустимый контент, политику использования."
    ),
    "35": (
        "«[Платформа]» — общий слой программного обеспечения проекта (оркестрация языковых моделей, "
        "поиск по базам знаний, безопасность и аудит), который используют все модули. "
        "Контракт на использование платформы; её детальную спецификацию в данном ТЗ не дублируем (легенда I.1)."
    ),
    "36": (
        "«+ ИБ [Заказчик]» — совместная ответственность: мы реализуем технические меры в продукте "
        "(фильтры, журналирование, разграничение доступа), политики и контроль — ИБ и заказчик "
        "(п. 5.1.14, главы 8–9 ТТ). Принято: в версии 1.2 добавим раздел по ИБ с полным покрытием глав 8–9."
    ),
    "37": (
        "См. №36: требования защищённого соединения и локальной установки детализируем "
        "в разделе ИБ и §V.1 поставки."
    ),
    "38": (
        "Да, интеграция предусмотрена: вход и авторизация через каталог Active Directory "
        "(п. 5.1.33–34, 7.1 ТТ) — по протоколу LDAPS (защищённое соединение, порт 636). "
        "ДИТ заказчика: параметры подключения, сертификаты, служебная учётная запись, "
        "создание и ведение групп безопасности в структуре каталога (переданные материалы "
        "«Структура_AD», тестовый контур BANK.ldif). "
        "Исполнитель: модуль аутентификации, чтение групп пользователя и атрибутов "
        "(подразделение, организация), разграничение доступа по матрице §I.4. "
        "Детальную спецификацию подключения LDAPS вынесем в доработку ТЗ v1.2."
    ),
    "39": (
        "«Системная интеграция / только программный интерфейс» — техническая учётная запись "
        "для обратных вызовов и синхронизации, не пользовательская роль. "
        "Перенесём из таблицы ролей в §III.7 (интеграции)."
    ),
    "40": (
        "«Совместно с ИБ» — инструмент «Код/SQL» (п. 5.1.39): мы реализуем интерфейс и механизм запросов, "
        "ИБ задаёт белый список баз и схем, режим «только чтение», кто видит инструмент. "
        "Детали — §III.6 и вопросы 14.1–14.10 (V.2)."
    ),
    "41": (
        "Ссылка ASS-T-UI-04 — трассировка к интеграции Oktell. Если не относится к «Ассистенту», "
        "перенесём в II.3 / ТЗ Oktell."
    ),
    "42": (
        "Имя пространства сценариев КЦ в редакторе (II.6.1), не модуль «Документы». "
        "Переименуем и поясним, чтобы не путать с распознаванием документов."
    ),
    "43": (
        "Принято. Имеются в виду внутренние отсылки вида «§III.9», «п. III.6» — сейчас они "
        "выглядят как обозначения без перехода. В версии 1.2 заменим их на активные "
        "перекрёстные ссылки Word с понятным текстом (название раздела / сценария), "
        "чтобы по клику открывался нужный фрагмент ТЗ. То же — для ссылок на связанные документы."
    ),
    "45": "См. №4: роли — в соответствии с минимальным набором Прил.1 §2.4.",
    "46": (
        "Автозагрузка через программный интерфейс — технический контур интеграции, не роль пользователя. "
        "Вынесем из таблицы «Роли» в раздел интеграций (см. также №39)."
    ),
    "47": (
        "Экспорт отчётов и выгрузок — отдельное действие в интерфейсе (кнопка «Экспорт»). "
        "Уточним в сценариях отчётности модуля «Документы»."
    ),
    "48": (
        "Добавим описание сценария UC-DOC-02-07 (или исправим нумерацию, если опечатка). "
        "Проверим реестр сценариев модуля «Документы»."
    ),
    "49": (
        "Да, поняли: в перечень поддерживаемых форматов модуля «Документы» нужно явно "
        "включить JPEG (п. 6.1.6 ТТ: .jpg, .jpeg). Сейчас указаны PDF/JPG/PNG/TIFF — "
        "в версии 1.2 приведём к формулировке ТТ: PDF, JPEG, PNG, TIFF (исправим опечатку «gpeg»)."
    ),
    "50": (
        "Принято. Раздел IV дополним требованиями ИБ по главам 8–9 ТТ "
        "(обработка документов, хранение, разграничение доступа)."
    ),
}


def new_para_id() -> str:
    return f"{random.randint(0, 0xFFFFFF):06X}"


def new_rsid() -> str:
    return f"{random.randint(0, 0xFFFFFF):06X}"


def text_of(el: ET.Element) -> str:
    parts: list[str] = []
    for t in el.iter(W + "t"):
        if t.text:
            parts.append(t.text)
        if t.tail:
            parts.append(t.tail)
    return "".join(parts).strip()


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


def build_reply_comment_xml(comment_id: int, paragraphs: list[str]) -> str:
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
    """Map comment id -> paraId of first paragraph (reply anchor)."""
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


def add_replies(
    comments_xml: str, comments_ext_xml: str
) -> tuple[str, str, dict[str, str], int]:
    """Return updated comments, extended, mapping parent_id -> reply_id, count."""
    parents = parse_comment_parents(comments_xml)
    next_id = max_comment_id(comments_xml) + 1
    added = 0
    parent_to_reply: dict[str, str] = {}

    insert_pos = comments_xml.rfind("</w:comments>")
    if insert_pos == -1:
        raise RuntimeError("Invalid comments.xml")

    new_comments: list[str] = []
    new_ext_entries: list[str] = []

    for cid in sorted(parents.keys(), key=lambda x: int(x)):
        response = RESPONSES.get(cid)
        if not response:
            continue
        reply_id = str(next_id)
        xml_block, reply_para_id = build_reply_comment_xml(next_id, split_comment_paragraphs(response))
        new_comments.append(xml_block)
        new_ext_entries.append(
            f'<w15:commentEx w15:paraId="{reply_para_id}" '
            f'w15:paraIdParent="{parents[cid]}" w15:done="0"/>'
        )
        parent_to_reply[cid] = reply_id
        next_id += 1
        added += 1

    updated_comments = comments_xml[:insert_pos] + "".join(new_comments) + comments_xml[insert_pos:]

    ext_insert = comments_ext_xml.rfind("</w15:commentsEx>")
    if ext_insert == -1:
        raise RuntimeError("Invalid commentsExtended.xml")
    updated_ext = (
        comments_ext_xml[:ext_insert] + "".join(new_ext_entries) + comments_ext_xml[ext_insert:]
    )

    return updated_comments, updated_ext, parent_to_reply, added


def add_reply_anchors(document_xml: str, parent_to_reply: dict[str, str]) -> str:
    """Attach each reply as a visible comment marker at the same place as the question."""
    for parent_id, reply_id in sorted(parent_to_reply.items(), key=lambda x: int(x[0]), reverse=True):
        anchor = (
            f'<w:commentRangeStart w:id="{reply_id}"/>'
            f'<w:commentRangeEnd w:id="{reply_id}"/>'
            f'<w:commentReference w:id="{reply_id}"/>'
        )
        pattern = rf'(<w:commentReference w:id="{parent_id}"/>)'
        document_xml, count = re.subn(pattern, r"\1" + anchor, document_xml, count=1)
        if count == 0:
            # fallback: zero-width anchor before closing body (comment #6 and similar)
            document_xml = document_xml.replace(
                "</w:body>",
                anchor + "</w:body>",
                1,
            )
    return document_xml


def verify_output(comments_xml: str, parent_to_reply: dict[str, str]) -> None:
    root = ET.fromstring(comments_xml)
    customer = sum(
        1 for c in root.findall(W + "comment") if c.get(W + "author") != AUTHOR
    )
    executor = sum(
        1 for c in root.findall(W + "comment") if c.get(W + "author") == AUTHOR
    )
    if customer != 46 or executor != len(parent_to_reply):
        raise RuntimeError(
            f"Verification failed: customer={customer}, executor={executor}, "
            f"expected 46/{len(parent_to_reply)}"
        )


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

    if WORK.exists():
        shutil.rmtree(WORK)
    WORK.mkdir()

    with zipfile.ZipFile(SRC, "r") as zin:
        zin.extractall(WORK)

    comments_path = WORK / "word" / "comments.xml"
    ext_path = WORK / "word" / "commentsExtended.xml"
    people_path = WORK / "word" / "people.xml"
    document_path = WORK / "word" / "document.xml"

    comments_xml = comments_path.read_text(encoding="utf-8")
    ext_xml = ext_path.read_text(encoding="utf-8")
    document_xml = document_path.read_text(encoding="utf-8")

    updated_comments, updated_ext, parent_to_reply, added = add_replies(comments_xml, ext_xml)
    updated_document = add_reply_anchors(document_xml, parent_to_reply)

    verify_output(updated_comments, parent_to_reply)

    comments_path.write_text(updated_comments, encoding="utf-8")
    ext_path.write_text(updated_ext, encoding="utf-8")
    document_path.write_text(updated_document, encoding="utf-8")
    people_path.write_text(
        ensure_executor_in_people(people_path.read_text(encoding="utf-8")),
        encoding="utf-8",
    )

    temp_out = OUT.with_name(OUT.stem + "._tmp.docx")
    if temp_out.exists():
        temp_out.unlink()

    with zipfile.ZipFile(temp_out, "w", compression=zipfile.ZIP_DEFLATED) as zout:
        for file_path in WORK.rglob("*"):
            if file_path.is_file():
                arcname = file_path.relative_to(WORK).as_posix()
                zout.write(file_path, arcname)

    try:
        if OUT.exists():
            OUT.unlink()
        temp_out.replace(OUT)
    except PermissionError:
        fallback = OUT.with_name(OUT.stem + " (new).docx")
        temp_out.replace(fallback)
        print(f"WARNING: {OUT.name} is locked (close Word). Written to: {fallback}")
        return

    print(f"Written: {OUT}")
    print(f"Customer comments: 46")
    print(f"Executor replies: {added} (author: {AUTHOR})")
    print(f"Reply anchors in document.xml: {added}")


if __name__ == "__main__":
    main()
