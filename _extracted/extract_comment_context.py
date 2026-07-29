# -*- coding: utf-8 -*-
"""Pull customer comments + Nikita replies for risky IDs, with nearby document text if possible."""
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
W14 = "{http://schemas.microsoft.com/office/word/2010/wordml}"
W15 = "{http://schemas.microsoft.com/office/word/2012/wordml}"

desk = Path(r"C:\Users\user\Desktop")
docx = next(f for f in desk.glob("TZ-unified-v1.4*.docx") if "(1)" in f.name)


def text_of(el: ET.Element) -> str:
    parts = []
    for p in el.findall(W + "p"):
        t = "".join((x.text or "") + (x.tail or "") for x in p.iter(W + "t")).strip()
        if t:
            parts.append(t)
    return "\n".join(parts)


with zipfile.ZipFile(docx) as z:
    root = ET.fromstring(z.read("word/comments.xml"))
    comments = {}
    cid_to_para = {}
    for c in root.findall(W + "comment"):
        cid = int(c.get(W + "id"))
        comments[cid] = {
            "author": c.get(W + "author", ""),
            "body": text_of(c),
        }
        for p in c.findall(W + "p"):
            if W14 + "paraId" in p.attrib:
                cid_to_para[cid] = p.get(W14 + "paraId")
                break
    para_to_cid = {v: k for k, v in cid_to_para.items()}
    parent = {}
    if "word/commentsExtended.xml" in z.namelist():
        ex = ET.fromstring(z.read("word/commentsExtended.xml"))
        for ce in ex.findall(W15 + "commentEx"):
            para = ce.get(W15 + "paraId")
            par = ce.get(W15 + "paraIdParent")
            cid = para_to_cid.get(para)
            if cid is None or not par:
                continue
            pc = para_to_cid.get(par)
            if pc is not None:
                parent[cid] = pc

# focus IDs
focus = {9, 20, 144, 161, 162, 180, 189, 196, 280, 192, 194, 200, 7, 5, 143, 177}
# also any without reply that are important
lines = []
for cid in sorted(comments):
    if cid in parent:
        continue
    kids = [k for k, v in parent.items() if v == cid]
    body = comments[cid]["body"]
    interesting = (
        cid in focus
        or "SUF-T" in body
        or "пошагов" in body.lower()
        or "ПМИ" in body
        or "копир" in body.lower()
        or "webhook" in body.lower()
        or "две минут" in body.lower()
        or "2 мин" in body
        or "настраива" in body.lower()
        or "виджет" in body.lower() and "сторон" in body.lower()
    )
    if not interesting and not kids:
        continue
    if not interesting and kids:
        # only include if reply looks weak
        weak = False
        for k in kids:
            b = comments[k]["body"].strip()
            if len(b) < 40 or b.lower() in {"принято", "принято.", "исправил", "добавил"}:
                weak = True
        if not weak:
            continue
    lines.append(f"=== ID={cid} [{comments[cid]['author']}]")
    lines.append(body)
    for k in kids:
        lines.append(f"  REPLY#{k} [{comments[k]['author']}]: {comments[k]['body']}")
    lines.append("")

out = Path(r"C:\Users\user\Desktop\sufler\sufler\_extracted\risky-replies.txt")
out.write_text("\n".join(lines), encoding="utf-8")
print("wrote", out, "blocks", lines.count("==="))
