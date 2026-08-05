# -*- coding: utf-8 -*-
import zipfile, re, sys
from xml.etree import ElementTree as ET
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

docx = Path(r"c:\Users\user\Desktop\666") / [
    p.name for p in Path(r"c:\Users\user\Desktop\666").glob("TZ-unified-v1.5*.docx")
    if not p.name.startswith("~$")
][0]

NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

def para_text(p):
    parts = []
    for t in p.iter(W + "t"):
        if t.text:
            parts.append(t.text)
        if t.tail:
            parts.append(t.tail)
    return "".join(parts)

def local(tag):
    return tag.split("}")[-1] if "}" in tag else tag

with zipfile.ZipFile(docx) as z:
    comments_xml = z.read("word/comments.xml")
    document_xml = z.read("word/document.xml")

comments_root = ET.fromstring(comments_xml)
doc_root = ET.fromstring(document_xml)
body = doc_root.find("w:body", NS)
paras = list(body.iter(W + "p"))

KEYWORDS = [
    "создания сценари",
    "порядк",
    "10 штук",
    "как работает",
    "функционал создания",
    "эот функционал",
    "этот функционал",
]

def matches_kw(text):
    tl = text.lower()
    return [k for k in KEYWORDS if k.lower() in tl]

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

out = []
def log(s=""):
    out.append(s)

log("=" * 80)
log("MATCHING COMMENTS")
log("File: " + str(docx))
log("=" * 80)
matched = []
for cid, info in comments.items():
    hits = matches_kw(info["text"])
    if hits:
        matched.append((cid, info, hits))
matched.sort(key=lambda x: int(x[0]) if str(x[0]).isdigit() else x[0])
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
    log("")

body_ii35 = 2005
t2005 = para_text(paras[2005]).strip()
log("=" * 80)
log("II.3.5 BODY SECTION (real heading)")
log("=" * 80)
log(f"[2005] {t2005}")

next_section = None
for j in range(2006, min(len(paras), 2800)):
    t = para_text(paras[j]).strip()
    if re.match(r"^II\.4\b", t) or t.startswith("II.4 ") or t.startswith("II.4."):
        next_section = j
        break
    if re.match(r"^II\.6\b", t) and not t.startswith("II.3.5"):
        # II.6 after II.3.5 area sometimes
        pass

# Prefer first II.4 after 2005
for j in range(2006, min(len(paras), 3200)):
    t = para_text(paras[j]).strip()
    if re.match(r"^II\.4(\.|$|\s)", t):
        next_section = j
        break

# If not found, look for II.3.6
if next_section is None:
    for j in range(2006, min(len(paras), 3200)):
        t = para_text(paras[j]).strip()
        if re.match(r"^II\.3\.6", t):
            next_section = j
            break

log(f"Next section candidate: {next_section} -> {para_text(paras[next_section]).strip()[:160] if next_section else 'N/A'}")

end = next_section if next_section else 2400
if end - body_ii35 > 450:
    end = body_ii35 + 450

log("")
log("-" * 80)
log(f"DUMP II.3.5 body paragraphs [{body_ii35} .. {end-1}]")
log("-" * 80)
for j in range(body_ii35, end):
    pt = para_text(paras[j]).strip()
    if pt:
        log(f"[{j}] {pt}")

log("")
log("=" * 80)
log("FR-SCR / UC related + acceptance (scenario editor)")
log("=" * 80)
fr_idxs = []
for i, p in enumerate(paras):
    t = para_text(p)
    if i < 1600:
        continue
    if re.search(
        r"FR-SCR|UC-SCR|SUF-T-0?9|SUF-T-10|SUF-T-11|редактор сценари|Scenarios & Prompts|создан.*сценари|сценари.*создан",
        t,
        re.I,
    ):
        fr_idxs.append(i)

windows = set()
for i in fr_idxs:
    windows.update(range(max(0, i - 2), min(len(paras), i + 4)))
for i, p in enumerate(paras):
    t = para_text(p)
    if "FR-SCR" in t and i >= 2900:
        windows.update(range(max(0, i - 2), min(len(paras), i + 5)))

for j in sorted(windows):
    pt = para_text(paras[j]).strip()
    if not pt:
        continue
    marker = ">>>" if j in fr_idxs else "   "
    log(f"{marker} [{j}] {pt}")

log("")
log("=" * 80)
log("Appendix CC-SCR-001..010 list area")
log("=" * 80)
for j in range(6210, min(len(paras), 6280)):
    pt = para_text(paras[j]).strip()
    if pt:
        log(f"[{j}] {pt}")

# Also dump SUF-T-11 acceptance block fully
log("")
log("=" * 80)
log("SUF-T-09..12 acceptance blocks (context)")
log("=" * 80)
for j in range(3185, min(len(paras), 3245)):
    pt = para_text(paras[j]).strip()
    if pt:
        log(f"[{j}] {pt}")

log("")
log("=" * 80)
log("SHORT SUMMARY: what TZ says about creating scenarios")
log("=" * 80)
log(
    """
1) Comment #1807 (Солдатенко Е.П.) on acceptance row CC-SCR-001…010 / FR-SCR-01:
   Asks for description of the order/process of creating scenarios (e.g. the 10 existing ones);
   says nowhere is it described how the scenario-creation functionality works.

2) II.3.5 «Настройки (редактор сценариев, LLM Контакт-центра)»:
   - II.3.5.1 Редактор диалоговых сценариев via Hub → «Редактор сценариев» /
     Embed Scenarios & Prompts Studio (sufler_cc) at /ai-hub/admin.
   - Goal: администратор управляет сценариями и промптами (§2.4 п.6).
   - CRUD сценариев/промптов, versioning on publish, test-run 4.5.2.7–8.
   - Промпты управляются внутри редактора сценария (не отдельный сайт).
   - Draft → saved → available for publication; acceptance: admin smoke.

3) FR-SCR-01 / FR-SCR-10 + SUF-T-09..11:
   - ≥50 scenarios production backlog (FR-SCR-01 / SUF-T-10).
   - Test-run for registry scenarios (FR-SCR-10 / SUF-T-11).
   - CC-SCR-001…010: ветки как в Прил.2 — acceptance checks branches (позитив/возражение/эскалация).
   - SUF-T-11: for all 10 CC-SCR scenarios, branches must match Прил.2.

4) Gap vs comment: TZ describes editor capabilities (CRUD, prompts, publish, test-run)
   and acceptance of the 10 fixed CC-SCR scenarios' content/branches, but does NOT
   spell out a step-by-step «порядок создания» of those scenarios as a UC/procedure.
"""
)

out_path = Path(r"C:\Users\user\Desktop\sufler\sufler\_tmp_scenario_create_comment.txt")
text = "\n".join(out) + "\n"
out_path.write_text(text, encoding="utf-8")
print(text)
print("WROTE", out_path, "bytes", out_path.stat().st_size)
