import pathlib
lines=pathlib.Path(r"c:\sufler\docs\modules\ai-hub\tz-unified-v1.4.md").read_text(encoding="utf-8").splitlines()
out=[]
for i,l in enumerate(lines):
    if l.startswith("| II-7 |") or l.startswith("| II-3 |"):
        out.append(f"LINE {i+1}\n{l}\n")
pathlib.Path(r"c:\sufler\_tmp_tz_rows.txt").write_text("\n".join(out), encoding="utf-8")
