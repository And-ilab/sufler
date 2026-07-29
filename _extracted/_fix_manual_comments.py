# -*- coding: utf-8 -*-
"""Extract comments from operation manual docx for review."""
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

docx = Path(r"c:\Users\user\Downloads\Rukovodstvo_po_ekspluatacii_dvuhstancionnaya_namotochnaya_mashina1.docx")
out = Path(r"C:\Users\user\Desktop\sufler\sufler\_extracted\manual_comments.txt")


def text_of(el: ET.Element) -> str:
    parts = []
    for t in el.iter(W + "t"):
        if t.text:
            parts.append(t.text)
        if t.tail:
            parts.append(t.tail)
    return "".join(parts).strip()


def main():
    print("exists", docx.exists(), docx)
    with zipfile.ZipFile(docx) as z:
        names = z.namelist()
        print("comment parts:", [n for n in names if "comment" in n.lower()])
        if "word/comments.xml" not in names:
            print("NO COMMENTS")
            return
        root = ET.fromstring(z.read("word/comments.xml"))
        comments = []
        for c in root.findall(W + "comment"):
            cid = int(c.get(W + "id"))
            author = c.get(W + "author", "")
            date = c.get(W + "date", "")
            paras = []
            for p in c.findall(W + "p"):
                t = text_of(p)
                if t:
                    paras.append(t)
            comments.append((cid, author, date, "\n".join(paras)))

        doc = ET.fromstring(z.read("word/document.xml"))
        anchored = {}
        active = {}
        for el in doc.iter():
            tag = el.tag
            if tag == W + "commentRangeStart":
                active[el.get(W + "id")] = []
            elif tag == W + "commentRangeEnd":
                cid = el.get(W + "id")
                if cid in active:
                    anchored[cid] = "".join(active.pop(cid)).strip()
            elif tag == W + "t" and active and el.text:
                for cid in active:
                    active[cid].append(el.text)

        # parent replies
        parent = {}
        cid_to_para = {}
        for c in root.findall(W + "comment"):
            cid = int(c.get(W + "id"))
            for p in c.findall(W + "p"):
                para = p.get("{http://schemas.microsoft.com/office/word/2010/wordml}paraId")
                if para:
                    cid_to_para[cid] = para
                    break
        para_to_cid = {v: k for k, v in cid_to_para.items()}
        if "word/commentsExtended.xml" in names:
            W15 = "{http://schemas.microsoft.com/office/word/2012/wordml}"
            ex = ET.fromstring(z.read("word/commentsExtended.xml"))
            for ce in ex.findall(W15 + "commentEx"):
                para = ce.get(W15 + "paraId")
                par = ce.get(W15 + "paraIdParent")
                cid = para_to_cid.get(para)
                if cid is None or not par:
                    continue
                pc = para_to_cid.get(par)
                if pc is not None:
                    parent[cid] = pc

    comments.sort(key=lambda x: x[0])
    lines = [f"FILE: {docx.name}", f"COUNT: {len(comments)}", ""]
    for cid, author, date, body in comments:
        is_reply = cid in parent
        prefix = f"REPLY->{parent[cid]} " if is_reply else ""
        lines.append(f"--- #{cid} {prefix}[{author}] {date}")
        anchor = anchored.get(str(cid), "")
        if anchor:
            lines.append(f"ANCHOR: {anchor[:500]}")
        lines.append(body)
        lines.append("")
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {out} with {len(comments)} comments")
    print("Top-level:", sum(1 for c, *_ in comments if c not in parent))
    print("Authors:", sorted({a for _, a, _, _ in comments}))


if __name__ == "__main__":
    main()
