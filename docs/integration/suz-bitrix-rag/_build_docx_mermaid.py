# -*- coding: utf-8 -*-
"""Render mermaid in TZ md to PNG and build DOCX."""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import zipfile
from pathlib import Path

ROOT = Path(r"c:\sufler\docs\integration\suz-bitrix-rag")
MD = ROOT / "tz-bitrix-rag-sufler.md"
TMP = ROOT / "_mermaid_tmp"
EXPORT = ROOT / "_export_with_diagrams.md"
DOCX = ROOT / "TZ-Bitrix-RAG.docx"
PANDOC = Path(r"C:\Program Files\Pandoc\pandoc.exe")
STATUS = ROOT / "_pipeline_status.txt"


def log(msg: str) -> None:
    print(msg, flush=True)
    with STATUS.open("a", encoding="utf-8") as f:
        f.write(msg + "\n")


def which_cmd(*names: str) -> str | None:
    """Resolve .exe/.cmd/.bat on Windows PATH."""
    for name in names:
        found = shutil.which(name)
        if found:
            return found
        if os.name == "nt" and not name.lower().endswith((".cmd", ".bat", ".exe")):
            for ext in (".cmd", ".bat", ".exe"):
                found = shutil.which(name + ext)
                if found:
                    return found
    return None


def mermaid_cmd(mmd: Path, png: Path) -> list[str]:
    """Build argv that CreateProcess can launch on Windows."""
    mmdc = which_cmd("mmdc", "mmdc.cmd")
    if mmdc:
        return [mmdc, "-i", str(mmd), "-o", str(png), "-b", "white"]

    npx = which_cmd("npx", "npx.cmd")
    if not npx:
        raise SystemExit(
            "Neither mmdc nor npx found on PATH. Install Node.js and "
            "`npm i -g @mermaid-js/mermaid-cli`, then retry."
        )
    # npx.cmd must go through cmd.exe on Windows
    if os.name == "nt":
        return [
            "cmd.exe",
            "/c",
            npx,
            "-y",
            "@mermaid-js/mermaid-cli",
            "-i",
            str(mmd),
            "-o",
            str(png),
            "-b",
            "white",
        ]
    return [
        npx,
        "-y",
        "@mermaid-js/mermaid-cli",
        "-i",
        str(mmd),
        "-o",
        str(png),
        "-b",
        "white",
    ]


def main() -> None:
    if STATUS.exists():
        STATUS.unlink()
    if TMP.exists():
        shutil.rmtree(TMP)
    TMP.mkdir(parents=True)

    text = MD.read_text(encoding="utf-8")
    pattern = re.compile(r"```mermaid\s*(.*?)```", re.DOTALL | re.IGNORECASE)
    blocks = list(pattern.finditer(text))
    log(f"mermaid_count={len(blocks)}")
    if not blocks:
        raise SystemExit("no mermaid blocks")

    log(f"mmdc={which_cmd('mmdc', 'mmdc.cmd')}")
    log(f"npx={which_cmd('npx', 'npx.cmd')}")

    pngs: list[Path] = []
    for i, m in enumerate(blocks, 1):
        stem = f"diag-{i:02d}"
        mmd = TMP / f"{stem}.mmd"
        png = TMP / f"{stem}.png"
        mmd.write_text(m.group(1).strip() + "\n", encoding="utf-8")
        cmd = mermaid_cmd(mmd, png)
        log(f"render {stem}: {' '.join(cmd)}")
        r = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True)
        if r.returncode != 0:
            log(f"stderr={r.stderr}")
            log(f"stdout={r.stdout}")
            raise SystemExit(f"render failed for {stem} code={r.returncode}")
        if not png.exists():
            raise SystemExit(f"missing png {png}")
        pngs.append(png)
        log(f"ok {png.name} bytes={png.stat().st_size}")

    # Build export md with images
    out_parts: list[str] = []
    last = 0
    for i, m in enumerate(blocks, 1):
        out_parts.append(text[last : m.start()])
        rel = f"_mermaid_tmp/diag-{i:02d}.png"
        out_parts.append(f"\n\n![Диаграмма {i}]({rel})\n\n")
        last = m.end()
    out_parts.append(text[last:])
    EXPORT.write_text("".join(out_parts), encoding="utf-8")
    log(f"wrote {EXPORT}")

    if not PANDOC.exists():
        raise SystemExit(f"pandoc missing: {PANDOC}")
    cmd = [
        str(PANDOC),
        str(EXPORT),
        "-o",
        str(DOCX),
        "--from",
        "markdown",
        "--to",
        "docx",
        "--standalone",
        "--toc",
        "--toc-depth=3",
        f"--resource-path={ROOT};{TMP}",
    ]
    log("pandoc...")
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        log(r.stderr)
        raise SystemExit(f"pandoc failed {r.returncode}")

    media = []
    with zipfile.ZipFile(DOCX, "r") as z:
        media = [n for n in z.namelist() if n.startswith("word/media/")]
    st = DOCX.stat()
    log(
        f"DONE path={DOCX} media_count={len(media)} size={st.st_size} mtime={st.st_mtime}"
    )
    for n in media:
        log(f"media:{n}")


if __name__ == "__main__":
    main()
