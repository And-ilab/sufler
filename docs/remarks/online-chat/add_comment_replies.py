#!/usr/bin/env python3
"""Add executor reply comments to Чат коррект.docx (body unchanged)."""

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
R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"

AUTHOR = "Андрей Пономарев"
INITIALS = "АП"
CUSTOMER = "Деева Светлана Владимировна"
CUSTOMER_INITIALS = "ДСВ"
REMARK_DATE = "2026-06-10T12:00:00Z"
REPLY_DATE = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

SRC = Path(__file__).parent / "Чат коррект.docx"
OUT = Path(__file__).parent / "Чат коррект +-ответы-исполнителя.docx"
WORK = Path(__file__).parent / "_reply_work"

# match — уникальная подстрока абзаца с правкой заказчика (w:ins)
# Все доработки — в едином согласуемом ТЗ v1.2 (все модули в одном документе).
TZ_V12 = "едином ТЗ v1.2"
MOD_CHAT = "модуль «Онлайн-чат»"
MOD_SUF = "модуль «Суфлёр»"

REMARKS: list[dict[str, str]] = [
    {
        "match": "мессенджеры, социальные сети",
        "remark": "Добавить «социальные сети» в перечень онлайн-каналов (§1.1).",
        "response": (
            f"Принято. В глоссарии ({MOD_CHAT}) уже указаны ВКонтакте и Одноклассники. "
            f"В {TZ_V12} в разделе контекста и состава системы {MOD_CHAT} добавим явную формулировку "
            "«мессенджеры и социальные сети» и отразим их в схеме состава."
        ),
    },
    {
        "match": "контактные данные- при необходимости",
        "remark": "Контактные данные клиента заполняются «при необходимости», не всегда обязательно.",
        "response": (
            f"Согласны. В {MOD_CHAT} уже заложена настраиваемая обязательность полей формы. "
            f"В {TZ_V12} уточним в описании роли «Клиент» и сценарии UC-K1: контактные поля — "
            "по необходимости, в зависимости от настроек размещения виджета и канала."
        ),
    },
    {
        "match": "закрывает, назначает тему диалога",
        "remark": "В действия оператора добавить закрытие диалога и назначение темы.",
        "response": (
            f"Принято. Закрытие описано в UC-O4, назначение темы/категории — в АРМ {MOD_CHAT}. "
            f"В {TZ_V12} явно зафиксируем в роли «Оператор КЦ» и UC-O4: оператор закрывает диалог "
            "и назначает тему/категорию (как правило — при завершении консультации, для отчётности)."
        ),
    },
    {
        "match": "ностройки ( включает все роли)",
        "remark": "У администратора должны быть все настройки (все роли); в UC функций администратора больше, чем в описании роли.",
        "response": (
            f"Согласны. В {TZ_V12} расширим краткое описание роли «Администратор» {MOD_CHAT} "
            "и добавим перекрёстную ссылку на реестр сценариев UC-A1…A5 и панель управления. "
            "Администратор управляет конфигурацией платформы чата; права супервизора и аналитика — "
            "отдельные роли по общей матрице доступа единого ТЗ."
        ),
    },
    {
        "match": "3. Состав системы (добавить соц. сети)",
        "remark": "В составе системы явно указать социальные сети.",
        "response": (
            f"Принято. В {TZ_V12} в составе системы {MOD_CHAT} и блоке «Адаптеры каналов» дополним: "
            "Telegram, Viber, ВКонтакте, Одноклассники (социальные сети) и API-каналы — "
            "единая очередь в АРМ. Согласуется с функциональной матрицей модуля."
        ),
    },
    {
        "match": "и /или иных точек",
        "remark": "Виджет размещается не только на публичном сайте, но и в иных точках входа.",
        "response": (
            f"Согласны. «Иные точки» — страницы интернет-банка, мобильного приложения "
            f"(при интеграции), лендинги — через отдельные размещения виджета. "
            f"В {TZ_V12} в разделе виджета {MOD_CHAT} уточним: размещение на всех согласованных "
            "точках контакта с клиентом, не только на основном сайте."
        ),
    },
    {
        "match": "по настройке со стороны банка – клиенту эту информацию",
        "remark": "Индикатор «операторы онлайн / очередь / время ответа» — настраиваемый; при занятости всех — текст «в настоящее время все операторы заняты…».",
        "response": (
            f"Принято. В {TZ_V12} индикатор статуса {MOD_CHAT} будет настраиваемым в редакторе "
            "размещения (панель управления, вкладка «Окно чата»): администратор включает/отключает "
            "элементы и задаёт тексты. При занятости всех операторов — системное сообщение "
            "с согласованной формулировкой. Видимость очереди и ETA для клиента — опционально."
        ),
    },
    {
        "match": "ИБ – это что?",
        "remark": "Непонятна аббревиатура «ИБ».",
        "response": (
            "ИБ — подразделение информационной безопасности банка. "
            f"«В объёме, согласованном с ИБ» означает: типы файлов, размеры, антивирусная проверка "
            f"и политика хранения — по требованиям ИБ (общий раздел ИБ {TZ_V12}, главы 8–9 ТТ). "
            "При первом упоминании в документе добавим расшифровку: «ИБ (информационная безопасность)»."
        ),
    },
    {
        "match": "список тем – сделать настраиваемым полем",
        "remark": "Поле «Тема» на форме входа — настраиваемое; тему определяет оператор в конце диалога.",
        "response": (
            f"Принято. В {TZ_V12} поле «Тема» на форме входа {MOD_CHAT} — настраиваемое: "
            "можно отключить или сделать необязательным. Итоговая категория/тема для отчётности "
            "назначается оператором при закрытии диалога (UC-O4) — из справочника «Шаблоны и категории» "
            "панели управления."
        ),
    },
    {
        "match": "настраивоемое поле – клиенту эта инфа не нужна",
        "remark": "Строка статуса на форме входа — настраиваемая; клиенту эта информация не обязательна.",
        "response": (
            f"Согласны полностью. В {TZ_V12} строка статуса на форме входа {MOD_CHAT} — "
            "опциональный элемент размещения: по умолчанию рекомендуем минимальную форму "
            "(тема + контакты без блока статуса). Настройка — в редакторе размещения."
        ),
    },
    {
        "match": "Фото оператора, Имя оператора, имя клиента)",
        "remark": "В диалоге отображать фото оператора, имя оператора и имя клиента.",
        "response": (
            f"Принято. В {TZ_V12} в активном диалоге виджета {MOD_CHAT} в шапке переписки зафиксируем: "
            "имя оператора (из профиля AD/настроек), опционально — фото/аватар оператора "
            "(настраивается администратором), имя клиента (из формы или уточнённое оператором). "
            "При отсутствии фото — инициалы или стандартный аватар."
        ),
    },
    {
        "match": "тема, и иные поля – возможность настройки",
        "remark": "Тема и иные поля формы — с возможностью настройки.",
        "response": (
            f"Согласны. В {TZ_V12} в разделе виджета и сценарии UC-A2 {MOD_CHAT} явно укажем: "
            "администратор задаёт набор полей, обязательность и порядок для каждого размещения "
            "(вкладка «Данные клиента» панели управления)."
        ),
    },
    {
        "match": "в диалоге с другими ( для обзора всеми операторами)",
        "remark": "Нужен раздел «В диалоге с другими» для обзора диалогов коллег всеми операторами.",
        "response": (
            f"Принято. В {TZ_V12} раздел «Диалоги коллег» (в интерфейсе — «В диалоге с другими») "
            f"{MOD_CHAT} доступен всем операторам отдела: список активных диалогов коллег, переписка "
            "и контекст клиента — только чтение (пометка «Режим просмотра», без ответа клиенту "
            "и без перевода). Супервизор в том же разделе дополнительно переводит диалоги (UC-S2). "
            "Включение обзора для операторов — настройка отдела (по умолчанию включено). "
            "Сценарий UC-O8."
        ),
    },
    {
        "match": "сообщение клиента которое он вводит, но еще не отправил",
        "remark": "В АРМ видно, что клиент набирает сообщение (ещё не отправил); нужна кнопка «блокировки».",
        "response": (
            f"Принято. В {TZ_V12} в АРМ {MOD_CHAT}: в виджете оператор видит черновик сообщения "
            "клиента в ленте в реальном времени (плашка «Клиент набирает…» с текстом по мере ввода; "
            "исчезает после отправки или паузы). В мессенджерах — только индикатор «клиент печатает» "
            "(ограничение API). Кнопка «Заблокировать» в шапке диалога: по подтверждению клиент "
            "не может писать, диалог закрывается, идентификатор — в список блокировок "
            "(повторные обращения из виджета отклоняются; снятие — администратором). "
            "Событие — в общий журнал аудита единого ТЗ."
        ),
    },
    {
        "match": "обед ( влияет на расчет статистики",
        "remark": "Добавить статус «обед» (учёт в статистике); режим обработки офлайн-сообщений, чтобы не падали онлайн-диалоги.",
        "response": (
            f"Принято. В {TZ_V12} расширим перечень статусов оператора {MOD_CHAT}: "
            "онлайн, невидимка, перерыв, обед, офлайн — каждый влияет на автоназначение "
            "и отчётность (UC-R2). Отдельный режим «Обработка офлайн-обращений»: оператор "
            "получает офлайн-диалоги, не участвует в автоназначении онлайн. "
            "Параметры — в настройках оператора/отдела (UC-A1, UC-A3)."
        ),
    },
    {
        "match": "возможно нужен еще статус «неверно»",
        "remark": "К обратной связи суфлёра «Полезно / Неполно» добавить статус «неверно».",
        "response": (
            f"Согласны. В {TZ_V12} добавим третий вариант обратной связи — «Неверно» "
            f"(или «Не подходит») — в панели суфлёра АРМ {MOD_CHAT}. "
            f"Детальная спецификация фидбека и обучения модели — в разделе {MOD_SUF} "
            "того же документа; в модуле чата зафиксируем точку интерфейса и передачу события (UC-O2)."
        ),
    },
    {
        "match": "офлайн диалог становится только при ожидании заданного времени",
        "remark": "Уточнение логики офлайн/потерянных/отказов в UC-K1: настраиваемые пороги, таймер отказа до 60 сек.",
        "response": (
            f"Принято. В {TZ_V12} в сценариях UC-K1 и UC-K4 {MOD_CHAT} детализируем логику: "
            "клиент закрыл окно до первого ответа в рабочее время — «отказ» или «потерянный» "
            "(настраиваемые пороги, в т.ч. таймер до 60 сек); после начала переписки — "
            "офлайн-обращение; в нерабочее время — офлайн-очередь. "
            "Пороги — в настройках администратора и блоке открытых вопросов модуля."
        ),
    },
]


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


def split_paragraphs(text: str) -> list[str]:
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


def build_comment_xml(
    comment_id: int,
    author: str,
    initials: str,
    paragraphs: list[str],
    *,
    date: str | None = None,
) -> tuple[str, str]:
    rsid = new_rsid()
    para_ids = [new_para_id() for _ in paragraphs]
    parts = [
        f'<w:comment w:id="{comment_id}" w:author="{author}" '
        f'w:date="{date or REPLY_DATE}" w:initials="{initials}">'
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


def paragraph_has_customer_ins(p: ET.Element) -> bool:
    for ins in p.findall(f".//{W}ins"):
        if ins.get(W + "author", "") == CUSTOMER:
            return True
    return False


def inject_comment_pair(p: ET.Element, remark_id: int, reply_id: int) -> None:
    """Якорь пары: замечание заказчика + ответ исполнителя на том же абзаце."""
    remark_cid = str(remark_id)
    reply_cid = str(reply_id)

    insert_idx = 1 if list(p) and list(p)[0].tag == W + "pPr" else 0

    start_remark = ET.Element(W + "commentRangeStart")
    start_remark.set(W + "id", remark_cid)
    start_reply = ET.Element(W + "commentRangeStart")
    start_reply.set(W + "id", reply_cid)
    p.insert(insert_idx, start_reply)
    p.insert(insert_idx, start_remark)

    end_reply = ET.Element(W + "commentRangeEnd")
    end_reply.set(W + "id", reply_cid)
    end_remark = ET.Element(W + "commentRangeEnd")
    end_remark.set(W + "id", remark_cid)
    p.append(end_reply)
    p.append(end_remark)

    for cid in (remark_cid, reply_cid):
        ref_p = ET.Element(W + "r")
        ref = ET.SubElement(ref_p, W + "commentReference")
        ref.set(W + "id", cid)
        p.append(ref_p)


def find_matching_remark(para_text: str, used: set[int]) -> int | None:
    for i, item in enumerate(REMARKS):
        if i in used:
            continue
        if item["match"] in para_text:
            return i
    return None


def build_comments_files(remark_indices: list[int]) -> tuple[str, str]:
    """Пара на каждое замечание: заказчик (Деева) → ответ исполнителя (Пономарёв)."""
    comments: list[str] = []
    extended: list[str] = []

    for pair_idx, idx in enumerate(remark_indices):
        item = REMARKS[idx]
        remark_id = pair_idx * 2
        reply_id = pair_idx * 2 + 1

        remark_body = split_paragraphs(item["remark"])
        reply_body = split_paragraphs(item["response"])

        remark_xml, remark_para_id = build_comment_xml(
            remark_id, CUSTOMER, CUSTOMER_INITIALS, remark_body, date=REMARK_DATE
        )
        reply_xml, reply_para_id = build_comment_xml(reply_id, AUTHOR, INITIALS, reply_body)

        comments.append(remark_xml)
        comments.append(reply_xml)
        extended.append(f'<w15:commentEx w15:paraId="{remark_para_id}" w15:done="0"/>')
        extended.append(
            f'<w15:commentEx w15:paraId="{reply_para_id}" '
            f'w15:paraIdParent="{remark_para_id}" w15:done="0"/>'
        )

    ns = (
        'xmlns:wpc="http://schemas.microsoft.com/office/word/2010/wordprocessingCanvas" '
        'xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
        'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
        'xmlns:w14="http://schemas.microsoft.com/office/word/2010/wordml" '
        'xmlns:w15="http://schemas.microsoft.com/office/word/2012/wordml" '
        'mc:Ignorable="w14 w15"'
    )
    comments_xml = (
        f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        f'<w:comments {ns}>{"".join(comments)}</w:comments>'
    )
    extended_xml = (
        f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        f'<w15:commentsEx {ns}>{"".join(extended)}</w15:commentsEx>'
    )
    return comments_xml, extended_xml


def ensure_people(people_xml: str) -> str:
    for author in (AUTHOR, CUSTOMER):
        if author in people_xml:
            continue
        insert_at = people_xml.rfind("</w15:people>")
        person = (
            f'<w15:person w15:author="{author}">'
            f'<w15:presenceInfo w15:providerId="None" w15:userId="{author}"/>'
            f"</w15:person>"
        )
        people_xml = people_xml[:insert_at] + person + people_xml[insert_at:]
    return people_xml


def patch_content_types(content_types: str) -> str:
    if "comments.xml" in content_types:
        return content_types
    insert = content_types.rfind("</Types>")
    overrides = (
        '<Override PartName="/word/comments.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.comments+xml"/>'
        '<Override PartName="/word/commentsExtended.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.commentsExtended+xml"/>'
    )
    return content_types[:insert] + overrides + content_types[insert:]


def patch_document_rels(rels_xml: str) -> str:
    if "comments.xml" in rels_xml:
        return rels_xml
    ids = [int(m.group(1)) for m in re.finditer(r'Id="rId(\d+)"', rels_xml)]
    next_id = max(ids) + 1 if ids else 1
    insert = rels_xml.rfind("</Relationships>")
    additions = (
        f'<Relationship Id="rId{next_id}" '
        f'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/comments" '
        f'Target="comments.xml"/>'
        f'<Relationship Id="rId{next_id + 1}" '
        f'Type="http://schemas.microsoft.com/office/2011/relationships/commentsExtended" '
        f'Target="commentsExtended.xml"/>'
    )
    return rels_xml[:insert] + additions + rels_xml[insert:]


def patch_document_root(document_xml: str) -> str:
    if "xmlns:w15=" in document_xml:
        return document_xml
    return document_xml.replace(
        'xmlns:w14="http://schemas.microsoft.com/office/word/2010/wordml"',
        'xmlns:w14="http://schemas.microsoft.com/office/word/2010/wordml" '
        'xmlns:w15="http://schemas.microsoft.com/office/word/2012/wordml"',
        1,
    )


def main() -> None:
    if not SRC.exists():
        raise SystemExit(f"Source not found: {SRC}")

    if WORK.exists():
        shutil.rmtree(WORK)
    WORK.mkdir()

    with zipfile.ZipFile(SRC, "r") as zin:
        zin.extractall(WORK)

    doc_path = WORK / "word" / "document.xml"
    root = ET.parse(doc_path).getroot()

    doc_path.write_text(patch_document_root(doc_path.read_text(encoding="utf-8")), encoding="utf-8")
    root = ET.parse(doc_path).getroot()

    used: set[int] = set()
    remark_indices: list[int] = []
    comment_id = 0

    for p in root.iter(W + "p"):
        if not paragraph_has_customer_ins(p):
            continue
        para_text = text_of(p)
        idx = find_matching_remark(para_text, used)
        if idx is None:
            print(f"WARNING: unmatched paragraph: {para_text[:120]}...")
            continue
        used.add(idx)
        remark_indices.append(idx)
        inject_comment_pair(p, comment_id, comment_id + 1)
        comment_id += 2

    if len(remark_indices) != len(REMARKS):
        missing = [REMARKS[i]["match"] for i in range(len(REMARKS)) if i not in used]
        raise SystemExit(f"Matched {len(remark_indices)}/{len(REMARKS)} remarks. Missing: {missing}")

    ET.register_namespace("w", W[1:-1])
    ET.register_namespace("w14", W14[1:-1])
    ET.register_namespace("w15", W15[1:-1])
    tree = ET.ElementTree(root)
    tree.write(doc_path, encoding="UTF-8", xml_declaration=True)

    comments_xml, extended_xml = build_comments_files(remark_indices)
    (WORK / "word" / "comments.xml").write_text(comments_xml, encoding="utf-8")
    (WORK / "word" / "commentsExtended.xml").write_text(extended_xml, encoding="utf-8")

    people_path = WORK / "word" / "people.xml"
    people_path.write_text(
        ensure_people(people_path.read_text(encoding="utf-8")),
        encoding="utf-8",
    )

    ct_path = WORK / "[Content_Types].xml"
    ct_path.write_text(patch_content_types(ct_path.read_text(encoding="utf-8")), encoding="utf-8")

    rels_path = WORK / "word" / "_rels" / "document.xml.rels"
    rels_path.write_text(patch_document_rels(rels_path.read_text(encoding="utf-8")), encoding="utf-8")

    out_path = OUT
    if out_path.exists():
        try:
            out_path.unlink()
        except PermissionError:
            out_path = OUT.with_name(OUT.stem + " (new)" + OUT.suffix)
            print(f"WARNING: {OUT.name} is open — writing to {out_path.name}")

    with zipfile.ZipFile(out_path, "w", compression=zipfile.ZIP_DEFLATED) as zout:
        for file_path in WORK.rglob("*"):
            if file_path.is_file():
                zout.write(file_path, file_path.relative_to(WORK).as_posix())

    print(f"Written: {out_path}")
    print(
        f"Comment pairs: {len(remark_indices)} "
        f"({CUSTOMER} -> {AUTHOR})"
    )


if __name__ == "__main__":
    main()
