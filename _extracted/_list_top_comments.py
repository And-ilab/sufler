# -*- coding: utf-8 -*-
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

desktop = Path(r"c:\Users\user\Desktop")
docx = next(desktop.glob("TZ-unified-v1.4*.docx"))
out = Path(r"C:\Users\user\Desktop\sufler\sufler\_extracted\tz-v1.4-top-comments.txt")

NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "w15": "http://schemas.microsoft.com/office/word/2012/wordml",
}
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
W15 = "{http://schemas.microsoft.com/office/word/2012/wordml}"
W14 = "{http://schemas.microsoft.com/office/word/2010/wordml}"


def text_of(el):
    parts = []
    for t in el.iter(W + "t"):
        if t.text:
            parts.append(t.text)
        if t.tail:
            parts.append(t.tail)
    return "".join(parts).strip()


with zipfile.ZipFile(docx) as z:
    root = ET.fromstring(z.read("word/comments.xml"))
    comments = {}
    cid_to_para = {}
    for c in root.findall("w:comment", NS):
        cid = int(c.get(W + "id"))
        author = c.get(W + "author", "")
        date = c.get(W + "date", "")
        paras = []
        for p in c.findall("w:p", NS):
            t = text_of(p)
            if t:
                paras.append(t)
            if W14 + "paraId" in p.attrib:
                cid_to_para[cid] = p.get(W14 + "paraId")
        comments[cid] = {
            "author": author,
            "date": date,
            "body": "\n".join(paras).strip(),
        }
    para_to_cid = {v: k for k, v in cid_to_para.items()}
    parent = {}
    ex = ET.fromstring(z.read("word/commentsExtended.xml"))
    for ce in ex.findall("w15:commentEx", NS):
        para = ce.get(W15 + "paraId")
        par = ce.get(W15 + "paraIdParent")
        cid = para_to_cid.get(para)
        if cid is None:
            continue
        if par:
            pc = para_to_cid.get(par)
            if pc is not None:
                parent[cid] = pc

    doc = ET.fromstring(z.read("word/document.xml"))
    anchored = {}
    active = {}
    for el in doc.iter():
        if el.tag == W + "commentRangeStart":
            active[el.get(W + "id")] = []
        elif el.tag == W + "commentRangeEnd":
            cid = el.get(W + "id")
            if cid in active:
                anchored[cid] = "".join(active.pop(cid)).strip()
        elif el.tag == W + "t" and active and el.text:
            for cid in list(active):
                active[cid].append(el.text)

reply_of = set(parent.keys())
top = [cid for cid in sorted(comments) if cid not in reply_of]

lines = [f"TOP_COUNT: {len(top)}", ""]
n = 0
for cid in top:
    n += 1
    c = comments[cid]
    kids = [k for k, v in parent.items() if v == cid]
    kids_txt = ""
    if kids:
        replies = []
        for k in kids:
            replies.append(f"  REPLY#{k} [{comments[k]['author']}]: {comments[k]['body']}")
        kids_txt = "\n" + "\n".join(replies)
    lines.append(f"=== N{n} ID={cid} [{c['author']}] {c['date']}")
    lines.append(f"ANCHOR: {anchored.get(str(cid), '')[:400]}")
    lines.append(c["body"])
    if kids_txt:
        lines.append(kids_txt)
    lines.append("")

out.write_text("\n".join(lines), encoding="utf-8")
print(f"wrote {out} top={len(top)}")
