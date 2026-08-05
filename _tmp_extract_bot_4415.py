# -*- coding: utf-8 -*-
import zipfile, xml.etree.ElementTree as ET, json
from pathlib import Path

docx = Path(r"c:\Users\user\Desktop\666") / "TZ-unified-v1.5 (\u041c\u0418\u0425).docx"
# resolve actual file
cands = list(Path(r"c:\Users\user\Desktop\666").glob("TZ-unified-v1.5*.docx"))
docx = cands[0]
out = Path(r"C:\Users\user\Desktop\sufler\sufler\_tmp_bot_4415.txt")
outj = Path(r"C:\Users\user\Desktop\sufler\sufler\_tmp_bot_4415.json")

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}

def texts(el):
    return "".join(t.text or "" for t in el.iter(W + "t"))

needles = [
    "4.4.15",
    "\u043d\u0430\u0441\u0442\u0440\u0430\u0438\u0432\u0430\u0435\u0442\u0441\u044f \u044d\u0442\u043e\u0442 \u0431\u043e\u0442",
    "\u041a\u0430\u043a\u0438\u0435 \u0437\u043d\u0430\u043d\u0438\u044f",
    "\u041d\u0435 \u043f\u043e\u043d\u044f\u0442\u0435\u043d \u0444\u0443\u043d\u043a\u0446\u0438\u043e\u043d\u0430\u043b",
    "\u041d\u0438\u0433\u0434\u0435 \u043d\u0435 \u043e\u043f\u0438\u0441\u0430\u043d \u043f\u0443\u043d\u043a\u0442",
]

with zipfile.ZipFile(docx) as z:
    comments_xml = z.read("word/comments.xml")
    document_xml = z.read("word/document.xml")

root = ET.fromstring(comments_xml)
all_comments = root.findall("w:comment", NS)
matched = []
for c in all_comments:
    cid = c.get(W + "id")
    author = c.get(W + "author")
    date = c.get(W + "date")
    text = texts(c).strip()
    if any(n in text for n in needles):
        matched.append({"id": cid, "author": author, "date": date, "text": text})

doc = ET.fromstring(document_xml)
body = doc.find("w:body", NS)
current_open = set()
para_buffer = {}
paras = []
for p in body.iter(W + "p"):
    ptext = texts(p)
    ends = []
    for el in p.iter():
        tag = el.tag.split("}")[-1]
        if tag == "commentRangeStart":
            cid = el.get(W + "id")
            current_open.add(cid)
            para_buffer.setdefault(cid, [])
        elif tag == "commentRangeEnd":
            ends.append(el.get(W + "id"))
        elif tag == "commentReference":
            cid = el.get(W + "id")
            if cid not in para_buffer:
                para_buffer[cid] = []
    for cid in list(current_open):
        if ptext.strip():
            para_buffer.setdefault(cid, []).append(ptext.strip())
    for cid in ends:
        current_open.discard(cid)
    if ptext.strip():
        paras.append(ptext.strip())

bn = [
    "4.4.15",
    "\u0431\u043e\u0442 \u043f\u0435\u0440\u0432\u043e\u0439 \u043b\u0438\u043d\u0438\u0438",
    "chatbot",
    "\u043a\u043d\u043e\u043f\u043e\u0447\u043d",
]
body_hits = []
for i, p in enumerate(paras):
    pl = p.lower()
    reasons = []
    if "4.4.15" in p:
        reasons.append("4.4.15")
    if bn[1] in p:
        reasons.append(bn[1])
    if "chatbot" in pl:
        reasons.append("chatbot")
    if bn[3] in pl:
        reasons.append(bn[3])
    if reasons:
        body_hits.append({"i": i, "reasons": reasons, "text": p})

appears = any("4.4.15" in p for p in paras)

lines = []
lines.append("=== MATCHED COMMENTS ===")
lines.append("Total comments in doc: %d" % len(all_comments))
lines.append("Matched: %d" % len(matched))
lines.append("4.4.15 appears in body: %s" % appears)
lines.append("")
for m in matched:
    ctx = para_buffer.get(m["id"], [])
    seen = set()
    uctx = []
    for t in ctx:
        if t not in seen:
            seen.add(t)
            uctx.append(t)
    lines.append("ID: %s" % m["id"])
    lines.append("Author: %s" % m["author"])
    lines.append("Date: %s" % m["date"])
    lines.append("Full text: %s" % m["text"])
    lines.append("REF/context:")
    lines.append("\n---\n".join(uctx) if uctx else "(no range context found)")
    lines.append("=" * 60)
    lines.append("")

lines.append("=== BODY PARAGRAPHS (4.4.15 / bot first line / chatbot / knopochn) ===")
lines.append("Hits: %d" % len(body_hits))
lines.append("")
for h in body_hits:
    lines.append("[para #%d] matches: %s" % (h["i"], ", ".join(h["reasons"])))
    lines.append(h["text"])
    lines.append("-" * 40)

out.write_text("\n".join(lines), encoding="utf-8-sig")
payload = {
    "docx": str(docx),
    "matched": matched,
    "appears_4415_body": appears,
    "body_hits": body_hits,
    "contexts": {m["id"]: para_buffer.get(m["id"], []) for m in matched},
}
outj.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(payload, ensure_ascii=False, indent=2))
print("WROTE", out)