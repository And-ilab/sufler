# -*- coding: utf-8 -*-
from pathlib import Path
import zipfile
from xml.etree import ElementTree as ET

p = next(Path(r"C:\Users\user\Desktop\666").glob("TZ-unified-v1.5*.docx"))
with zipfile.ZipFile(p) as z:
    xml = z.read("word/document.xml")
root = ET.fromstring(xml)
W_P = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p"
W_T = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t"

paras = []
for el in root.iter(W_P):
    texts = [t.text or "" for t in el.iter(W_T)]
    paras.append("".join(texts))

out = []

def dump_range(title, start, count):
    out.append("=" * 72)
    out.append(title)
    out.append("=" * 72)
    end = min(len(paras), start + count)
    for i in range(start, end):
        out.append(f"[{i}] {paras[i]}")
    out.append("")

# II.7 intro around 2973
ii7 = 2973
# verify
assert "II.7" in paras[ii7], paras[ii7][:80]
dump_range(f"II.7 intro — index {ii7}, 20 paragraphs", ii7, 20)

# VII.1
vii1 = next(i for i, t in enumerate(paras) if t.strip().startswith("VII.1."))
# prefer the body one near 6010 if TOC exists earlier
vii1_candidates = [i for i, t in enumerate(paras) if t.strip().startswith("VII.1.")]
vii1 = vii1_candidates[-1] if vii1_candidates else vii1
dump_range(f"VII.1 heading + next 40 paragraphs (from {vii1})", vii1, 41)

keys = ("устран", "дефект", "замечани")
first_vii_body = vii1
# acceptance context: from first substantial VII / приемк near end, plus TOC VII, plus paragraphs mentioning приемк near VII
accept_hits = [i for i, t in enumerate(paras) if "приемк" in t.lower() or "приёмк" in t.lower()]

windows = set(range(first_vii_body, min(len(paras), first_vii_body + 200)))
# also scan VI. / критерии приемки / устранение near end of doc and around accept_hits in body (not just TOC)
for a in accept_hits:
    if a >= 2500:  # body region
        windows.update(range(max(0, a - 10), min(len(paras), a + 120)))

# include any keyword hit in body (>=2500) or explicitly near VII
all_matches = []
for i, t in enumerate(paras):
    low = t.lower()
    if any(k in low for k in keys):
        all_matches.append(i)
        if i >= 2500 or i >= first_vii_body - 50:
            windows.add(i)

matches = [i for i in sorted(windows) if any(k in paras[i].lower() for k in keys)]

out.append("=" * 72)
out.append("Paragraphs containing 'устран' / 'дефект' / 'замечани' (VII / acceptance context)")
out.append("=" * 72)
out.append(f"VII.1 idx={vii1}; xml paragraph count={len(paras)}")
out.append(f"приемк idxs (body>=2500): {[i for i in accept_hits if i>=2500][:50]}")
out.append("")
out.append(f"Keyword matches in VII/acceptance windows: {len(matches)}")
for i in matches:
    out.append(f"[{i}] {paras[i]}")
out.append("")
out.append("--- All doc keyword hits ---")
out.append(f"total={len(all_matches)}")
for i in all_matches:
    mark = " [VII+]" if i >= first_vii_body else ""
    out.append(f"[{i}]{mark} {paras[i]}")

# Also dump nearby context for each body keyword hit (±3)
out.append("")
out.append("=" * 72)
out.append("Context ±3 around keyword hits (body region i>=2500)")
out.append("=" * 72)
for i in all_matches:
    if i < 2500:
        continue
    out.append(f"--- hit at {i} ---")
    for j in range(max(0, i - 3), min(len(paras), i + 4)):
        out.append(f"[{j}] {paras[j]}")
    out.append("")

text = "\n".join(out)
out_path = Path(r"C:\Users\user\Desktop\sufler\sufler\_tmp_vii1.txt")
out_path.write_text(text, encoding="utf-8")
print("wrote", out_path)
print("ii7", ii7, "vii1", vii1, "matches", len(matches), "all", len(all_matches))
# print file to stdout via python with utf-8
import sys
sys.stdout.reconfigure(encoding="utf-8")
print(text)
