# -*- coding: utf-8 -*-
import zipfile
import re
import sys
from xml.etree import ElementTree as ET
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

docx = Path(r"c:\Users\user\Desktop\666") / [p.name for p in Path(r"c:\Users\user\Desktop\666").glob("TZ-unified-v1.5*.docx") if not p.name.startswith("~$")][0]

NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

def local(tag):
    return tag.split("}")[-1] if "}" in tag else tag

def para_text(p):
    parts = []
    for t in p.iter(W + "t"):
        if t.text:
            parts.append(t.text)
        if t.tail:
            parts.append(t.tail)
    return "".join(parts)

KEYWORDS = [
    "огранич",
    "не будет ограничиваться",
    "перечнем критериев",
    "всег функционала",
    "всего функционала",
    "приемка должна",
]

def matches_kw(text):
    tl = text.lower()
    return [k for k in KEYWORDS if k.lower() in tl]

out_lines = []
def log(s=""):
    out_lines.append(s)

with zipfile.ZipFile(docx, "r") as z:
    comments_xml = z.read("word/comments.xml")
    document_xml = z.read("word/document.xml")

comments_root = ET.fromstring(comments_xml)
doc_root = ET.fromstring(document_xml)

comments = {}
for c in comments_root.findall("w:comment", NS):
    cid = c.get(W + "id")
    author = c.get(W + "author")
    date = c.get(W + "date")
    texts = []
    for p in c.findall("w:p", NS):
        t = para_text(p)
        if t.strip():
            texts.append(t)
    comments[cid] = {"author": author, "date": date, "text": "\n".join(texts)}

body = doc_root.find("w:body", NS)
paras = list(body.iter(W + "p"))

comment_para_idxs = {cid: [] for cid in comments}
for i, p in enumerate(paras):
    for el in p.iter():
        tag = local(el.tag)
        if tag in ("commentRangeStart", "commentRangeEnd", "commentReference"):
            cid = el.get(W + "id")
            if cid in comment_para_idxs and i not in comment_para_idxs[cid]:
                comment_para_idxs[cid].append(i)

def extract_range_text(cid):
    collecting = False
    parts = []
    for el in body.iter():
        tag = local(el.tag)
        if tag == "commentRangeStart" and el.get(W + "id") == cid:
            collecting = True
            continue
        if tag == "commentRangeEnd" and el.get(W + "id") == cid:
            collecting = False
            continue
        if collecting and tag == "t" and el.text:
            parts.append(el.text)
    return "".join(parts)

log("=" * 80)
log("MATCHING COMMENTS")
log("File: " + str(docx))
log("=" * 80)

matched = []
for cid, info in comments.items():
    hits = matches_kw(info["text"])
    if hits:
        matched.append((cid, info, hits))

log(f"Total comments: {len(comments)}")
log(f"Matching comments: {len(matched)}")
log("")

for cid, info, hits in matched:
    log("-" * 80)
    log(f"Comment ID: {cid}")
    log(f"Author: {info['author']}")
    log(f"Date: {info['date']}")
    log(f"Matched keywords: {hits}")
    log("Full text:")
    log(info["text"])
    idxs = sorted(set(comment_para_idxs.get(cid, [])))
    ref = extract_range_text(cid)
    log(f"REF (anchored range text): {ref}")
    if idxs:
        start = max(0, min(idxs) - 5)
        end = min(len(paras), max(idxs) + 6)
        log(f"Surrounding paragraphs (indices {start}-{end-1}, anchors {idxs}):")
        for j in range(start, end):
            pt = para_text(paras[j]).strip()
            marker = ">>>" if j in idxs else "   "
            if pt or j in idxs:
                log(f"{marker} [{j}] {pt}")
    else:
        log("No paragraph anchor found for this comment.")
    log("")

log("=" * 80)
log("PARAGRAPHS containing 'огранич' near II.7 or приемк")
log("=" * 80)

ogranich_idxs = []
for i, p in enumerate(paras):
    t = para_text(p)
    if "огранич" in t.lower():
        ogranich_idxs.append(i)

log(f"Paragraphs with 'огранич': {len(ogranich_idxs)}")

def near_ii7_or_priem(i, window=25):
    lo, hi = max(0, i - window), min(len(paras), i + window + 1)
    hits = []
    for j in range(lo, hi):
        t = para_text(paras[j])
        tl = t.lower()
        if re.search(r"(?i)ii\.?\s*7\b", t) or "ii.7" in tl:
            hits.append((j, "II.7"))
        if "приемк" in tl:
            hits.append((j, "приемк"))
    return hits

shown = 0
for i in ogranich_idxs:
    near = near_ii7_or_priem(i)
    if near:
        shown += 1
        kinds = ", ".join(f"{k}@{j}" for j, k in near[:5])
        log("-" * 80)
        log(f"Para [{i}] near: {kinds}")
        start = max(0, i - 5)
        end = min(len(paras), i + 6)
        near_idxs = {j for j, _ in near}
        for j in range(start, end):
            pt = para_text(paras[j]).strip()
            if j == i:
                marker = ">>>"
            elif j in near_idxs:
                marker = "***"
            else:
                marker = "   "
            if pt:
                log(f"{marker} [{j}] {pt}")
        log("")

if shown == 0:
    log("No 'огранич' paragraphs found near II.7 or приемк within window=25.")
    log("Dumping all 'огранич' paragraphs with short context:")
    for i in ogranich_idxs:
        log("-" * 80)
        log(f"Para [{i}]")
        start = max(0, i - 3)
        end = min(len(paras), i + 4)
        for j in range(start, end):
            pt = para_text(paras[j]).strip()
            marker = ">>>" if j == i else "   "
            if pt:
                log(f"{marker} [{j}] {pt[:500]}")
        log("")
else:
    log(f"Shown {shown} 'огранич' paragraphs near II.7/приемк.")

# Also dump II.7 section header area briefly if no ограничен nearby in section
log("")
log("=" * 80)
log("II.7 section scan (paras matching II.7 heading + nearby 'огранич'/'приемк')")
log("=" * 80)
ii7_idxs = [i for i, p in enumerate(paras) if re.search(r"(?i)\bII\.?\s*7\b", para_text(p))]
log(f"II.7-like paragraphs: {ii7_idxs[:20]}")
for i in ii7_idxs[:10]:
    t = para_text(paras[i]).strip()
    log(f"  [{i}] {t[:200]}")

out_path = Path(r"C:\Users\user\Desktop\sufler\sufler\_tmp_accept_limit_comment.txt")
text = "\n".join(out_lines) + "\n"
out_path.write_text(text, encoding="utf-8")
print(text)
print("WROTE", out_path, "bytes", out_path.stat().st_size)