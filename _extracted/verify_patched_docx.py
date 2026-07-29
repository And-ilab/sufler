# -*- coding: utf-8 -*-
import hashlib
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

desk = Path(r"C:\Users\user\Desktop")
files = sorted(desk.glob("TZ-unified-v1.4*.docx"), key=lambda p: p.stat().st_mtime)
print("files", [f.name for f in files])
src = next(f for f in files if "(1)" in f.name)
out = next(f for f in files if "+" in f.name)
print("src", src.name, src.stat().st_size)
print("out", out.name, out.stat().st_size)


def h(z: Path, n: str) -> str | None:
    with zipfile.ZipFile(z) as f:
        if n not in f.namelist():
            return None
        return hashlib.sha256(f.read(n)).hexdigest()


for n in ["word/comments.xml", "word/commentsExtended.xml"]:
    print(n, "SAME" if h(src, n) == h(out, n) else "DIFF")

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
with zipfile.ZipFile(out) as z:
    root = ET.fromstring(z.read("word/document.xml"))

ids = []
for p in root.iter(W + "p"):
    t = "".join(x.text or "" for x in p.iter(W + "t")).strip()
    if t.startswith(("SUF-T-", "CHAT-T-", "RPT-T-")):
        ids.append(t)
need = [
    f"SUF-T-{n:02d}" for n in (6, 7, 8, 9, 10, 11, 13, 14)
] + [
    f"CHAT-T-{n:02d}" for n in (6, 8, 9, 10, 11, 12, 14, 15, 16, 17, 18, 19, 20)
]
joined = "\n".join(ids)
print("count_headings", len(ids))
for n in need:
    ok = any(i.startswith(n + " —") or i.startswith(n + " -") or i == n for i in ids)
    # also accept startswith n + space/dash
    ok = ok or any(i.startswith(n) and ("—" in i or "-" in i) for i in ids)
    print(("OK" if ok else "MISSING"), n)

# detailed step tables only: titles containing em dash after id
detail = [i for i in ids if "—" in i or " - " in i]
Path(r"C:\Users\user\Desktop\sufler\sufler\_extracted\verify_headings.txt").write_text(
    "\n".join(detail), encoding="utf-8"
)
print("wrote verify_headings.txt", len(detail))
