# -*- coding: utf-8 -*-
"""Export all IB markdown files to docx via pandoc."""
import os
import subprocess
import sys

BASE = os.path.join(
    r"c:\sufler\docs\sources",
    "\u0430\u043d\u043a\u0435\u0442\u0430 \u043f\u043e \u043a\u0438\u0431\u0435\u0440\u0443\u0441\u0442\u043e\u0439\u0447\u0438\u0432\u043e\u0441\u0442\u0438",
)
OUT = os.path.join(BASE, "outgoing", "docx")
OUT_DOCS = os.path.join(OUT, "documents")

SKIP_PREFIX = ("_",)
SKIP_NAMES = {"README.md", "INDEX-dokumenty.md"}


def find_pandoc():
    for cmd in ("pandoc", r"C:\Program Files\Pandoc\pandoc.exe"):
        try:
            r = subprocess.run([cmd, "--version"], capture_output=True, text=True)
            if r.returncode == 0:
                return cmd
        except FileNotFoundError:
            continue
    return None


def export(pandoc, src, dst, title):
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    print(f"  {os.path.relpath(src, BASE)} -> {os.path.relpath(dst, BASE)}")
    r = subprocess.run(
        [
            pandoc,
            src,
            "-o",
            dst,
            "--from",
            "markdown",
            "--to",
            "docx",
            "--standalone",
            "--metadata",
            f"title={title}",
        ],
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        print(r.stderr, file=sys.stderr)
        raise SystemExit(f"pandoc failed: {src}")


def main():
    pandoc = find_pandoc()
    if not pandoc:
        print("Pandoc not found. Install: winget install --id JohnMacFarlane.Pandoc -e", file=sys.stderr)
        sys.exit(1)

    os.makedirs(OUT_DOCS, exist_ok=True)
    count = 0

    # plan-dorabotok.md
    plan = os.path.join(BASE, "plan-dorabotok.md")
    if os.path.isfile(plan):
        export(pandoc, plan, os.path.join(OUT, "plan-dorabotok.docx"), "plan-dorabotok")
        count += 1

    # documents/
    docs_dir = os.path.join(BASE, "documents")
    if os.path.isdir(docs_dir):
        for name in sorted(os.listdir(docs_dir)):
            if not name.endswith(".md"):
                continue
            src = os.path.join(docs_dir, name)
            base = os.path.splitext(name)[0]
            export(pandoc, src, os.path.join(OUT_DOCS, f"{base}.docx"), base)
            count += 1

    # outgoing/*.md (not in docx subfolder)
    out_dir = os.path.join(BASE, "outgoing")
    if os.path.isdir(out_dir):
        for name in sorted(os.listdir(out_dir)):
            if not name.endswith(".md"):
                continue
            if name in SKIP_NAMES:
                continue
            src = os.path.join(out_dir, name)
            base = os.path.splitext(name)[0]
            export(pandoc, src, os.path.join(OUT, f"{base}.docx"), base)
            count += 1

    # Also export politika from documents is already done
    # Write manifest
    manifest = os.path.join(OUT, "_export_manifest.txt")
    with open(manifest, "w", encoding="utf-8") as f:
        for root, _, files in os.walk(OUT):
            for fn in sorted(files):
                if fn.endswith(".docx"):
                    f.write(os.path.join(root, fn) + "\n")

    print(f"\nDone: {count} docx -> {OUT}")


if __name__ == "__main__":
    main()
