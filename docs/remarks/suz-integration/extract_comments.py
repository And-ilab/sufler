#!/usr/bin/env python3
"""Extract comments from TZ-Bitrix-RAG_MIX.docx"""

import shutil
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
W14 = "{http://schemas.microsoft.com/office/word/2010/wordml}"

SRC = Path(__file__).parent / "TZ-Bitrix-RAG_MIX.docx"
WORK = Path(__file__).parent / "_extracted"
OUT = Path(__file__).parent / "_comment_map.txt"


def text_of(el: ET.Element) -> str:
    parts: list[str] = []
    for t in el.iter(W + "t"):
        if t.text:
            parts.append(t.text)
        if t.tail:
            parts.append(t.tail)
    return "".join(parts).strip()


def find_context_for_comment(doc_xml: str, comment_id: str) -> str:
    root = ET.fromstring(doc_xml)
    context_parts: list[str] = []

    for p in root.iter(W + "p"):
        para_text_parts: list[str] = []
        in_range = False
        for child in p.iter():
            tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
            if tag == "commentRangeStart" and child.get(W + "id") == comment_id:
                in_range = True
            elif tag == "commentRangeEnd" and child.get(W + "id") == comment_id:
                in_range = False
            elif tag == "commentReference" and child.get(W + "id") == comment_id:
                in_range = True
            if tag == "t" and (in_range or child.text):
                if child.text:
                    para_text_parts.append(child.text)
                if child.tail and in_range:
                    para_text_parts.append(child.tail)
        if in_range or any(
            c.get(W + "id") == comment_id
            for c in p.iter()
            if c.tag.endswith("commentReference") or c.tag.endswith("commentRangeStart")
        ):
            txt = "".join(para_text_parts).strip() or text_of(p)
            if txt:
                context_parts.append(txt)

    return " | ".join(context_parts[:3]) if context_parts else ""


def main() -> None:
    if WORK.exists():
        shutil.rmtree(WORK)
    WORK.mkdir()

    with zipfile.ZipFile(SRC, "r") as z:
        z.extractall(WORK)

    comments_path = WORK / "word" / "comments.xml"
    doc_path = WORK / "word" / "document.xml"
    doc_xml = doc_path.read_text(encoding="utf-8")

    lines: list[str] = []
    if comments_path.exists():
        root = ET.parse(comments_path).getroot()
        for i, c in enumerate(
            sorted(root.findall(W + "comment"), key=lambda x: int(x.get(W + "id", "0"))),
            1,
        ):
            cid = c.get(W + "id", "")
            author = c.get(W + "author", "")
            date = c.get(W + "date", "")
            text = text_of(c)
            context = find_context_for_comment(doc_xml, cid)
            lines.append(f"=== COMMENT #{i} (id={cid}) ===")
            lines.append(f"Author: {author}")
            lines.append(f"Date: {date}")
            lines.append(f"Context: {context}")
            lines.append(f"Text: {text}")
            lines.append("")
    else:
        lines.append("No comments.xml found")

    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Written {OUT}")
    print(f"Comments: {len([l for l in lines if l.startswith('=== COMMENT')])}")


if __name__ == "__main__":
    main()
