# -*- coding: utf-8 -*-
import zipfile
import xml.etree.ElementTree as ET
import re
import os
from pathlib import Path

files = [
    r"c:\Users\user\Downloads\Double_station_winding_machine_unpacking_steps_+_threading_operation.pptx",
    r"c:\Users\user\Downloads\Parameter settings (2).pptx",
]
out_dir = Path(r"C:\Users\user\Desktop\sufler\sufler\_extracted")
out_dir.mkdir(parents=True, exist_ok=True)

NS_A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"

for f in files:
    name = Path(f).stem
    out_path = out_dir / f"{name}_slides.txt"
    lines = [f"FILE: {f}", f"EXISTS: {os.path.exists(f)}"]
    if not os.path.exists(f):
        out_path.write_text("\n".join(lines), encoding="utf-8")
        continue
    with zipfile.ZipFile(f) as z:
        slides = sorted(
            [n for n in z.namelist() if re.match(r"ppt/slides/slide\d+\.xml$", n)],
            key=lambda x: int(re.findall(r"\d+", x)[0]),
        )
        lines.append(f"SLIDES: {len(slides)}")
        for s in slides:
            root = ET.fromstring(z.read(s))
            texts = []
            for t in root.iter(f"{NS_A}t"):
                if t.text and t.text.strip():
                    texts.append(t.text.strip())
            lines.append(f"\n{'='*40}\n{s}\n{'='*40}")
            lines.extend(texts)
    out_path.write_text("\n".join(lines), encoding="utf-8")
    # ASCII-only status for console
    print(f"OK {out_path.name} slides={len(slides)} bytes={out_path.stat().st_size}")
