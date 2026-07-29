# -*- coding: utf-8 -*-
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

DOCX = Path(r"c:\Users\user\Desktop\TZ-unified-v1.3_75.docx")
OUT = Path(r"C:\Users\user\Desktop\sufler\sufler\_extracted\tz-v1.3-75-comments.txt")
OUT.parent.mkdir(parents=True, exist_ok=True)

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
W14 = "{http://schemas.microsoft.com/office/word/2010/wordml}"
W15 = "{http://schemas.microsoft.com/office/word/2012/wordml}"

def local(tag):
    return tag.split("}")[-1] if "}" in tag else tag

def text_of(elem):
    parts = []
    for t in elem.iter(W + "t"):
        if t.text:
            parts.append(t.text)
    return "".join(parts)

comments = {}
extended = {}
para_ids = {}

with zipfile.ZipFile(DOCX, "r") as z:
    names = set(z.namelist())

    if "word/comments.xml" not in names:
        raise SystemExit("No word/comments.xml in docx")

    croot = ET.fromstring(z.read("word/comments.xml"))
    for c in croot.findall(W + "comment"):
        cid = c.get(W + "id")
        author = c.get(W + "author", "")
        date = c.get(W + "date", "")
        initials = c.get(W + "initials", "")
        paras = []
        for p in c.findall(W + "p"):
            pt = text_of(p).strip()
            if pt:
                paras.append(pt)
        body_full = "\n".join(paras) if paras else text_of(c).strip()
        comments[cid] = {
            "id": cid,
            "author": author,
            "date": date,
            "initials": initials,
            "body": body_full,
        }
        for p in c.findall(W + "p"):
            pid = p.get(W14 + "paraId")
            if pid:
                para_ids[cid] = pid
                break

    if "word/commentsExtended.xml" in names:
        eroot = ET.fromstring(z.read("word/commentsExtended.xml"))
        for i, ce in enumerate(eroot):
            para_id = ce.get(W15 + "paraId") or ce.get("paraId")
            done = ce.get(W15 + "done") or ce.get("done")
            parent = ce.get(W15 + "paraIdParent") or ce.get("paraIdParent")
            # also scan attribs by local name
            for attr, val in ce.attrib.items():
                an = local(attr)
                if an == "paraId" and not para_id:
                    para_id = val
                elif an == "done" and done is None:
                    done = val
                elif an == "paraIdParent" and not parent:
                    parent = val
            extended[para_id or ("idx%d" % i)] = {
                "done": done,
                "parent": parent,
                "raw_tag": local(ce.tag),
            }

    doc = ET.fromstring(z.read("word/document.xml"))
    anchored = {cid: [] for cid in comments}
    active = set()
    for elem in doc.iter():
        tag = local(elem.tag)
        if tag == "commentRangeStart":
            cid = elem.get(W + "id")
            if cid is not None:
                active.add(cid)
        elif tag == "commentRangeEnd":
            cid = elem.get(W + "id")
            if cid is not None:
                active.discard(cid)
        elif tag == "t" and elem.text and active:
            for cid in list(active):
                if cid in anchored:
                    anchored[cid].append(elem.text)

reply_count = sum(1 for e in extended.values() if e.get("parent"))
done_count = sum(1 for e in extended.values() if str(e.get("done")) == "1")

lines = []
lines.append("Source: %s" % DOCX)
lines.append("Total comments in comments.xml: %d" % len(comments))
lines.append("commentsExtended entries: %d" % len(extended))
lines.append("Replies (have parent): %d" % reply_count)
lines.append("Marked done: %d" % done_count)
lines.append("=" * 80)
lines.append("")

def sort_key(cid):
    try:
        return (0, int(cid))
    except Exception:
        return (1, cid)

for n, cid in enumerate(sorted(comments.keys(), key=sort_key), 1):
    c = comments[cid]
    anchor = "".join(anchored.get(cid, [])).strip()
    anchor_short = anchor[:300] + ("..." if len(anchor) > 300 else "")
    pid = para_ids.get(cid)
    ext_info = ""
    if pid and pid in extended:
        e = extended[pid]
        parts = []
        if e.get("done") is not None:
            parts.append("done=%s" % e["done"])
        if e.get("parent"):
            parts.append("parentParaId=%s" % e["parent"])
        ext_info = ", ".join(parts)

    lines.append("--- Comment #%d (id=%s) ---" % (n, cid))
    lines.append("Author: %s" % c["author"])
    lines.append("Date:   %s" % c["date"])
    if c.get("initials"):
        lines.append("Initials: %s" % c["initials"])
    if pid:
        lines.append("paraId: %s" % pid)
    if ext_info:
        lines.append("Extended: %s" % ext_info)
    lines.append("Anchored text (%d chars):" % len(anchor))
    lines.append(anchor_short if anchor_short else "(no range text / point comment)")
    lines.append("Comment body:")
    lines.append(c["body"] if c["body"] else "(empty)")
    lines.append("")

text = "\n".join(lines) + "\n"
OUT.write_text(text, encoding="utf-8")
print("SUMMARY: %d comments extracted" % len(comments))
print("Replies (parent): %d; done: %d" % (reply_count, done_count))
print("Wrote: %s" % OUT)
print("Output size: %d chars, %d lines" % (len(text), len(lines)))
