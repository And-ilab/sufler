from pathlib import Path
p = Path(r"C:\Users\user\Desktop\sufler\sufler\_extracted\_inspect_passport.py")
t = p.read_text(encoding="utf-8")
old = "    lines: list[str] = []\n    w = lines.append"
new = "    lines: list[str] = []\n    def w(s=\"\"):\n        lines.append(s)"
if old not in t:
    raise SystemExit("pattern missing")
p.write_text(t.replace(old, new, 1), encoding="utf-8")
print("patched")
