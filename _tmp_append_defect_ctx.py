# -*- coding: utf-8 -*-
from pathlib import Path
import zipfile
from xml.etree import ElementTree as ET

docx = Path(r"c:\Users\user\Desktop\666\TZ-unified-v1.5 (МИХ).docx")
out = Path(r"C:\Users\user\Desktop\sufler\sufler\_tmp_defect_sla_comment.txt")
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
with zipfile.ZipFile(docx) as z:
    root = ET.fromstring(z.read("word/document.xml"))
paras = ["".join(x.text or "" for x in p.iter(W + "t")) for p in root.iter(W + "p")]

lines = []
lines.append("")
lines.append("=== ACCEPTANCE SECTION CONTEXT (around comment 1737 / II.7) ===")
for j in range(2935, min(len(paras), 2975)):
    t = paras[j].strip()
    if t:
        lines.append(f"[{j}] {t}")

lines.append("")
lines.append("=== VII.2 CONTROL AND ACCEPTANCE (body excerpt) ===")
for j in range(6057, min(len(paras), 6125)):
    t = paras[j].strip()
    if t:
        lines.append(f"[{j}] {t}")

lines.append("")
lines.append("=== TZ TEXT mentioning устранение/дефект/гарантия (filtered) ===")
filt_hits = []
for i, t in enumerate(paras):
    low = t.lower()
    if not t.strip():
        continue
    hit = False
    if "срок" in low and ("устран" in low or "дефект" in low):
        hit = True
    if any(k in low for k in ["устранения ошибок", "срок устранения", "сроки устранения", "bugfix", "sla устранения"]):
        hit = True
    if "дефект" in low and ("приемк" in low or "приёмк" in low or "гарант" in low):
        hit = True
    if hit:
        filt_hits.append(f"[{i}] {t.strip()[:500]}")
        lines.append(filt_hits[-1])

lines.append("")
lines.append(
    f"(filtered body hits: {len(filt_hits)}; "
    "phrases сроки устранения / устранения ошибок / bugfix / sla устранения NOT found in body text)"
)

prev = out.read_text(encoding="utf-8")
marker = "=== ACCEPTANCE SECTION CONTEXT"
if marker in prev:
    prev = prev.split(marker)[0].rstrip()
out.write_text(prev + "\n" + "\n".join(lines), encoding="utf-8")

print(out.read_text(encoding="utf-8")[:8000])
print("\n...[truncated]...\n")
print("FILE:", out, "SIZE:", out.stat().st_size)
