import re, pathlib
t=pathlib.Path(r"C:\Users\bkp2.LAPTOP-714KMOB9\.cursor\projects\c-sufler\canvases\online-chat-mockups.canvas.tsx").read_text(encoding="utf-8")
ver=re.search(r'CANVAS_MOCKUP_VERSION = "([^"]+)"', t).group(1)
chg=t.splitlines()[36] if len(t.splitlines())>36 else ""
print(ver)
print(chg)
