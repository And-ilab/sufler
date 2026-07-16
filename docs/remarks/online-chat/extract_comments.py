#!/usr/bin/env python3
"""Extract comments and context from Чат коррект.docx"""

import re
import shutil
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
W14 = "{http://schemas.microsoft.com/office/word/2010/wordml}"

SRC = Path(__file__).parent / "Чат коррект.docx"
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


def extract_paragraphs(doc_xml: str) -> list[tuple[str, str]]:
    """Return list of (para_id, text) from document."""
    root = ET.fromstring(doc_xml)
    result: list[tuple[str, str]] = []
    for p in root.iter(W + "p"):
        para_id = p.get(W14 + "paraId", "")
        txt = text_of(p)
        if txt:
            result.append((para_id, txt))
    return result


def find_context_for_comment(doc_xml: str, comment_id: str) -> str:
    """Find text near comment markers in document."""
    root = ET.fromstring(doc_xml)
    context_parts: list[str] = []

    for p in root.iter(W + "p"):
        para_text_parts: list[str] = []
        in_range = False
        for child in p.iter():
            tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
            if tag == "commentRangeStart":
                if child.get(W + "id") == comment_id:
                    in_range = True
            elif tag == "commentRangeEnd":
                if child.get(W + "id") == comment_id:
                    in_range = False
            elif tag == "commentReference":
                if child.get(W + "id") == comment_id:
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
    comments_xml = comments_path.read_text(encoding="utf-8") if comments_path.exists() else ""

    lines: list[str] = []
    if comments_path.exists():
        root = ET.parse(comments_path).getroot()
        for c in sorted(root.findall(W + "comment"), key=lambda x: int(x.get(W + "id", "0"))):
            cid = c.get(W + "id", "")
            author = c.get(W + "author", "")
            date = c.get(W + "date", "")
            text = text_of(c)
            context = find_context_for_comment(doc_xml, cid)
            lines.append(f"=== COMMENT #{cid} ===")
            lines.append(f"Author: {author}")
            lines.append(f"Date: {date}")
            lines.append(f"Context: {context}")
            lines.append(f"Text: {text}")
            lines.append("")
    else:
        lines.append("No comments.xml found")

    # Also dump tracked changes / revisions if any
    rev_count = doc_xml.count("w:ins") + doc_xml.count("w:del")
    lines.append(f"Revision markers in document: {rev_count}")

    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Written {OUT}")
    print(f"Comments found: {len([l for l in lines if l.startswith('=== COMMENT')])}")


if __name__ == "__main__":
    main()
