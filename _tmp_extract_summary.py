# -*- coding: utf-8 -*-
import zipfile, re
from xml.etree import ElementTree as ET
from pathlib import Path

cands = list(Path(r"c:\Users\user\Desktop\666").glob("TZ-unified-v1.5*.docx"))
src = cands[0]
out = Path(r"C:\Users\user\Desktop\sufler\sufler\_tmp_summary_accept.txt")
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

with zipfile.ZipFile(src) as z:
    comments_xml = z.read("word/comments.xml")
    doc_xml = z.read("word/document.xml")

def para_text(p):
    parts = []
    for t in p.iter(W + "t"):
        if t.text: parts.append(t.text)
        if t.tail: parts.append(t.tail)
    return "".join(parts)

ctree = ET.fromstring(comments_xml)
comments = {}
for c in ctree.findall(W + "comment"):
    cid = c.get(W + "id")
    texts = []
    for t in c.iter(W + "t"):
        if t.text: texts.append(t.text)
        if t.tail: texts.append(t.tail)
    comments[cid] = {
        "author": c.get(W + "author") or "",
        "date": c.get(W + "date") or "",
        "text": "".join(texts),
    }

root = ET.fromstring(doc_xml)
paras = []
for p in root.iter(W + "p"):
    text = para_text(p)
    starts, ends, refs = [], [], []
    for el in p.iter():
        if el.tag == W + "commentRangeStart":
            starts.append(el.get(W + "id"))
        elif el.tag == W + "commentRangeEnd":
            ends.append(el.get(W + "id"))
        elif el.tag == W + "commentReference":
            refs.append(el.get(W + "id"))
    paras.append({"text": text, "starts": starts, "ends": ends, "refs": refs})

# Map every comment id to para indices that contain any marker
cid_to_idxs = {}
open_ranges = set()
for i, p in enumerate(paras):
    for cid in p["starts"]:
        open_ranges.add(cid)
        cid_to_idxs.setdefault(cid, set()).add(i)
    for cid in list(open_ranges):
        cid_to_idxs.setdefault(cid, set()).add(i)
    for cid in p["ends"]:
        open_ranges.discard(cid)
        cid_to_idxs.setdefault(cid, set()).add(i)
    for cid in p["refs"]:
        cid_to_idxs.setdefault(cid, set()).add(i)

# For comments with empty text in marked paras, expand neighbors
def context_for(cid, radius=3):
    idxs = sorted(cid_to_idxs.get(cid, []))
    if not idxs:
        return []
    lo = max(0, min(idxs) - radius)
    hi = min(len(paras) - 1, max(idxs) + radius)
    outp = []
    for i in range(lo, hi + 1):
        t = paras[i]["text"].strip()
        if t:
            mark = " *" if i in idxs else ""
            outp.append((i, t, mark))
    return outp

keys_re = re.compile(r"summary|саммар", re.I)
summary_comments = [(cid, c) for cid, c in comments.items() if keys_re.search(c["text"])]

summary_word = re.compile(r"Summary|саммар", re.I)
lines = [(i, p["text"]) for i, p in enumerate(paras)]

# Find real section heading 4.3.1.13
sec_43113 = []
for i, t in lines:
    ts = t.strip()
    if re.search(r"4\.3\.1\.13\b", ts) and len(ts) < 200:
        sec_43113.append(i)
    if re.match(r"^4\.3\.1\.13\b", ts) or re.match(r"^§?\s*4\.3\.1\.13\b", ts):
        sec_43113.append(i)

# Also FR-SUF-15, FR-CHAT-07 headings
fr_ids = []
for i, t in lines:
    ts = t.strip()
    if re.search(r"\b(FR-SUF-15|FR-CHAT-07|FR-RPT-CC-15|4\.3\.1\.13|4\.3\.1\.14|4\.3\.2\.11)\b", ts):
        if len(ts) < 250 or summary_word.search(ts):
            fr_ids.append((i, ts[:300]))

# Dump body of 4.3.1.13: find best start
def dump_from_heading(pred, max_paras=100):
    starts = [i for i, t in lines if pred(t.strip())]
    blocks = []
    for st in starts:
        block = []
        for j in range(st, min(st + max_paras, len(lines))):
            jt = lines[j][1].strip()
            if not jt:
                continue
            # stop at next same-level numbered section
            if j > st and re.match(r"^4\.\d+\.\d+\.\d+", jt) and not pred(jt):
                break
            if j > st and re.match(r"^4\.\d+\.\d+\s", jt) and len(jt) < 120:
                # higher level
                if not re.match(r"^4\.3\.1\.1", jt):
                    pass
            block.append((j, jt))
        blocks.append(block)
    return blocks

blocks_43113 = dump_from_heading(
    lambda ts: bool(re.match(r"^4\.3\.1\.13\b", ts) or re.search(r"^4\.3\.1\.13\s", ts)),
    80,
)
# looser
if not blocks_43113:
    blocks_43113 = dump_from_heading(
        lambda ts: ("4.3.1.13" in ts and summary_word.search(ts) and len(ts) < 180),
        80,
    )

# CHAT-T-13 and SUF-T related acceptance
chat_t13 = dump_from_heading(lambda ts: bool(re.search(r"\bCHAT-T-13\b", ts)), 60)
suf_t_sum = []
for i, t in lines:
    if summary_word.search(t) and re.search(r"\bSUF-T-\d+", t):
        suf_t_sum.append((i, t.strip()[:500]))

# II.7 detailed scenarios table area around p3000 and acceptance around chat
# Find paragraphs that are CHAT-T-13 scenario steps
chat_accept = []
for i, t in lines:
    if re.search(r"\bCHAT-T-13\b", t):
        for j in range(max(0, i - 2), min(len(lines), i + 40)):
            jt = lines[j][1].strip()
            if jt:
                chat_accept.append((j, jt[:600]))
        chat_accept.append((-1, "---"))

# Acceptance criteria containing Summary near II.7 table
ii7_sum_paras = []
for i, t in lines:
    if not summary_word.search(t):
        continue
    # look back 40 for SUF-T-/CHAT-T-
    back = " ".join(lines[j][1] for j in range(max(0, i - 40), i + 1))
    tags = []
    m1 = re.findall(r"\bSUF-T-\d+\b", back)
    m2 = re.findall(r"\bCHAT-T-\d+\b", back)
    if m1:
        tags.append("near " + ",".join(m1[-3:]))
    if m2:
        tags.append("near " + ",".join(m2[-3:]))
    if re.search(r"(II|ІІ)\.?\s*7", back) or tags:
        ii7_sum_paras.append((i, tags, t.strip()[:700]))

# Build final dump
L = []
def w(s=""):
    L.append(s)

w("=" * 80)
w("DUMP: Summary / саммар / саммариз from TZ-unified-v1.5")
w("Source: " + str(src))
w("=" * 80)

w()
w("## 1) COMMENTS containing Summary / саммар")
w("Count: %d" % len(summary_comments))
for cid, c in summary_comments:
    w("-" * 60)
    w("ID: " + cid)
    w("AUTHOR: " + c["author"])
    w("DATE: " + c["date"])
    w("TEXT: " + c["text"])
    w("REF/CONTEXT:")
    ctx = context_for(cid, 4)
    if not ctx:
        w("  (no markers in document — orphan comment?)")
    else:
        for i, t, mark in ctx:
            w("  [p%d%s] %s" % (i, mark, t[:700]))

w()
w("## 2) II.7 / SUF-T / CHAT-T paragraphs mentioning Summary/саммар")
w("Hits with nearby SUF-T-*/CHAT-T-* IDs: %d" % len(ii7_sum_paras))
for i, tags, t in ii7_sum_paras:
    w("  [p%d] %s" % (i, tags))
    w("    %s" % t)

w()
w("SUF-T-* lines that also mention Summary:")
if not suf_t_sum:
    w("  (none — no single paragraph contains both SUF-T-NN and Summary)")
else:
    for i, t in suf_t_sum:
        w("  [p%d] %s" % (i, t))

w()
w("CHAT-T-13 blocks:")
for bi, block in enumerate(chat_t13):
    w("--- CHAT-T-13 block %d ---" % (bi + 1))
    for j, t in block[:50]:
        w("  [p%d] %s" % (j, t[:600]))

w()
w("## 3) FR/UC about Summary + acceptance scenario texts")
w("FR/section index hits (id lines):")
for i, t in fr_ids[:80]:
    w("  [p%d] %s" % (i, t))

w()
w("### §4.3.1.13 body dumps")
if not blocks_43113:
    w("(no dedicated heading match; searching body containing '4.3.1.13' + Summary title patterns)")
    # find paragraphs that look like the requirement definition
    for i, t in lines:
        ts = t.strip()
        if re.search(r"4\.3\.1\.13", ts) and (summary_word.search(ts) or "истори" in ts.lower()):
            w("  [p%d] %s" % (i, ts[:500]))
            for j in range(i + 1, min(i + 50, len(lines))):
                jt = lines[j][1].strip()
                if not jt:
                    continue
                if re.match(r"^4\.\d+\.\d+\.\d+", jt):
                    break
                w("  [p%d] %s" % (j, jt[:500]))
            w("---")
else:
    for bi, block in enumerate(blocks_43113):
        w("--- 4.3.1.13 block %d ---" % (bi + 1))
        for j, t in block:
            w("  [p%d] %s" % (j, t[:600]))

# FR-SUF-15 / FR-CHAT-07 bodies
for frname in ["FR-SUF-15", "FR-CHAT-07", "4.3.1.14", "4.3.2.11"]:
    bl = dump_from_heading(lambda ts, n=frname: ts.startswith(n) or re.match(r"^" + re.escape(n) + r"\b", ts), 70)
    w()
    w("### %s body dumps (%d)" % (frname, len(bl)))
    for bi, block in enumerate(bl[:3]):
        w("--- %s block %d ---" % (frname, bi + 1))
        for j, t in block[:55]:
            w("  [p%d] %s" % (j, t[:600]))

# Acceptance scenarios: look for Сценарий принятия near summary FR
w()
w("### Acceptance scenarios (сценар*/принят*) near Summary FR text")
accept_hits = []
for i, t in lines:
    if not re.search(r"сценар\w*\s+принят|критер\w*\s+принят|Acceptance", t, re.I):
        continue
    # window back/forward for summary
    window = " ".join(lines[j][1] for j in range(max(0, i - 30), min(len(lines), i + 40)))
    if summary_word.search(window) or "4.3.1.13" in window or "FR-SUF-15" in window:
        block = []
        for j in range(i, min(i + 35, len(lines))):
            jt = lines[j][1].strip()
            if jt:
                block.append((j, jt))
        accept_hits.append(block)
w("Accept blocks: %d" % len(accept_hits))
seen = set()
for block in accept_hits:
    key = block[0][0]
    if key in seen:
        continue
    seen.add(key)
    w("--- Accept @ p%d ---" % key)
    for j, t in block[:40]:
        w("  [p%d] %s" % (j, t[:600]))

# Also dump the detailed UC-style blocks already found at p1920/p2002/p3545
w()
w("### Key UC/scenario texts that mention Summary (curated)")
for idx in [1920, 1921, 2002, 2003, 2485, 2539, 2690, 3333, 3397, 3541, 3545, 3547, 5457, 5751, 5752]:
    if idx < len(paras):
        t = paras[idx]["text"].strip()
        if t:
            w("  [p%d] %s" % (idx, t[:800]))

w()
w("## 4) COVERAGE VERDICT")
chat_cover = [x for x in ii7_sum_paras if any("CHAT-T" in str(t) for t in x[1])]
suf_cover = [x for x in ii7_sum_paras if any("SUF-T" in str(t) for t in x[1])]
w("Paragraphs near CHAT-T-* mentioning Summary: %d" % len(chat_cover))
w("Paragraphs near SUF-T-* mentioning Summary: %d" % len(suf_cover))
# Is there CHAT-T-13?
has_chat13 = any("CHAT-T-13" in "".join(tags) or "CHAT-T-13" in t for _, tags, t in ii7_sum_paras)
has_suf_step = any(re.search(r"SUF-T-\d+", "".join(tags)) for _, tags, _ in ii7_sum_paras)
w("CHAT-T-13 referenced with Summary: %s" % has_chat13)
w("SUF-T-* referenced near Summary paras: %s" % has_suf_step)
w()
w("VERDICT:")
if has_chat13:
    w("YES — CHAT-T-13 already covers Summary (cross-channel history + summary; refs FR-SUF-15 / §4.3.1.13-14).")
else:
    w("CHAT-T-13 coverage unclear from proximity scan.")
if not suf_t_sum:
    w("NO dedicated SUF-T-NN step title/line embeds the word Summary; coverage is via FR-SUF-15 and CHAT-T-13 acceptance links.")
w()
w("Comment 1802 ('Нет описания Summary в приёмке') sits on the acceptance table header area (near SUF-T list) — meaning acceptance matrix may lack an explicit Summary row, even though CHAT-T-13 narrative covers it.")

w()
w("## COMMENT TEXTS (full)")
for cid, c in summary_comments:
    w("[%s] %s: %s" % (cid, c["author"], c["text"]))

out.write_text("\n".join(L), encoding="utf-8")
print("WROTE", out, out.stat().st_size)
print("comments", len(summary_comments))
print("ii7_sum_paras", len(ii7_sum_paras))
print("blocks_43113", len(blocks_43113))
print("chat_t13", len(chat_t13))
print("accept_hits", len(accept_hits))
print("sec_43113 idxs", sec_43113[:20])
# write a small UTF-8 report for parent without console issues
brief = Path(r"C:\Users\user\Desktop\sufler\sufler\_tmp_summary_accept_brief.txt")
# extract verdict + comments only
start = "\n".join(L)
brief.write_text(start, encoding="utf-8")
