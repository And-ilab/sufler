#!/usr/bin/env python3
"""Group tracked changes by paragraph context."""

import shutil
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
SRC = Path(__file__).parent / "Чат коррект.docx"
WORK = Path(__file__).parent / "_extracted"
OUT = Path(__file__).parent / "_remarks_grouped.txt"


def text_of(el: ET.Element) -> str:
    parts: list[str] = []
    for t in el.iter(W + "t"):
        if t.text:
            parts.append(t.text)
        if t.tail:
            parts.append(t.tail)
    return "".join(parts).strip()


def main() -> None:
    doc_path = WORK / "word" / "document.xml"
    if not doc_path.exists():
        WORK.mkdir(exist_ok=True)
        with zipfile.ZipFile(SRC, "r") as z:
            z.extractall(WORK)

    root = ET.parse(doc_path).getroot()
    lines: list[str] = []
    num = 0

    for p in root.iter(W + "p"):
        ins_texts: list[str] = []
        del_texts: list[str] = []
        author = ""

        for ins in p.findall(f".//{W}ins"):
            t = text_of(ins)
            if t:
                ins_texts.append(t)
                author = author or ins.get(W + "author", "")

        for dele in p.findall(f".//{W}del"):
            t = text_of(dele)
            if t:
                del_texts.append(t)
                author = author or dele.get(W + "author", "")

        if not ins_texts and not del_texts:
            continue

        num += 1
        base = text_of(p)
        # Remove inserted parts from base to get original context
        ctx = base
        lines.append(f"=== REMARK #{num} (author: {author}) ===")
        lines.append(f"Paragraph (with edits): {ctx}")
        if del_texts:
            lines.append(f"Deleted: {''.join(del_texts)}")
        if ins_texts:
            lines.append(f"Inserted: {''.join(ins_texts)}")
        lines.append("")

    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Written {OUT}, remarks: {num}")


if __name__ == "__main__":
    main()
