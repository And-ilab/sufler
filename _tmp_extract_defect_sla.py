# -*- coding: utf-8 -*-
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET
from collections import defaultdict

docx = Path(r"c:\Users\user\Desktop\666\TZ-unified-v1.5 (МИХ).docx")
out = Path(r"C:\Users\user\Desktop\sufler\sufler\_tmp_defect_sla_comment.txt")

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}

def texts(el):
    return "".join(t.text or "" for t in el.iter(W + "t"))

with zipfile.ZipFile(docx) as z:
    names = z.namelist()
    comments_xml = z.read("word/comments.xml") if "word/comments.xml" in names else None
    doc_xml = z.read("word/document.xml")

comments = []
if comments_xml:
    root_c = ET.fromstring(comments_xml)
    for c in root_c.findall("w:comment", NS):
        comments.append({
            "id": c.get(W + "id"),
            "author": c.get(W + "author") or "",
            "date": c.get(W + "date") or "",
            "text": texts(c).strip(),
        })

root_d = ET.fromstring(doc_xml)
body = root_d.find("w:body", NS)
all_para_texts = []
comment_paras = defaultdict(list)
para_idx = -1
open_ranges = set()

def process_element(el):
    global para_idx
    if el.tag == W + "p":
        para_idx += 1
        ptext_parts = []
        starts, ends, refs = [], [], []
        in_range_at_start = set(open_ranges)
        for node in el.iter():
            if node is el:
                continue
            if node.tag == W + "commentRangeStart":
                cid = node.get(W + "id")
                open_ranges.add(cid)
                starts.append(cid)
            elif node.tag == W + "commentRangeEnd":
                ends.append(node.get(W + "id"))
            elif node.tag == W + "commentReference":
                refs.append(node.get(W + "id"))
            elif node.tag == W + "t" and node.text:
                ptext_parts.append(node.text)
            elif node.tag == W + "tab":
                ptext_parts.append("\t")
        ptext = "".join(ptext_parts)
        all_para_texts.append(ptext)
        related = in_range_at_start | set(starts) | set(refs) | set(ends)
        for cid in related:
            if para_idx not in comment_paras[cid]:
                comment_paras[cid].append(para_idx)
        for cid in ends:
            open_ranges.discard(cid)
    else:
        for child in list(el):
            if child.tag == W + "p":
                process_element(child)
            elif child.tag in (W + "tbl", W + "tr", W + "tc", W + "sdt", W + "sdtContent", W + "body"):
                process_element(child)
            elif any(True for _ in child.iter(W + "p")):
                process_element(child)

process_element(body)

phrases = [
    "устранения ошибок",
    "срок ввода",
    "Договором определен",
    "при приемке",
    "ошибки при",
]

matched = []
for c in comments:
    t = c["text"]
    hits = [p for p in phrases if p.lower() in t.lower()]
    if hits:
        matched.append((c, hits))

kw_accept = ["приемк", "приёмк", "acceptance"]
nearby_hits = []
for i, ptext in enumerate(all_para_texts):
    low = ptext.lower()
    if not ptext.strip():
        continue
    has_accept = any(k in low for k in kw_accept)
    if has_accept and any(k in low for k in ["устранен", "дефект", "замечан", "ошибк", "bug", "sla", "срок"]):
        nearby_hits.append((i, ptext))
    elif any(k in low for k in [
        "сроки устранения", "срок устранения", "устранения ошиб", "устранения дефект",
        "дефект", "замечан", "bugfix", "sla устранения", "устранения ошибок",
    ]):
        window = " ".join(all_para_texts[max(0, i - 5) : i + 6]).lower()
        if any(a in window for a in kw_accept):
            nearby_hits.append((i, ptext))

search_body = [
    "сроки устранения", "срок устранения", "дефект", "замечан",
    "bugfix", "sla устранения", "устранения ошибок",
]
body_phrase_hits = []
for i, ptext in enumerate(all_para_texts):
    low = ptext.lower()
    hits = [s for s in search_body if s.lower() in low]
    if hits and any(a in " ".join(all_para_texts[max(0, i - 8) : i + 9]).lower() for a in kw_accept):
        body_phrase_hits.append((i, hits, ptext))

# Also find comments mentioning SLA/defect fix near acceptance context
extra_comment_kw = [
    "сроки устранения", "срок устранения", "дефект", "замечан",
    "bugfix", "sla устранения", "sla", "устранения ошибок",
]
extra_matched = []
for c in comments:
    low = c["text"].lower()
    hits = [k for k in extra_comment_kw if k.lower() in low]
    if hits and c["id"] not in {m[0]["id"] for m in matched}:
        # include if context near acceptance OR comment itself about defects
        idxs = comment_paras.get(c["id"], [])
        ctx = " ".join(all_para_texts[j] for j in idxs).lower() if idxs else ""
        if any(a in ctx for a in kw_accept) or any(k in low for k in ["устранен", "дефект", "замечан", "bugfix", "sla"]):
            extra_matched.append((c, hits))

lines = []
lines.append("=== MATCHING COMMENTS (phrases) ===")
lines.append(f"Source: {docx}")
lines.append(f"Total comments in doc: {len(comments)}")
lines.append(f"Matched: {len(matched)}")
lines.append("")

for c, hits in matched:
    lines.append("-" * 60)
    lines.append(f"ID: {c['id']}")
    lines.append(f"Author: {c['author']}")
    lines.append(f"Date: {c['date']}")
    lines.append(f"Matched phrases: {hits}")
    lines.append("Full text:")
    lines.append(c["text"])
    idxs = comment_paras.get(c["id"], [])
    lines.append(f"REF/context paragraph indices: {idxs}")
    if idxs:
        for pi in sorted(set(idxs)):
            for j in range(max(0, pi - 1), min(len(all_para_texts), pi + 2)):
                t = all_para_texts[j].strip()
                if t:
                    mark = ">>>" if j == pi else "   "
                    lines.append(f"{mark} [{j}] {t}")
    else:
        lines.append("(no paragraph context found)")
    lines.append("")

lines.append("")
lines.append("=== RELATED COMMENTS (defect/SLA/remark keywords) ===")
lines.append(f"Extra matched: {len(extra_matched)}")
for c, hits in extra_matched:
    lines.append("-" * 60)
    lines.append(f"ID: {c['id']}")
    lines.append(f"Author: {c['author']}")
    lines.append(f"Matched: {hits}")
    lines.append(c["text"])
    idxs = comment_paras.get(c["id"], [])
    if idxs:
        for pi in sorted(set(idxs))[:5]:
            t = all_para_texts[pi].strip()
            if t:
                lines.append(f">>> [{pi}] {t}")
    lines.append("")

lines.append("")
lines.append("=== NEARBY TZ TEXT (acceptance + defect/fix deadlines) ===")
seen = set()
for i, ptext in nearby_hits:
    if i in seen:
        continue
    seen.add(i)
    lines.append(f"[{i}] {ptext.strip()}")

lines.append("")
lines.append("=== BODY PHRASE HITS NEAR ACCEPTANCE ===")
seen2 = set()
for i, hits, ptext in body_phrase_hits:
    key = (i, ptext[:80])
    if key in seen2:
        continue
    seen2.add(key)
    lines.append(f"[{i}] hits={hits}")
    lines.append(ptext.strip())
    lines.append("--- context ---")
    for j in range(max(0, i - 2), min(len(all_para_texts), i + 3)):
        t = all_para_texts[j].strip()
        if t:
            mark = ">>>" if j == i else "   "
            lines.append(f"{mark} [{j}] {t}")
    lines.append("")

text_out = "\n".join(lines)
out.write_text(text_out, encoding="utf-8")
print(text_out)
print(f"\n\nWrote {out} ({len(text_out)} chars)")
