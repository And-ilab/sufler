#!/usr/bin/env python3
"""Extract tracked changes (insertions/deletions) from Чат коррект.docx"""

import shutil
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
W14 = "{http://schemas.microsoft.com/office/word/2010/wordml}"

SRC = Path(__file__).parent / "Чат коррект.docx"
WORK = Path(__file__).parent / "_extracted"
OUT = Path(__file__).parent / "_tracked_changes.txt"


def text_of(el: ET.Element) -> str:
    parts: list[str] = []
    for t in el.iter(W + "t"):
        if t.text:
            parts.append(t.text)
        if t.tail:
            parts.append(t.tail)
    return "".join(parts).strip()


def para_context(p: ET.Element) -> str:
    return text_of(p)


def main() -> None:
    doc_path = WORK / "word" / "document.xml"
    if not doc_path.exists():
        if WORK.exists():
            shutil.rmtree(WORK)
        WORK.mkdir()
        with zipfile.ZipFile(SRC, "r") as z:
            z.extractall(WORK)

    root = ET.parse(doc_path).getroot()
    lines: list[str] = []
    change_num = 0

    for p in root.iter(W + "p"):
        ctx = para_context(p)
        if not ctx:
            continue

        for ins in p.findall(f".//{W}ins"):
            author = ins.get(W + "author", "?")
            text = text_of(ins)
            if text.strip():
                change_num += 1
                lines.append(f"=== INSERT #{change_num} (author: {author}) ===")
                lines.append(f"Context: {ctx[:300]}")
                lines.append(f"Inserted: {text}")
                lines.append("")

        for dele in p.findall(f".//{W}del"):
            author = dele.get(W + "author", "?")
            text = text_of(dele)
            if text.strip():
                change_num += 1
                lines.append(f"=== DELETE #{change_num} (author: {author}) ===")
                lines.append(f"Context: {ctx[:300]}")
                lines.append(f"Deleted: {text}")
                lines.append("")

    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Written {OUT}")
    print(f"Changes: {change_num}")


if __name__ == "__main__":
    main()
