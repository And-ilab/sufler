#!/usr/bin/env python3
"""Extract text and comments from meeting-protocol docx files."""

import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

FILES = [
    Path("docs/sources/meeting-protocols/02 07 26 Онлайн чат/TZ-unified-v1.3.docx чат.docx"),
    Path("docs/sources/meeting-protocols/02 07 26 Онлайн чат/Протокол встречи по Модулю онлайн чат 02 07 26.docx"),
    Path("docs/sources/meeting-protocols/06 07 26 Суфлер и общие вопросы по ТЗ/TZ-unified-v1.3_МИХ.docx"),
    Path(
        "docs/sources/meeting-protocols/06 07 26 Суфлер и общие вопросы по ТЗ/"
        "ПРОТОКОЛ ВСТРЕЧИ по Модулю Суфлер и по Общим вопросам по ТЗ.docx"
    ),
]

FALLBACK_REGEX = True
OUT_DIR = Path("_extracted")


def text_of(el: ET.Element) -> str:
    parts: list[str] = []
    for t in el.iter(W + "t"):
        if t.text:
            parts.append(t.text)
        if t.tail:
            parts.append(t.tail)
    return "".join(parts).strip()


def extract_docx_regex(path: Path) -> dict:
    import re

    out: dict = {"paragraphs": [], "comments": []}
    with zipfile.ZipFile(path) as z:
        if "word/document.xml" in z.namelist():
            xml = z.read("word/document.xml").decode("utf-8", errors="replace")
            texts = re.findall(r"<w:t[^>]*>([^<]*)</w:t>", xml)
            out["paragraphs"] = [t for t in texts if t.strip()]
        if "word/comments.xml" in z.namelist():
            cxml = z.read("word/comments.xml").decode("utf-8", errors="replace")
            for block in re.findall(r"<w:comment\b.*?</w:comment>", cxml, re.S):
                cid = re.search(r'w:id="(\d+)"', block)
                author = re.search(r'w:author="([^"]*)"', block)
                date = re.search(r'w:date="([^"]*)"', block)
                texts = re.findall(r"<w:t[^>]*>([^<]*)</w:t>", block)
                txt = "".join(texts).strip()
                if txt:
                    out["comments"].append(
                        {
                            "id": cid.group(1) if cid else "",
                            "author": author.group(1) if author else "",
                            "date": date.group(1) if date else "",
                            "text": txt,
                        }
                    )
    return out


def extract_docx(path: Path) -> dict:
    out = {"paragraphs": [], "comments": []}
    try:
        with zipfile.ZipFile(path) as z:
            if "word/document.xml" in z.namelist():
                root = ET.fromstring(z.read("word/document.xml"))
                for p in root.iter(W + "p"):
                    txt = text_of(p)
                    if txt:
                        out["paragraphs"].append(txt)
            if "word/comments.xml" in z.namelist():
                root = ET.fromstring(z.read("word/comments.xml"))
                for c in root.iter(W + "comment"):
                    cid = c.get(W + "id", "")
                    author = c.get(W + "author", "")
                    date = c.get(W + "date", "")
                    txt = text_of(c)
                    if txt:
                        out["comments"].append(
                            {"id": cid, "author": author, "date": date, "text": txt}
                        )
    except ET.ParseError:
        if FALLBACK_REGEX:
            return extract_docx_regex(path)
        raise
    return out


def main() -> None:
    base = Path(__file__).parent
    OUT_DIR.mkdir(exist_ok=True)
    for rel in FILES:
        path = base / rel
        data = extract_docx(path)
        out_path = OUT_DIR / f"{path.stem}.txt"
        lines = [
            f"FILE: {path.name}",
            f"PARAGRAPHS: {len(data['paragraphs'])}",
            f"COMMENTS: {len(data['comments'])}",
            "=" * 80,
            "",
        ]
        if data["comments"]:
            lines.append("=== COMMENTS ===")
            for c in data["comments"]:
                lines.append(
                    f"[{c['id']}] {c['author']} ({c['date']}): {c['text']}"
                )
            lines.append("")
        lines.append("=== DOCUMENT TEXT ===")
        lines.extend(data["paragraphs"])
        out_path.write_text("\n".join(lines), encoding="utf-8")
        print(
            f"{path.name}: {len(data['paragraphs'])} paras, "
            f"{len(data['comments'])} comments -> {out_path}"
        )


if __name__ == "__main__":
    main()
