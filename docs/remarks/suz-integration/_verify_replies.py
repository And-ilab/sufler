"""Verify executor replies for parent comment ids 33-35."""
from __future__ import annotations

import subprocess
import sys
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SCRIPT = ROOT / "add_comment_replies.py"
DOCX = ROOT / "TZ-Bitrix-RAG +-ответы-исполнителя.docx"
LOG = ROOT / "_verify_replies.log"

NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "w15": "http://schemas.microsoft.com/office/word/2012/wordml",
    "w14": "http://schemas.microsoft.com/office/word/2010/wordml",
}


def main() -> int:
    lines: list[str] = []
    proc = subprocess.run(
        [sys.executable, str(SCRIPT)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    lines.append(f"script_exit={proc.returncode}")
    lines.append(f"script_stdout={proc.stdout.strip()!r}")
    lines.append(f"script_stderr={proc.stderr.strip()!r}")

    if not DOCX.exists():
        lines.append("docx_missing=1")
        LOG.write_text("\n".join(lines), encoding="utf-8")
        return 1

    with zipfile.ZipFile(DOCX) as zf:
        comments_xml = zf.read("word/comments.xml")
        ext_xml = zf.read("word/commentsExtended.xml")

    root = ET.fromstring(comments_xml)
    ext = ET.fromstring(ext_xml)

    by_paraid: dict[str, dict[str, str]] = {}
    for cm in root.findall("w:comment", NS):
        cid = cm.get(f"{{{NS['w']}}}id", "")
        author = cm.get(f"{{{NS['w']}}}author", "")
        text = " ".join((t.text or "") for t in cm.findall(".//w:t", NS)).strip()
        pnode = cm.find("w:p", NS)
        paraid = pnode.get(f"{{{NS['w14']}}}paraId") if pnode is not None else ""
        by_paraid[paraid] = {"id": cid, "author": author, "text": text}

    parent_para: dict[str, str] = {}
    for cm in root.findall("w:comment", NS):
        cid = cm.get(f"{{{NS['w']}}}id", "")
        pnode = cm.find("w:p", NS)
        paraid = pnode.get(f"{{{NS['w14']}}}paraId") if pnode is not None else ""
        parent_para[cid] = paraid

    child_by_parent: dict[str, list[str]] = {}
    for ex in ext.findall("w15:commentEx", NS):
        child = ex.get(f"{{{NS['w15']}}}paraId", "")
        parent = ex.get(f"{{{NS['w15']}}}paraIdParent", "")
        if parent:
            child_by_parent.setdefault(parent, []).append(child)

    for parent_id in ("33", "34", "35"):
        lines.append(f"=== parent {parent_id} ===")
        parent_paraid = parent_para.get(parent_id, "")
        children = child_by_parent.get(parent_paraid, [])
        ponomarev = [
            by_paraid[c]
            for c in children
            if by_paraid.get(c, {}).get("author") == "Андрей Пономарев"
        ]
        lines.append(f"reply_count={len(ponomarev)}")
        for reply in ponomarev:
            text = reply["text"]
            lines.append(f"reply_id={reply['id']}")
            lines.append(f"starts_da_ispolzuetsya={text.startswith('Да, используется')}")
            lines.append(f"first_120={text[:120]}")

    LOG.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
