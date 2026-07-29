import zipfile, re, html
from pathlib import Path
from xml.etree import ElementTree as ET

desktop = Path(r"c:\Users\user\Desktop")
docx = next(desktop.glob("TZ-unified-v1.4*.docx"))
out = Path(r"C:\Users\user\Desktop\sufler\sufler\_extracted\tz-v1.4-remarks-comments.txt")
out.parent.mkdir(parents=True, exist_ok=True)

NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "w14": "http://schemas.microsoft.com/office/word/2010/wordml",
    "w15": "http://schemas.microsoft.com/office/word/2012/wordml",
}

def text_of(el):
    parts = []
    for t in el.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t"):
        if t.text:
            parts.append(t.text)
        if t.tail:
            parts.append(t.tail)
    return "".join(parts).strip()

with zipfile.ZipFile(docx) as z:
    names = z.namelist()
    comment_parts = [n for n in names if "comment" in n.lower()]
    print("parts:", comment_parts)
    if "word/comments.xml" not in names:
        print("NO COMMENTS")
        raise SystemExit(1)
    root = ET.fromstring(z.read("word/comments.xml"))
    comments = []
    for c in root.findall("w:comment", NS):
        cid = c.get("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}id")
        author = c.get("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}author", "")
        date = c.get("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}date", "")
        initials = c.get("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}initials", "")
        paras = []
        for p in c.findall("w:p", NS):
            t = text_of(p)
            if t:
                paras.append(t)
        body = "\n".join(paras).strip()
        comments.append((int(cid), author, date, initials, body))

    # parent map from commentsExtended if present
    parent = {}
    done = {}
    if "word/commentsExtended.xml" in names:
        ex = ET.fromstring(z.read("word/commentsExtended.xml"))
        # Map paraId -> done/parent; need comments ids via comments.xml paraIds - hard.
        # Alternative: use commentsIds.xml if present
        print("extended present")
    if "word/commentsIds.xml" in names:
        print("commentsIds present")

    # Get anchored text ranges from document.xml
    doc = ET.fromstring(z.read("word/document.xml"))
    W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    anchored = {}
    # Walk document collecting comment range texts
    active = {}  # id -> list of text fragments
    # simpler: find commentRangeStart/End and collect intervening text
    # Use iterative approach on all elements in order
    events = []
    for el in doc.iter():
        tag = el.tag
        if tag == W + "commentRangeStart":
            cid = el.get(W + "id")
            active[cid] = []
        elif tag == W + "commentRangeEnd":
            cid = el.get(W + "id")
            if cid in active:
                anchored[cid] = "".join(active.pop(cid)).strip()
        elif tag == W + "t" and active:
            if el.text:
                for cid in active:
                    active[cid].append(el.text)

comments.sort(key=lambda x: x[0])
lines = []
lines.append(f"FILE: {docx.name}")
lines.append(f"COUNT: {len(comments)}")
lines.append("")
for cid, author, date, initials, body in comments:
    anchor = anchored.get(str(cid), "")
    lines.append(f"--- #{cid} [{author}] {date}")
    if anchor:
        lines.append(f"ANCHOR: {anchor[:300]}")
    lines.append(body)
    lines.append("")

out.write_text("\n".join(lines), encoding="utf-8")
print(f"Wrote {out} with {len(comments)} comments")
print("Authors:", sorted(set(a for _,a,_,_,_ in comments)))
