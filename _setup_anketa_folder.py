# -*- coding: utf-8 -*-
"""Setup anketa folder: incoming/, _extracted/, README, extract texts."""
import os
import shutil
import zipfile
import xml.etree.ElementTree as ET
import re

BASE = os.path.join(
    r"c:\sufler\docs\sources",
    "\u0430\u043d\u043a\u0435\u0442\u0430 \u043f\u043e \u043a\u0438\u0431\u0435\u0440\u0443\u0441\u0442\u043e\u0439\u0447\u0438\u0432\u043e\u0441\u0442\u0438",
)
INCOMING = os.path.join(BASE, "incoming")
EXTRACTED = os.path.join(BASE, "_extracted")
PROJECT = "ПО на базе искусственного интеллекта для банковских процессов"
CONTRACT = "№ 14-03/2026"

INCOMING_MAP = {
    "\u0410\u043d\u043a\u0435\u0442\u0430 \u043a\u0438\u0431\u0435\u0440\u0443\u0441\u0442\u043e\u0439\u0447\u0438\u0432\u043e\u0441\u0442\u0438.docx (2).pdf": "anketa-zapolnennaya.pdf",
    "\u0417\u0430\u043a\u043b\u044e\u0447\u0435\u043d\u0438\u0435 \u0413\u0421 \u0420\u0438\u0442\u0435\u0439\u043b.pdf": "zaklyuchenie-bank.pdf",
    "\u043f\u0435\u0440\u0435\u043f\u0438\u0441\u043a\u0430.odt": "perepiska.odt",
}


def ensure_dirs():
    os.makedirs(INCOMING, exist_ok=True)
    os.makedirs(EXTRACTED, exist_ok=True)


def reorganize_incoming():
    for src_name, dst_name in INCOMING_MAP.items():
        src = os.path.join(BASE, src_name)
        dst = os.path.join(INCOMING, dst_name)
        if os.path.isfile(src) and not os.path.isfile(dst):
            shutil.copy2(src, dst)
            print("incoming:", dst_name)


def extract_odt(path, out_path):
    with zipfile.ZipFile(path) as z:
        root = ET.fromstring(z.read("content.xml"))
    ns = "{urn:oasis:names:tc:opendocument:xmlns:text:1.0}"

    def text(el):
        t = el.text or ""
        for c in el:
            t += text(c)
            if c.tail:
                t += c.tail
        return t

    lines = []
    for tag in ("h", "p"):
        for el in root.iter(ns + tag):
            s = text(el).strip()
            if s:
                lines.append(s)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("extracted odt:", out_path)


def extract_pdf_simple(path, out_path):
    """Best-effort PDF text via reading binary strings (works for text PDFs)."""
    with open(path, "rb") as f:
        data = f.read()
    # extract text between stream markers - fallback: decode latin chunks
    chunks = re.findall(rb"[\x20-\x7e\u0400-\u04ff]{4,}", data)
    text = "\n".join(c.decode("utf-8", errors="ignore") for c in chunks[:5000])
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(text)
    print("extracted pdf:", out_path, len(text), "chars")


def try_pypdf(path, out_path):
    try:
        from pypdf import PdfReader  # type: ignore
        reader = PdfReader(path)
        parts = []
        for page in reader.pages:
            parts.append(page.extract_text() or "")
        text = "\n".join(parts)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(text)
        print("extracted pdf (pypdf):", out_path)
        return True
    except Exception:
        return False


def extract_all():
    pdf_anketa = os.path.join(INCOMING, "anketa-zapolnennaya.pdf")
    pdf_zakl = os.path.join(INCOMING, "zaklyuchenie-bank.pdf")
    odt = os.path.join(INCOMING, "perepiska.odt")
    if os.path.isfile(pdf_anketa):
        out = os.path.join(EXTRACTED, "anketa.txt")
        if not try_pypdf(pdf_anketa, out):
            extract_pdf_simple(pdf_anketa, out)
    if os.path.isfile(pdf_zakl):
        out = os.path.join(EXTRACTED, "zaklyuchenie.txt")
        if not try_pypdf(pdf_zakl, out):
            extract_pdf_simple(pdf_zakl, out)
    if os.path.isfile(odt):
        extract_odt(odt, os.path.join(EXTRACTED, "perepiska.txt"))


def write_readme():
    content = f"""# Анкета по киберустойchивoci — устранение замечаний

**Заказчик:** ОАО «АСБ Беларусбанк» · **Исполнитель:** ООО «ГС Ритейл» · **Договор:** {CONTRACT}  
**Проект:** {PROJECT}

Материалы по оценке киберустойchивoci подрядчика и устранению замечаний банка (оценка **26,5 балла — «неудовлетворительно»**).

## Структура

| Папка / файл | Содержание |
|--------------|------------|
| [incoming/](incoming/) | Исходники от банка (PDF, ODT) |
| [_extracted/](_extracted/) | Текст, извлечённый из исходников |
| [documents/](documents/) | Политики и регламенты ИБ (markdown) |
| [outgoing/](outgoing/) | Материалы для банка (markdown + docx) |
| [outgoing/docx/](outgoing/docx/) | Экспорт документов в Word |
| [plan-dorabotok.md](plan-dorabotok.md) | План мероприятий и статусы |
| [_template-dokumenta.md](_template-dokumenta.md) | Шаблон оформления |
| [export-to-word.ps1](export-to-word.ps1) | Экспорт markdown → docx |

## Контакт

Пономарев Андрей Викторович, технический директор · +375 29 6678873
"""
    # fix typo in киberустойchивoci -> proper
    content = content.replace("киberустойchивoci", "киberустойchивoci")
    content = content.replace("\u043a\u0438ber", "\u043a\u0438\u0431\u0435\u0440")  # won't work that way
    content = f"""# Анкета по киберустойчивости — устранение замечаний

**Заказчик:** ОАО «АСБ Беларусбанк» · **Исполнитель:** ООО «ГС Ритейл» · **Договор:** {CONTRACT}  
**Проект:** {PROJECT}

Материалы по оценке киберустойчивости подрядчика и устранению замечаний банка (оценка **26,5 балла — «неудовлетворительно»**).

## Структура

| Папка / файл | Содержание |
|--------------|------------|
| [incoming/](incoming/) | Исходники от банка (PDF, ODT) |
| [_extracted/](_extracted/) | Текст, извлечённый из исходников |
| [documents/](documents/) | Политики и регламенты ИБ (markdown) |
| [outgoing/](outgoing/) | Материалы для банка (markdown + docx) |
| [outgoing/docx/](outgoing/docx/) | Экспорт документов в Word |
| [plan-dorabotok.md](plan-dorabotok.md) | План мероприятий и статусы |
| [_template-dokumenta.md](_template-dokumenta.md) | Шаблон оформления |
| [export-to-word.ps1](export-to-word.ps1) | Экспорт markdown → docx |

## Контакт

Пономарев Андрей Викторович, технический директор · +375 29 6678873
"""
    with open(os.path.join(BASE, "README.md"), "w", encoding="utf-8") as f:
        f.write(content)


if __name__ == "__main__":
    ensure_dirs()
    reorganize_incoming()
    extract_all()
    write_readme()
    print("setup done")
